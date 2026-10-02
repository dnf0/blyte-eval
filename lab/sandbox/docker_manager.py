"""Docker lifecycle and host disk space management.

Ensures deterministic container removal, volume pruning, and pre-flight
disk space safety checks to prevent host filesystem saturation.
"""

from __future__ import annotations

from contextlib import contextmanager
import datetime
import io
import logging
import os
from pathlib import Path
import shutil
import tarfile
import threading
import time
from typing import Any, Generator, Mapping, Sequence

import docker
import docker.errors
import docker.utils
from docker.models.containers import Container

logger = logging.getLogger("blyte_eval.docker_manager")

OFFLINE_NETWORK = "blyte-eval-offline"


class DiskSpaceError(RuntimeError):
    """Raised when host disk space falls below the critical emergency threshold."""


class WorkspaceSeedError(RuntimeError):
    """Raised when the task repository cannot be materialized onto the host."""


class ImageBuildError(RuntimeError):
    """Raised when an image (typically the held-out verifier) cannot be built."""


def find_static_blyte_binary() -> Path | None:
    """Locate pre-compiled static Linux blyte binary if available on host.

    Checks the BLYTE_LINUX_BIN environment variable first, then standard candidate
    paths within the repository or user cache directory.

    Returns:
        Path to the static Linux blyte binary if found on the host, otherwise None.
    """
    # SUPERSTATE_LINUX_BIN: deprecated pre-rename name, still read when BLYTE_LINUX_BIN is unset.
    env_path = os.environ.get("BLYTE_LINUX_BIN") or os.environ.get("SUPERSTATE_LINUX_BIN")
    # If explicitly configured in environment, verify it points to an existing file
    if env_path:
        p = Path(env_path)
        if p.is_file():
            return p

    # Fall back to known candidate paths relative to repository root and home cache
    repo_root = Path(__file__).resolve().parent.parent.parent
    candidates = [
        repo_root / "bin" / "blyte-linux-x86_64",
        repo_root / "bin" / "blyte-linux",
    ]
    try:
        candidates.append(Path.home() / ".cache" / "blyte" / "blyte-linux-x86_64")
    except RuntimeError:
        pass
    for c in candidates:
        if c.is_file():
            return c
    return None


