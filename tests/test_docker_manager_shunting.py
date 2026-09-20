"""Tests for mounting static Linux superstate binary into sandbox containers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from lab.sandbox.docker_manager import (
    DockerManager,
    find_static_superstate_binary,
)


def test_spawn_sandbox_mounts_static_superstate_when_file_exists(tmp_path: Path) -> None:
    """Verify spawn_sandbox bind-mounts /usr/local/bin/superstate when static binary is present."""
    fake_bin = tmp_path / "superstate-linux-x86_64"
    fake_bin.write_bytes(b"\x7fELFfakebinary")

    mock_docker_client = MagicMock()
    mock_container = MagicMock()
    mock_container.id = "sandbox-container-1234"
    mock_docker_client.containers.run.return_value = mock_container

    with patch(
        "lab.sandbox.docker_manager.find_static_superstate_binary",
        return_value=fake_bin,
    ):
        with patch("lab.sandbox.docker_manager.docker.from_env", return_value=mock_docker_client):
            manager = DockerManager()
            with manager.spawn_sandbox(image="dummy-image", command="sleep 10") as container:
                assert container.id == "sandbox-container-1234"

            call_kwargs = mock_docker_client.containers.run.call_args.kwargs
            volumes = call_kwargs.get("volumes", {})
            resolved_fake_path = str(fake_bin.resolve())
            assert resolved_fake_path in volumes
            assert volumes[resolved_fake_path] == {
                "bind": "/usr/local/bin/superstate",
                "mode": "ro",
            }


def test_spawn_sandbox_omits_mount_when_binary_absent() -> None:
    """Verify spawn_sandbox does not add mount when static binary is absent."""
    mock_docker_client = MagicMock()
    mock_container = MagicMock()
    mock_container.id = "sandbox-container-5678"
    mock_docker_client.containers.run.return_value = mock_container

    with patch(
        "lab.sandbox.docker_manager.find_static_superstate_binary",
        return_value=None,
    ):
        with patch("lab.sandbox.docker_manager.docker.from_env", return_value=mock_docker_client):
            manager = DockerManager()
            with manager.spawn_sandbox(image="dummy-image", command="sleep 10") as container:
                assert container.id == "sandbox-container-5678"

            call_kwargs = mock_docker_client.containers.run.call_args.kwargs
            volumes = call_kwargs.get("volumes", {})
            for _host_path, mount_cfg in volumes.items():
                assert mount_cfg.get("bind") != "/usr/local/bin/superstate"


def test_find_static_superstate_binary_env_var(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify find_static_superstate_binary respects SUPERSTATE_LINUX_BIN when file exists."""
    fake_bin = tmp_path / "custom-superstate-bin"
    fake_bin.write_bytes(b"\x7fELFcustombinary")

    monkeypatch.setenv("SUPERSTATE_LINUX_BIN", str(fake_bin))
    assert find_static_superstate_binary() == fake_bin


def test_find_static_superstate_binary_env_var_nonexistent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify find_static_superstate_binary falls back when SUPERSTATE_LINUX_BIN does not exist."""
    nonexistent = tmp_path / "does-not-exist"
    monkeypatch.setenv("SUPERSTATE_LINUX_BIN", str(nonexistent))

    # Mock candidate checks to return False so we verify fallback returns None
    with patch.object(Path, "is_file", return_value=False):
        assert find_static_superstate_binary() is None


def test_find_static_superstate_binary_none_when_no_candidates_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify find_static_superstate_binary returns None when no binaries exist."""
    monkeypatch.delenv("SUPERSTATE_LINUX_BIN", raising=False)
    with patch.object(Path, "is_file", return_value=False):
        assert find_static_superstate_binary() is None
