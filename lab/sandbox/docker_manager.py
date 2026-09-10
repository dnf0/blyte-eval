"""Docker lifecycle and host disk space management.

Ensures deterministic container removal, volume pruning, and pre-flight
disk space safety checks to prevent host filesystem saturation.
"""

from __future__ import annotations

from contextlib import contextmanager
import io
import logging
from pathlib import Path
import shutil
import tarfile
from typing import Any, Generator, Mapping

import docker
from docker.models.containers import Container

logger = logging.getLogger("superstate_eval.docker_manager")


class DiskSpaceError(RuntimeError):
    """Raised when host disk space falls below the critical emergency threshold."""


class WorkspaceSeedError(RuntimeError):
    """Raised when the task repository cannot be materialized onto the host."""


class ImageBuildError(RuntimeError):
    """Raised when an image (typically the held-out verifier) cannot be built."""


class DockerManager:
    """Manages Docker containers and host disk resource reclamation."""

    def __init__(self, client: docker.DockerClient | None = None) -> None:
        self._client = client

    @property
    def client(self) -> docker.DockerClient:
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    @contextmanager
    def run_sandbox(
        self,
        image: str,
        command: str = "sleep infinity",
        volumes: Mapping[str, Mapping[str, str]] | None = None,
        working_dir: str = "/app",
        network_mode: str | None = None,
        environment: Mapping[str, str] | None = None,
        nano_cpus: int | None = None,
        mem_limit: str | None = "4g",
        logs_dir: Path | str | None = None,
        container_name: str | None = None,
    ) -> Generator[Container, None, None]:
        """Run a container with guaranteed teardown upon context exit.

        Guarantees that the container is forcefully removed even if the block
        raises an unhandled exception or times out.
        """
        combined_volumes = dict(volumes or {})
        if logs_dir is not None:
            logs_path = Path(logs_dir).resolve()
            logs_path.mkdir(parents=True, exist_ok=True)
            combined_volumes[str(logs_path)] = {"bind": "/logs", "mode": "rw"}

        run_kwargs: dict[str, Any] = {
            "image": image,
            "command": command,
            "volumes": combined_volumes,
            "working_dir": working_dir,
            "network_mode": network_mode,
            "environment": environment or {},
            "detach": True,
            "remove": False,  # We manage removal explicitly in the finally block
        }
        if nano_cpus is not None:
            run_kwargs["nano_cpus"] = nano_cpus
        if mem_limit is not None:
            run_kwargs["mem_limit"] = mem_limit
        if container_name is not None:
            run_kwargs["name"] = container_name

        container = self.client.containers.run(**run_kwargs)
        logger.info(f"Spawned sandbox container: {container.id[:12]} ({image})")
        try:
            yield container
        finally:
            logger.info(f"Tearing down sandbox container: {container.id[:12]}")
            try:
                container.remove(force=True)
            except Exception as e:
                logger.warning(f"Error removing container {container.id[:12]}: {e}")

    def seed_workspace_from_image(
        self,
        image: str,
        dest: Path | str,
        source_path: str = "/app",
    ) -> int:
        """Copy the task repository out of `image` into the host directory `dest`.

        A bind mount SHADOWS whatever the image ships at the mount point, so
        mounting an empty host directory onto /app hides the task repository from
        both the agent and the grader. The workspace must therefore be seeded from
        the image before it is mounted.

        Returns the number of entries extracted. Raises WorkspaceSeedError if the
        image has nothing at `source_path`.
        """
        dest_path = Path(dest)
        dest_path.mkdir(parents=True, exist_ok=True)

        try:
            container = self.client.containers.create(image=image, command="true")
        except Exception as err:
            raise WorkspaceSeedError(
                f"Cannot seed workspace: image '{image}' is unavailable ({err}). "
                "Pull or build the task image before running the evaluation."
            ) from err
        try:
            try:
                stream, _stat = container.get_archive(source_path)
            except Exception as err:
                raise WorkspaceSeedError(
                    f"Image '{image}' has no '{source_path}' to seed the workspace from: {err}"
                ) from err

            raw = io.BytesIO(b"".join(stream))
            prefix = Path(source_path).name + "/"
            extracted = 0
            with tarfile.open(fileobj=raw, mode="r:*") as tar:
                for member in tar.getmembers():
                    # get_archive tars the directory itself; strip the leading component.
                    if member.name == Path(source_path).name:
                        continue
                    if not member.name.startswith(prefix):
                        continue
                    member.name = member.name[len(prefix) :]
                    if not member.name:
                        continue
                    if (member.islnk() or member.issym()) and member.linkname.startswith(prefix):
                        member.linkname = member.linkname[len(prefix) :]
                    tar.extract(member, path=dest_path, filter="tar")
                    extracted += 1
        finally:
            try:
                container.remove(force=True)
            except Exception as err:
                logger.warning("Failed to remove seed container: %s", err)

        if extracted == 0:
            raise WorkspaceSeedError(
                f"Image '{image}' produced an empty workspace from '{source_path}'"
            )

        logger.info("Seeded workspace %s from %s:%s (%d entries)", dest_path, image, source_path, extracted)
        return extracted

    def build_image(self, context_dir: Path | str, tag: str, timeout: int = 1800) -> str:
        """Build an image from `context_dir` and return its tag.

        Used for the held-out verifier, whose Dockerfile layers the hidden tests
        on top of the task image. The agent never sees this image.
        """
        context = Path(context_dir)
        if not (context / "Dockerfile").is_file():
            raise ImageBuildError(f"No Dockerfile in build context {context}")
        with self._suppressed_registry_auth():
            try:
                _image, _logs = self.client.images.build(
                    path=str(context), tag=tag, rm=True, forcerm=True, timeout=timeout
                )
            except Exception as err:
                raise ImageBuildError(
                    f"Failed to build image '{tag}' from {context}: {err}"
                ) from err
        logger.info("Built image %s from %s", tag, context)
        return tag

    def build_image_from_dockerfile(
        self, dockerfile: str, tag: str, timeout: int = 1800
    ) -> str:
        """Build an image from an inline Dockerfile with no build context."""
        with self._suppressed_registry_auth():
            try:
                _image, _logs = self.client.images.build(
                    fileobj=io.BytesIO(dockerfile.encode("utf-8")),
                    tag=tag,
                    rm=True,
                    forcerm=True,
                    timeout=timeout,
                    pull=False,
                )
            except Exception as err:
                raise ImageBuildError(f"Failed to build image '{tag}': {err}") from err
        logger.info("Built image %s", tag)
        return tag

    @contextmanager
    def _suppressed_registry_auth(self) -> Generator[None, None, None]:
        """Stop docker-py invoking every configured credential helper on build.

        docker-py attaches auth for *all* registries in the user's docker config
        to a build request, so one unauthenticated helper (a stale gcloud or ECR
        login) fails an entirely local build. Task and verifier images come from
        public registries, so building without those headers is both safe and
        markedly more robust.
        """
        api: Any = getattr(self.client, "api", None)
        original = getattr(api, "_auth_configs", None) if api is not None else None
        if api is None or original is None:
            yield
            return
        try:
            from docker import auth as docker_auth

            # NOT AuthConfig({}): docker-py reloads the on-disk config whenever
            # the in-memory one looks empty, which re-invokes the helpers. A
            # single inert entry keeps it non-empty and helper-free.
            api._auth_configs = docker_auth.AuthConfig(
                {"auths": {"superstate-eval.invalid": {}}}
            )
        except Exception as err:  # pragma: no cover - defensive
            logger.debug("Could not suppress registry auth: %s", err)
            yield
            return
        try:
            yield
        finally:
            api._auth_configs = original

    def prune_ephemeral_resources(self) -> None:
        """Prune dangling images, stopped containers, and unreferenced volumes."""
        logger.info("Pruning ephemeral docker volumes and dangling images...")
        try:
            self.client.volumes.prune()
            self.client.images.prune(filters={"dangling": True})
        except Exception as e:
            logger.warning(f"Failed to prune ephemeral docker resources: {e}")

    def check_disk_space_or_prune(
        self,
        target_path: Path | str = "/",
        min_free_gb: float = 20.0,
        emergency_halt_gb: float = 10.0,
    ) -> float:
        """Check available disk space. Prune docker if below min_free_gb; raise if below emergency_halt_gb."""
        usage = shutil.disk_usage(target_path)
        free_gb = round(usage.free / (1024**3), 2)
        logger.info(f"Host disk check: {free_gb} GB free on {target_path}")

        if free_gb < emergency_halt_gb:
            # Emergency prune attempt
            try:
                self.client.containers.prune()
                self.client.volumes.prune()
                self.client.images.prune(filters={"dangling": True})
            except Exception:
                pass
            usage_after = shutil.disk_usage(target_path)
            free_gb_after = round(usage_after.free / (1024**3), 2)
            if free_gb_after < emergency_halt_gb:
                raise DiskSpaceError(
                    f"Host disk space critically low: {free_gb_after} GB free (minimum emergency threshold: {emergency_halt_gb} GB)"
                )
            return free_gb_after

        if free_gb < min_free_gb:
            logger.warning(
                f"Free disk space ({free_gb} GB) below safety threshold ({min_free_gb} GB). Running cleanup..."
            )
            try:
                self.client.containers.prune()
                self.client.volumes.prune()
                self.client.images.prune(filters={"dangling": True})
            except Exception as e:
                logger.warning(f"Error during opportunistic docker prune: {e}")

        return free_gb
