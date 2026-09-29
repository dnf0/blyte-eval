"""Tests for mounting static Linux blyte binary into sandbox containers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from lab.sandbox.docker_manager import (
    DockerManager,
    find_static_blyte_binary,
)


def test_spawn_sandbox_mounts_static_blyte_when_file_exists(tmp_path: Path) -> None:
    """Verify spawn_sandbox bind-mounts /usr/local/bin/blyte when static binary is present."""
    fake_bin = tmp_path / "blyte-linux-x86_64"
    fake_bin.write_bytes(b"\x7fELFfakebinary")

    mock_docker_client = MagicMock()
    mock_container = MagicMock()
    mock_container.id = "sandbox-container-1234"
    mock_docker_client.containers.run.return_value = mock_container

    with patch(
        "lab.sandbox.docker_manager.find_static_blyte_binary",
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
                "bind": "/usr/local/bin/blyte",
                "mode": "ro",
            }


def test_spawn_sandbox_omits_mount_when_binary_absent() -> None:
    """Verify spawn_sandbox does not add mount when static binary is absent."""
    mock_docker_client = MagicMock()
    mock_container = MagicMock()
    mock_container.id = "sandbox-container-5678"
    mock_docker_client.containers.run.return_value = mock_container

    with patch(
        "lab.sandbox.docker_manager.find_static_blyte_binary",
        return_value=None,
    ):
        with patch("lab.sandbox.docker_manager.docker.from_env", return_value=mock_docker_client):
            manager = DockerManager()
            with manager.spawn_sandbox(image="dummy-image", command="sleep 10") as container:
                assert container.id == "sandbox-container-5678"

            call_kwargs = mock_docker_client.containers.run.call_args.kwargs
            volumes = call_kwargs.get("volumes", {})
            assert not any(
                isinstance(mount_cfg, dict) and mount_cfg.get("bind") == "/usr/local/bin/blyte"
                for mount_cfg in volumes.values()
            )


def test_spawn_sandbox_does_not_duplicate_existing_blyte_mount(tmp_path: Path) -> None:
    """Verify spawn_sandbox does not override or duplicate an existing blyte mount."""
    fake_bin = tmp_path / "blyte-linux-x86_64"
    fake_bin.write_bytes(b"\x7fELFfakebinary")
    custom_bin = tmp_path / "custom-binary"
    custom_bin.write_bytes(b"\x7fELFcustom")

    mock_docker_client = MagicMock()
    mock_container = MagicMock()
    mock_docker_client.containers.run.return_value = mock_container

    with patch(
        "lab.sandbox.docker_manager.find_static_blyte_binary",
        return_value=fake_bin,
    ):
        with patch("lab.sandbox.docker_manager.docker.from_env", return_value=mock_docker_client):
            manager = DockerManager()
            existing_volumes = {
                str(custom_bin): {"bind": "/usr/local/bin/blyte", "mode": "rw"}
            }
            with manager.spawn_sandbox(
                image="dummy-image", command="sleep 10", volumes=existing_volumes
            ):
                pass

            call_kwargs = mock_docker_client.containers.run.call_args.kwargs
            volumes = call_kwargs.get("volumes", {})
            # Ensure custom_bin is present and fake_bin was NOT added as a duplicate
            assert str(custom_bin) in volumes
            assert str(fake_bin.resolve()) not in volumes


def test_find_static_blyte_binary_env_var(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify find_static_blyte_binary respects BLYTE_LINUX_BIN when file exists."""
    fake_bin = tmp_path / "custom-blyte-bin"
    fake_bin.write_bytes(b"\x7fELFcustombinary")

    monkeypatch.setenv("BLYTE_LINUX_BIN", str(fake_bin))
    assert find_static_blyte_binary() == fake_bin


def test_find_static_blyte_binary_env_var_nonexistent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify find_static_blyte_binary falls back when BLYTE_LINUX_BIN does not exist."""
    nonexistent = tmp_path / "does-not-exist"
    monkeypatch.setenv("BLYTE_LINUX_BIN", str(nonexistent))

    # Mock candidate checks to return False so we verify fallback returns None
    with patch.object(Path, "is_file", return_value=False):
        assert find_static_blyte_binary() is None


def test_find_static_blyte_binary_none_when_no_candidates_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify find_static_blyte_binary returns None when no binaries exist."""
    monkeypatch.delenv("BLYTE_LINUX_BIN", raising=False)
    with patch.object(Path, "is_file", return_value=False):
        assert find_static_blyte_binary() is None
