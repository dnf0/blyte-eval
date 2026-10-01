"""Tests for image cleanup and container labeling during evaluation runs."""

from __future__ import annotations

import datetime
import logging
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from lab.sandbox.docker_manager import DockerManager, ImageTracker
from scripts.paired_run import build_parser


def test_image_present_before_run_never_removed() -> None:
    """An image present before the run is never removed."""
    mock_docker_client = MagicMock()
    preexisting_img = MagicMock()
    preexisting_img.id = "sha256:preexisting1234567890abcdef"
    preexisting_img.short_id = "sha256:preexisting"
    preexisting_img.tags = ["preexisting:latest"]
    preexisting_img.attrs = {"Size": 4 * 1024 * 1024 * 1024}

    # At start of run, this image exists
    mock_docker_client.images.list.return_value = [preexisting_img]
    mock_docker_client.images.get.return_value = preexisting_img
    mock_docker_client.containers.list.return_value = []

    manager = DockerManager(client=mock_docker_client)
    tracker = ImageTracker(docker_manager=manager)
    tracker.record_initial_images()

    # Register and complete job using this image
    tracker.register_job("preexisting:latest")
    removed = tracker.job_finished("preexisting:latest")

    assert not removed
    mock_docker_client.images.remove.assert_not_called()


def test_two_jobs_sharing_image_removed_only_after_second_finishes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """With two jobs sharing an image, it is removed only after the second finishes."""
    mock_docker_client = MagicMock()
    # Image was not present before the run
    mock_docker_client.images.list.return_value = []

    shared_img = MagicMock()
    shared_img.id = "sha256:shared1234567890abcdef"
    shared_img.short_id = "sha256:shared123"
    shared_img.tags = ["shared-image:v1"]
    shared_img.attrs = {"Size": int(4.2 * 1024 * 1024 * 1024)}
    mock_docker_client.images.get.return_value = shared_img
    mock_docker_client.containers.list.return_value = []

    manager = DockerManager(client=mock_docker_client)
    tracker = ImageTracker(docker_manager=manager)
    tracker.record_initial_images()

    tracker.register_job("shared-image:v1")
    tracker.register_job("shared-image:v1")

    # First job finishes -> remaining count is 1 -> image is NOT removed
    first_removed = tracker.job_finished("shared-image:v1")
    assert not first_removed
    mock_docker_client.images.remove.assert_not_called()

    # Second job finishes -> remaining count is 0 -> image IS removed
    with caplog.at_level(logging.INFO):
        second_removed = tracker.job_finished("shared-image:v1")
    assert second_removed
    mock_docker_client.images.remove.assert_called_once_with(image="shared-image:v1", force=False)
    assert "removed image shared-image:v1 (4.2 GB) after its last job" in caplog.text


def test_image_still_used_by_container_is_kept() -> None:
    """An image still used by a container (running or stopped) is kept."""
    mock_docker_client = MagicMock()
    mock_docker_client.images.list.return_value = []

    target_img = MagicMock()
    target_img.id = "sha256:inuse1234567890abcdef"
    target_img.short_id = "sha256:inuse123"
    target_img.tags = ["in-use:v1"]
    target_img.attrs = {"Size": 1024 * 1024 * 1024}
    mock_docker_client.images.get.return_value = target_img

    # A container is still using this image
    container = MagicMock()
    container.image = MagicMock()
    container.image.id = "sha256:inuse1234567890abcdef"
    container.image.tags = ["in-use:v1"]
    container.attrs = {"Image": "sha256:inuse1234567890abcdef", "Config": {"Image": "in-use:v1"}}
    mock_docker_client.containers.list.return_value = [container]

    manager = DockerManager(client=mock_docker_client)
    tracker = ImageTracker(docker_manager=manager)
    tracker.record_initial_images()

    tracker.register_job("in-use:v1")
    removed = tracker.job_finished("in-use:v1")

    assert not removed
    mock_docker_client.images.remove.assert_not_called()


def test_keep_images_removes_nothing() -> None:
    """--keep-images removes nothing."""
    mock_docker_client = MagicMock()
    mock_docker_client.images.list.return_value = []

    new_img = MagicMock()
    new_img.id = "sha256:newimage123"
    new_img.short_id = "sha256:new"
    new_img.tags = ["keep-me:latest"]
    new_img.attrs = {"Size": 1024 * 1024}
    mock_docker_client.images.get.return_value = new_img
    mock_docker_client.containers.list.return_value = []

    manager = DockerManager(client=mock_docker_client)
    tracker = ImageTracker(docker_manager=manager, keep_images=True)
    tracker.record_initial_images()

    tracker.register_job("keep-me:latest")
    removed = tracker.job_finished("keep-me:latest")

    assert not removed
    mock_docker_client.images.remove.assert_not_called()

    # CLI flag test
    parser = build_parser()
    args_default = parser.parse_args([])
    assert not args_default.keep_images
    args_keep = parser.parse_args(["--keep-images"])
    assert args_keep.keep_images


