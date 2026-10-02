"""Tests for ensuring docker images are present before container creation or running."""

from __future__ import annotations

import io
import logging
from pathlib import Path
import tarfile
from unittest.mock import MagicMock
import docker.errors
import pytest

from lab.sandbox.docker_manager import DockerManager, WorkspaceSeedError


def _create_mock_archive() -> bytes:
    tar_bio = io.BytesIO()
    with tarfile.open(fileobj=tar_bio, mode="w") as tar:
        data = b"print('hello world')\n"
        ti = tarfile.TarInfo(name="app/main.py")
        ti.size = len(data)
        tar.addfile(ti, io.BytesIO(data))
    return tar_bio.getvalue()


def test_missing_image_pulled_once_and_seeding_proceeds(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A missing image is pulled once and seeding proceeds."""
    mock_docker_client = MagicMock()
    mock_docker_client.images.get.side_effect = docker.errors.ImageNotFound(
        "Image does not exist locally"
    )

    mock_container = MagicMock()
    mock_container.get_archive.return_value = ([_create_mock_archive()], {})
    mock_docker_client.containers.create.return_value = mock_container

    image_ref = "public.ecr.aws/d3j8x8q7/swe-bench-202605:20261001"
    manager = DockerManager(client=mock_docker_client)
    dest_dir = tmp_path / "workspace"

    with caplog.at_level(logging.INFO):
        extracted = manager.seed_workspace_from_image(image=image_ref, dest=dest_dir)

    mock_docker_client.images.pull.assert_called_once_with(
        "public.ecr.aws/d3j8x8q7/swe-bench-202605", tag="20261001"
    )
    assert f"pulling missing image {image_ref}" in caplog.text
    assert extracted == 1
    assert (dest_dir / "main.py").read_text() == "print('hello world')\n"
    mock_docker_client.containers.create.assert_called_once()


def test_present_image_not_pulled(tmp_path: Path) -> None:
    """An image that is present is not pulled again (no network call)."""
    mock_docker_client = MagicMock()
    mock_img = MagicMock()
    mock_docker_client.images.get.return_value = mock_img

    mock_container = MagicMock()
    mock_container.get_archive.return_value = ([_create_mock_archive()], {})
    mock_docker_client.containers.create.return_value = mock_container

    image_ref = "ubuntu:22.04"
    manager = DockerManager(client=mock_docker_client)

    # 1. Calling ensure_image directly does not pull
    manager.ensure_image(image_ref)
    mock_docker_client.images.pull.assert_not_called()

    # 2. Seeding from a present image does not pull
    dest_dir = tmp_path / "workspace"
    extracted = manager.seed_workspace_from_image(image=image_ref, dest=dest_dir)
    mock_docker_client.images.pull.assert_not_called()
    assert extracted == 1


def test_failed_pull_raises_workspace_seed_error_naming_image(tmp_path: Path) -> None:
    """A failed pull raises WorkspaceSeedError with the pull error in the message naming the image."""
    mock_docker_client = MagicMock()
    mock_docker_client.images.get.side_effect = docker.errors.ImageNotFound("Not found")
    mock_docker_client.images.pull.side_effect = docker.errors.APIError(
        "404 Client Error: repository does not exist or may require 'docker login'"
    )

    image_ref = "private.registry.internal/secret/repo:latest"
    manager = DockerManager(client=mock_docker_client)

    with pytest.raises(WorkspaceSeedError) as exc_info:
        manager.seed_workspace_from_image(image=image_ref, dest=tmp_path / "workspace")

    err_str = str(exc_info.value)
    assert image_ref in err_str
    assert "repository does not exist" in err_str
    mock_docker_client.containers.create.assert_not_called()


def test_ensure_image_splits_registry_host_with_port() -> None:
    """Image references with custom registry hosts and ports are correctly parsed."""
    mock_docker_client = MagicMock()
    mock_docker_client.images.get.side_effect = docker.errors.ImageNotFound("Not found")

    manager = DockerManager(client=mock_docker_client)
    manager.ensure_image("registry.local:5000/my-org/my-app:v1.2.3")

    mock_docker_client.images.pull.assert_called_once_with(
        "registry.local:5000/my-org/my-app", tag="v1.2.3"
    )


def test_ensure_image_without_tag() -> None:
    """Image references without a tag pass tag=None to images.pull."""
    mock_docker_client = MagicMock()
    mock_docker_client.images.get.side_effect = docker.errors.ImageNotFound("Not found")

    manager = DockerManager(client=mock_docker_client)
    manager.ensure_image("alpine")

    mock_docker_client.images.pull.assert_called_once_with("alpine", tag=None)


def test_run_sandbox_pulls_missing_image_before_containers_run() -> None:
    """run_sandbox ensures a missing image is pulled before calling containers.run."""
    mock_docker_client = MagicMock()
    mock_docker_client.images.get.side_effect = docker.errors.ImageNotFound("Not found")

    mock_container = MagicMock()
    mock_container.id = "sandbox-c123456789"
    mock_docker_client.containers.run.return_value = mock_container

    image_ref = "python:3.12-slim"
    manager = DockerManager(client=mock_docker_client)

    with manager.run_sandbox(image=image_ref, command="python --version"):
        mock_docker_client.images.pull.assert_called_once_with("python", tag="3.12-slim")
        mock_docker_client.containers.run.assert_called_once()


def test_run_sandbox_present_image_not_pulled() -> None:
    """run_sandbox does not pull when the image is already present."""
    mock_docker_client = MagicMock()
    mock_docker_client.images.get.return_value = MagicMock()

    mock_container = MagicMock()
    mock_container.id = "sandbox-c123456789"
    mock_docker_client.containers.run.return_value = mock_container

    manager = DockerManager(client=mock_docker_client)

    with manager.run_sandbox(image="python:3.12-slim"):
        mock_docker_client.images.pull.assert_not_called()
        mock_docker_client.containers.run.assert_called_once()


def test_run_sandbox_failed_pull_raises_workspace_seed_error() -> None:
    """A failed pull in run_sandbox raises WorkspaceSeedError and never calls containers.run."""
    mock_docker_client = MagicMock()
    mock_docker_client.images.get.side_effect = docker.errors.ImageNotFound("Not found")
    mock_docker_client.images.pull.side_effect = docker.errors.APIError("Network timeout")

    image_ref = "unreachable.repo/app:tag"
    manager = DockerManager(client=mock_docker_client)

    with pytest.raises(WorkspaceSeedError) as exc_info:
        with manager.run_sandbox(image=image_ref):
            pass

    assert image_ref in str(exc_info.value)
    assert "Network timeout" in str(exc_info.value)
    mock_docker_client.containers.run.assert_not_called()
