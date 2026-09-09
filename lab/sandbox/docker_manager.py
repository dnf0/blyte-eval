"""Docker lifecycle and host disk space management.

Ensures deterministic container removal, volume pruning, and pre-flight
disk space safety checks to prevent host filesystem saturation.
"""

from __future__ import annotations

from contextlib import contextmanager
import logging
from pathlib import Path
import shutil
from typing import Generator, Mapping

import docker
from docker.models.containers import Container

logger = logging.getLogger("superstate_eval.docker_manager")


class DiskSpaceError(RuntimeError):
    """Raised when host disk space falls below the critical emergency threshold."""


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
    ) -> Generator[Container, None, None]:
        """Run a container with guaranteed teardown upon context exit.

        Guarantees that the container is forcefully removed even if the block
        raises an unhandled exception or times out.
        """
        container = self.client.containers.run(
            image=image,
            command=command,
            volumes=volumes or {},
            working_dir=working_dir,
            network_mode=network_mode,
            environment=environment or {},
            detach=True,
            remove=False,  # We manage removal explicitly in the finally block
        )
        logger.info(f"Spawned sandbox container: {container.id[:12]} ({image})")
        try:
            yield container
        finally:
            logger.info(f"Tearing down sandbox container: {container.id[:12]}")
            try:
                container.remove(force=True)
            except Exception as e:
                logger.warning(f"Error removing container {container.id[:12]}: {e}")

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
