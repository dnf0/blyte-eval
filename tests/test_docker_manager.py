"""Tests for Docker Lifecycle and Disk Space Watchdog."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from lab.sandbox.docker_manager import DockerManager, DiskSpaceError


def test_docker_manager_context_teardown_removes_container() -> None:
    mock_docker_client = MagicMock()
    mock_container = MagicMock()
    mock_container.id = "test-container-1234"
    mock_docker_client.containers.run.return_value = mock_container

    with patch("lab.sandbox.docker_manager.docker.from_env", return_value=mock_docker_client):
        manager = DockerManager()
        with manager.run_sandbox(image="ubuntu:latest", command="sleep 10") as container:
            assert container.id == "test-container-1234"
            # In-context, container was run
            mock_docker_client.containers.run.assert_called_once()

        # After context exit, container.remove(force=True) must have been called
        mock_container.remove.assert_called_once_with(force=True)


def test_docker_manager_resource_constraints_and_logs_mount() -> None:
    mock_docker_client = MagicMock()
    mock_container = MagicMock()
    mock_docker_client.containers.run.return_value = mock_container

    with patch("lab.sandbox.docker_manager.docker.from_env", return_value=mock_docker_client):
        manager = DockerManager()
        with manager.run_sandbox(
            image="ubuntu:latest",
            nano_cpus=2500000000,
            mem_limit="4g",
            logs_dir="/tmp/host_logs",
            container_name="eval-test-container",
        ):
            pass

        call_kwargs = mock_docker_client.containers.run.call_args.kwargs
        assert call_kwargs["nano_cpus"] == 2500000000
        assert call_kwargs["mem_limit"] == "4g"
        assert call_kwargs["name"] == "eval-test-container"
        expected_logs_path = str(Path("/tmp/host_logs").resolve())
        assert expected_logs_path in call_kwargs["volumes"]
        assert call_kwargs["volumes"][expected_logs_path]["bind"] == "/logs"


def test_docker_manager_context_teardown_on_exception() -> None:
    mock_docker_client = MagicMock()
    mock_container = MagicMock()
    mock_container.id = "test-container-err"
    mock_docker_client.containers.run.return_value = mock_container

    with patch("lab.sandbox.docker_manager.docker.from_env", return_value=mock_docker_client):
        manager = DockerManager()
        with pytest.raises(RuntimeError, match="Task failure inside container"):
            with manager.run_sandbox(image="ubuntu:latest") as container:
                assert container.id == "test-container-err"
                raise RuntimeError("Task failure inside container")

        # Container is removed even on exception
        mock_container.remove.assert_called_once_with(force=True)


def test_prune_ephemeral_resources() -> None:
    mock_docker_client = MagicMock()
    with patch("lab.sandbox.docker_manager.docker.from_env", return_value=mock_docker_client):
        manager = DockerManager()
        manager.prune_ephemeral_resources()
        mock_docker_client.volumes.prune.assert_called_once()
        mock_docker_client.images.prune.assert_called_once_with(filters={"dangling": True})


def test_check_disk_space_healthy() -> None:
    with patch("shutil.disk_usage") as mock_usage:
        # 50 GB free
        mock_usage.return_value = MagicMock(free=50 * (1024**3))
        manager = DockerManager()
        free_gb = manager.check_disk_space_or_prune(min_free_gb=20.0, emergency_halt_gb=10.0)
        assert free_gb == 50.0


def test_check_disk_space_triggers_prune_when_below_min() -> None:
    mock_docker_client = MagicMock()
    with patch("lab.sandbox.docker_manager.docker.from_env", return_value=mock_docker_client):
        with patch("shutil.disk_usage") as mock_usage:
            # 15 GB free (< 20 GB min, > 10 GB emergency)
            mock_usage.return_value = MagicMock(free=15 * (1024**3))
            manager = DockerManager()
            free_gb = manager.check_disk_space_or_prune(min_free_gb=20.0, emergency_halt_gb=10.0)
            assert free_gb == 15.0
            mock_docker_client.volumes.prune.assert_called_once()
            mock_docker_client.containers.prune.assert_called_once()


def test_check_disk_space_raises_on_emergency_limit() -> None:
    mock_docker_client = MagicMock()
    with patch("lab.sandbox.docker_manager.docker.from_env", return_value=mock_docker_client):
        with patch("shutil.disk_usage") as mock_usage:
            # 5 GB free (< 10 GB emergency limit)
            mock_usage.return_value = MagicMock(free=5 * (1024**3))
            manager = DockerManager()
            with pytest.raises(DiskSpaceError, match="Host disk space critically low"):
                manager.check_disk_space_or_prune(min_free_gb=20.0, emergency_halt_gb=10.0)