def test_spawned_containers_carry_label(tmp_path: Path) -> None:
    """Every container the docker manager spawns gets the label blyte-eval.run=<run stamp>."""
    mock_docker_client = MagicMock()
    mock_container = MagicMock()
    mock_container.id = "sandbox-c12345678901"
    mock_docker_client.containers.run.return_value = mock_container
    mock_docker_client.containers.create.return_value = mock_container

    run_stamp = "test-run-20261001-120000"
    manager = DockerManager(client=mock_docker_client, run_stamp=run_stamp)

    # 1. run_sandbox
    with manager.run_sandbox(image="ubuntu:latest", command="sleep 1"):
        pass

    mock_docker_client.containers.run.assert_called_once()
    run_kwargs = mock_docker_client.containers.run.call_args.kwargs
    assert "labels" in run_kwargs
    assert run_kwargs["labels"].get("blyte-eval.run") == run_stamp

    # 2. seed_workspace_from_image
    import io
    import tarfile

    tar_bio = io.BytesIO()
    with tarfile.open(fileobj=tar_bio, mode="w"):
        pass
    mock_container.get_archive.return_value = ([tar_bio.getvalue()], {})
    manager.seed_workspace_from_image(image="ubuntu:latest", dest=tmp_path / "dest")
    mock_docker_client.containers.create.assert_called_once()
    create_kwargs = mock_docker_client.containers.create.call_args.kwargs
    assert "labels" in create_kwargs
    assert create_kwargs["labels"].get("blyte-eval.run") == run_stamp


def test_old_labelled_container_produces_warning(caplog: pytest.LogCaptureFixture) -> None:
    """An old labelled container (>24h old) produces a warning with its age and removal command."""
    mock_docker_client = MagicMock()

    now = datetime.datetime.fromisoformat("2026-10-01T12:00:00+00:00")
    # Old container: created 30 hours ago
    created_old = (now - datetime.timedelta(hours=30)).isoformat()
    old_container = MagicMock()
    old_container.id = "c_old_111122223333"
    old_container.short_id = "c_old_111122"
    old_container.name = "orphaned-worker-1"
    old_container.labels = {"blyte-eval.run": "20260930-060000"}
    old_container.attrs = {
        "Created": created_old,
        "Config": {"Labels": {"blyte-eval.run": "20260930-060000"}},
    }

    # Recent container: created 2 hours ago
    created_recent = (now - datetime.timedelta(hours=2)).isoformat()
    recent_container = MagicMock()
    recent_container.id = "c_recent_444455556666"
    recent_container.short_id = "c_recent_4444"
    recent_container.name = "active-worker-2"
    recent_container.labels = {"blyte-eval.run": "20261001-100000"}
    recent_container.attrs = {
        "Created": created_recent,
        "Config": {"Labels": {"blyte-eval.run": "20261001-100000"}},
    }

    mock_docker_client.containers.list.return_value = [old_container, recent_container]

    manager = DockerManager(client=mock_docker_client)
    with caplog.at_level(logging.WARNING):
        flagged = manager.warn_old_containers(max_age_hours=24.0, now=now)

    assert len(flagged) == 1
    assert flagged[0] == old_container

    # Warning must name the container, its age, and the removal command: docker rm -f <ids>
    warning_text = caplog.text
    assert "orphaned-worker-1" in warning_text
    assert "30.0h" in warning_text
    assert "docker rm -f c_old_111122" in warning_text

    # Containers must NOT be removed automatically
    old_container.remove.assert_not_called()
    mock_docker_client.containers.remove.assert_not_called()