def format_size(size_bytes: int | float | str | None) -> str:
    """Format byte count into human-readable string (e.g. 4.2 GB)."""
    if size_bytes is None:
        return "unknown size"
    if isinstance(size_bytes, str):
        return size_bytes
    try:
        val = float(size_bytes)
    except (ValueError, TypeError):
        return str(size_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(val) < 1024.0 or unit == "TB":
            if unit == "B":
                return f"{int(val)} B"
            return f"{val:.1f} {unit}"
        val /= 1024.0
    return f"{val:.1f} GB"


def _parse_created_time(val: Any) -> datetime.datetime | None:
    """Parse container creation time from ISO-8601 string or numeric timestamp."""
    if isinstance(val, (int, float)):
        return datetime.datetime.fromtimestamp(val, tz=datetime.timezone.utc)
    if isinstance(val, str):
        s = val.rstrip("Z")
        tz_offset = "+00:00" if val.endswith("Z") else ""
        if "." in s:
            main_part, frac = s.split(".", 1)
            for sep in ("+", "-"):
                if sep in frac:
                    frac, tz = frac.split(sep, 1)
                    tz_offset = sep + tz
                    break
            s = f"{main_part}.{frac[:6]}{tz_offset}"
        elif tz_offset:
            s = f"{s}{tz_offset}"
        try:
            dt = datetime.datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt
        except Exception:
            return None
    return None


class DockerManager:
    """Manages Docker containers and host disk resource reclamation."""

    def __init__(
        self,
        client: docker.DockerClient | None = None,
        run_stamp: str | None = None,
    ) -> None:
        self._client = client
        self.run_stamp = run_stamp or time.strftime("%Y%m%d-%H%M%S")

    @property
    def client(self) -> docker.DockerClient:
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    def ensure_offline_network(self) -> str:
        """Ensure the offline internal network exists and return its name."""
        if not self.client.networks.list(names=[OFFLINE_NETWORK]):
            self.client.networks.create(OFFLINE_NETWORK, driver="bridge", internal=True)
        return OFFLINE_NETWORK

    def connect_for_grading(self, container: Any) -> None:
        """Connect container to the default bridge network for grading."""
        self.client.networks.get("bridge").connect(container)

    def ensure_image(self, image: str) -> None:
        """Ensure the specified image is locally available, pulling it if missing."""
        try:
            self.client.images.get(image)
            return
        except docker.errors.ImageNotFound:
            pass

        logger.info(f"pulling missing image {image}")
        try:
            repository, tag = docker.utils.parse_repository_tag(image)
            self.client.images.pull(repository, tag=tag)
        except Exception as err:
            raise WorkspaceSeedError(
                f"Cannot seed workspace: image '{image}' is unavailable ({err}). "
                "Pull or build the task image before running the evaluation."
            ) from err

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
        network: str | None = None,
        labels: Mapping[str, str] | None = None,
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

        # Mount pre-compiled static Linux blyte binary into container when available
        has_blyte_mount = any(
            isinstance(cfg, Mapping) and cfg.get("bind") == "/usr/local/bin/blyte"
            for cfg in combined_volumes.values()
        )
        static_bin = find_static_blyte_binary()
        if static_bin is not None and not has_blyte_mount:
            combined_volumes[str(static_bin.resolve())] = {
                "bind": "/usr/local/bin/blyte",
                "mode": "ro",
            }

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
        if network is not None:
            run_kwargs["network"] = network
        if nano_cpus is not None:
            run_kwargs["nano_cpus"] = nano_cpus
        if mem_limit is not None:
            run_kwargs["mem_limit"] = mem_limit
        if container_name is not None:
            run_kwargs["name"] = container_name
        combined_labels = {"blyte-eval.run": self.run_stamp}
        if labels is not None:
            combined_labels.update(labels)
        run_kwargs["labels"] = combined_labels

        self.ensure_image(image)
        container = self.client.containers.run(**run_kwargs)
        logger.info(f"Spawned sandbox container: {container.id[:12]} ({image})")
        # On a Linux host the bind-mounted repository is owned by the host user while the container
        # runs as root, and git refuses to work in it ("dubious ownership"); Docker Desktop hides
        # this on macOS. Patch collection and the held-out grader both run git in /app. Found by CI.
        try:
            container.exec_run(["git", "config", "--global", "--add", "safe.directory", "*"])
        except Exception as e:
            logger.warning(f"Could not mark /app safe for git in {container.id[:12]}: {e}")
        try:
            yield container
        finally:
            logger.info(f"Tearing down sandbox container: {container.id[:12]}")
            try:
                container.remove(force=True)
            except Exception as e:
                logger.warning(f"Error removing container {container.id[:12]}: {e}")

    # Convenience alias for run_sandbox
    spawn_sandbox = run_sandbox

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

        self.ensure_image(image)

        try:
            container = self.client.containers.create(
                image=image,
                command="true",
                labels={"blyte-eval.run": self.run_stamp},
            )
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
            logger.info(
                "Image '%s' has an empty '%s' directory; workspace initialized empty at %s",
                image,
                source_path,
                dest_path,
            )
        else:
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
                {"auths": {"blyte-eval.invalid": {}}}
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

    def remove_image(self, image: str, force: bool = False) -> None:
        """Remove an image by tag or ID."""
        self.client.images.remove(image=image, force=force)

    def get_image_ids(self) -> set[str]:
        """Record the set of image IDs already present on host (`docker images -q`)."""
        ids: set[str] = set()
        for img in self.client.images.list():
            img_id = getattr(img, "id", None)
            if img_id and isinstance(img_id, str):
                ids.add(img_id)
        return ids

    def is_image_in_use(self, image_id: str, image_obj: Any = None) -> bool:
        """Check if any container (running or stopped) uses `image_id`."""
        try:
            containers = self.client.containers.list(all=True)
        except Exception as err:
            logger.warning("Could not list containers to check image usage: %s", err)
            return True

        target_id = getattr(image_obj, "id", None) or image_id
        if not target_id:
            return False

        for c in containers:
            attrs = getattr(c, "attrs", None)
            if isinstance(attrs, Mapping) and attrs.get("Image") == target_id:
                return True

        return False

    def warn_old_containers(
        self,
        max_age_hours: float = 24.0,
        now: datetime.datetime | None = None,
    ) -> list[Any]:
        """Warn about containers carrying blyte-eval.run label created > max_age_hours ago."""
        try:
            containers = self.client.containers.list(
                all=True, filters={"label": "blyte-eval.run"}
            )
        except Exception as err:
            logger.warning("Could not list containers to check for old runs: %s", err)
            return []

        current_time = now or datetime.datetime.now(datetime.timezone.utc)
        old_containers: list[tuple[Any, str]] = []

        for c in containers:
            labels = getattr(c, "labels", None)
            if labels is None and hasattr(c, "attrs") and isinstance(c.attrs, dict):
                labels = c.attrs.get("Config", {}).get("Labels") or c.attrs.get("Labels")
            if labels is not None and "blyte-eval.run" not in labels:
                continue

            created_val = None
            if hasattr(c, "attrs") and isinstance(c.attrs, dict):
                created_val = c.attrs.get("Created")
            if created_val is None:
                created_val = getattr(c, "created", None)

            created_dt = _parse_created_time(created_val)
            if created_dt is None:
                continue

            age_seconds = (current_time - created_dt).total_seconds()
            if age_seconds > max_age_hours * 3600:
                hours = age_seconds / 3600
                if hours >= 48:
                    age_str = f"{hours / 24:.1f}d"
                else:
                    age_str = f"{hours:.1f}h"
                old_containers.append((c, age_str))

        if old_containers:
            ids = [
                getattr(c, "short_id", getattr(c, "id", str(c)))[:12]
                for c, _ in old_containers
            ]
            descriptions = []
            for c, age_str in old_containers:
                c_id = getattr(c, "short_id", getattr(c, "id", str(c)))[:12]
                c_name = getattr(c, "name", "unknown")
                descriptions.append(f"{c_name} (id={c_id}, age={age_str})")

            logger.warning(
                "Found %d orphaned container(s) from past runs (>%.0fh old): %s. "
                "Remove them with: docker rm -f %s",
                len(old_containers),
                max_age_hours,
                ", ".join(descriptions),
                " ".join(ids),
            )

        return [c for c, _ in old_containers]


class ImageTracker:
    """Tracks unfinished jobs per image and removes images after their last job."""

    def __init__(
        self,
        docker_manager: DockerManager,
        keep_images: bool = False,
    ) -> None:
        self.docker_manager = docker_manager
        self.keep_images = keep_images
        self._initial_image_ids: set[str] = set()
        self._initial_listing_succeeded: bool = False
        self._job_counts: dict[str, int] = {}
        self._lock = threading.Lock()

    def record_initial_images(self) -> None:
        """Record image IDs present before the run started."""
        with self._lock:
            try:
                self._initial_image_ids = self.docker_manager.get_image_ids()
                self._initial_listing_succeeded = True
            except Exception:
                self._initial_listing_succeeded = False
                logger.warning("image cleanup disabled: could not list images")

    def register_job(self, image: str | None) -> None:
        """Register a job that will use `image`."""
        if not image:
            return
        with self._lock:
            self._job_counts[image] = self._job_counts.get(image, 0) + 1

    def register_jobs(self, jobs: Sequence[tuple[Any, ...]]) -> None:
        """Register images for a sequence of jobs (each job being a tuple with task as first element)."""
        for job in jobs:
            self.register_job(job[0].docker_image)

    def job_finished(self, image: str | None) -> bool:
        """Notify that a job using `image` has finished.

        If remaining count reaches 0, remove image if not present at start
        and no container uses it.
        Returns True if image was removed, False otherwise.
        """
        if not image or self.keep_images or not self._initial_listing_succeeded:
            return False

        with self._lock:
            if image not in self._job_counts:
                return False
            self._job_counts[image] -= 1
            remaining = self._job_counts[image]
            if remaining > 0:
                return False
            del self._job_counts[image]

        return self._maybe_remove_image(image)

    def _is_image_present_at_start(self, image_id: str | None) -> bool:
        if not self._initial_listing_succeeded:
            return True
        if not image_id or not self._initial_image_ids:
            return False
        return image_id in self._initial_image_ids

    def _maybe_remove_image(self, image: str) -> bool:
        """Check prerequisites and remove image if eligible."""
        try:
            img = self.docker_manager.client.images.get(image)
        except Exception as err:
            logger.debug("Could not inspect image %s for cleanup: %s", image, err)
            return False

        img_id = getattr(img, "id", None)
        if not img_id or not isinstance(img_id, str):
            return False

        if self._is_image_present_at_start(img_id):
            logger.debug("Image %s was present before run; keeping it", image)
            return False

        if self.docker_manager.is_image_in_use(img_id):
            logger.info("Image %s is still used by a container; keeping it", image)
            return False

        size_bytes = None
        if hasattr(img, "attrs") and isinstance(img.attrs, dict):
            size_bytes = img.attrs.get("Size")
        size_str = format_size(size_bytes)

        try:
            if hasattr(self.docker_manager, "remove_image") and isinstance(
                self.docker_manager, DockerManager
            ):
                self.docker_manager.remove_image(image)
            else:
                self.docker_manager.client.images.remove(image=image)
            logger.info("removed image %s (%s) after its last job", image, size_str)
            return True
        except Exception as err:
            logger.warning("Could not remove image %s: %s", image, err)
            return False