def test_removal_failure_logged_as_warning_never_fails_run(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Image removal failure is logged as a warning and never raises."""
    mock_docker_client = MagicMock()
    mock_docker_client.images.list.return_value = []

    err_img = MagicMock()
    err_img.id = "sha256:err123"
    err_img.short_id = "sha256:err"
    err_img.tags = ["err-image:latest"]
    err_img.attrs = {"Size": 1024}
    mock_docker_client.images.get.return_value = err_img
    mock_docker_client.containers.list.return_value = []
    mock_docker_client.images.remove.side_effect = RuntimeError("Docker daemon connection failed")

    manager = DockerManager(client=mock_docker_client)
    tracker = ImageTracker(docker_manager=manager)
    tracker.record_initial_images()
    tracker.register_job("err-image:latest")

    with caplog.at_level(logging.WARNING):
        # Must not raise
        result = tracker.job_finished("err-image:latest")

    assert not result
    assert "Could not remove image err-image:latest" in caplog.text


def test_paired_run_cleans_images_and_warns_old_containers(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """paired_run _run records initial images, warns old containers, and cleans task images."""
    from unittest.mock import patch
    from scripts.paired_run import _run, build_parser

    mock_docker_client = MagicMock()
    # Initial image present before run
    initial_img = MagicMock()
    initial_img.id = "sha256:preexisting"
    initial_img.short_id = "preexisting"
    initial_img.tags = ["preexisting:latest"]
    initial_img.attrs = {"Size": 1000}

    # Task image brought in during run
    task_img = MagicMock()
    task_img.id = "sha256:taskimg123"
    task_img.short_id = "taskimg123"
    task_img.tags = ["task-image:v1"]
    task_img.attrs = {"Size": 4 * 1024 * 1024 * 1024}

    # At start of run, only initial_img is listed
    mock_docker_client.images.list.return_value = [initial_img]
    # When inspected for cleanup, return task_img
    mock_docker_client.images.get.return_value = task_img
    mock_docker_client.containers.list.return_value = []

    # Mock task
    mock_task = MagicMock()
    mock_task.id = "task-1"
    mock_task.name = "task-1"
    mock_task.docker_image = "task-image:v1"
    mock_task.agent_timeout_sec = 60.0
    mock_task.tests_dir = "tests"
    mock_task.memory_mb = 1024

    mock_driver = MagicMock()
    mock_driver.harness_name = "agy"

    mock_telemetry = MagicMock()
    mock_telemetry.passed = True
    mock_telemetry.cost_usd = 0.05
    mock_telemetry.extra = {"turns": 2}
    mock_telemetry.failure_reason = None
    mock_telemetry.to_dict.return_value = {"passed": True}

    parser = build_parser()
    args = parser.parse_args([
        "--tasks", "task-1",
        "--arms", "vanilla",
        "--concurrency", "1",
        "--workspace-root", str(tmp_path / "run_20261001-120000"),
    ])

    with patch("lab.sandbox.docker_manager.docker.from_env", return_value=mock_docker_client), \
         patch("scripts.paired_run.load_task_from_dir", return_value=mock_task), \
         patch("scripts.paired_run.AgyCliDriver", return_value=mock_driver), \
         patch("lab.engine.runner.AblationRunner.run_task", return_value=mock_telemetry):
        with caplog.at_level(logging.INFO):
            exit_code = _run(args)

    assert exit_code == 0
    # Image brought in by the run must be removed after its last job
    mock_docker_client.images.remove.assert_called_once_with(image="task-image:v1", force=False)
    assert "removed image task-image:v1 (4.0 GB) after its last job" in caplog.text


def test_paired_run_keep_images_flag_preserves_images(tmp_path: Path) -> None:
    """paired_run with --keep-images does not remove any images."""
    from unittest.mock import patch
    from scripts.paired_run import _run, build_parser

    mock_docker_client = MagicMock()
    task_img = MagicMock()
    task_img.id = "sha256:taskimg123"
    task_img.tags = ["task-image:v1"]
    task_img.attrs = {"Size": 4 * 1024 * 1024 * 1024}

    mock_docker_client.images.list.return_value = []
    mock_docker_client.images.get.return_value = task_img
    mock_docker_client.containers.list.return_value = []

    mock_task = MagicMock()
    mock_task.id = "task-1"
    mock_task.name = "task-1"
    mock_task.docker_image = "task-image:v1"
    mock_task.agent_timeout_sec = 60.0
    mock_task.tests_dir = "tests"
    mock_task.memory_mb = 1024

    mock_driver = MagicMock()
    mock_driver.harness_name = "agy"

    mock_telemetry = MagicMock()
    mock_telemetry.passed = True
    mock_telemetry.cost_usd = 0.05
    mock_telemetry.extra = {"turns": 2}
    mock_telemetry.failure_reason = None
    mock_telemetry.to_dict.return_value = {"passed": True}

    parser = build_parser()
    args = parser.parse_args([
        "--tasks", "task-1",
        "--arms", "vanilla",
        "--keep-images",
        "--concurrency", "1",
        "--workspace-root", str(tmp_path / "run_20261001-120000"),
    ])

    with patch("lab.sandbox.docker_manager.docker.from_env", return_value=mock_docker_client), \
         patch("scripts.paired_run.load_task_from_dir", return_value=mock_task), \
         patch("scripts.paired_run.AgyCliDriver", return_value=mock_driver), \
         patch("lab.engine.runner.AblationRunner.run_task", return_value=mock_telemetry):
        exit_code = _run(args)

    assert exit_code == 0
    # Image must NOT be removed
    mock_docker_client.images.remove.assert_not_called()

