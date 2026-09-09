"""The verifier image is the held-out answer key; it must not linger on the host."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lab.engine.verifier import HeldOutVerifier, VerifierOutcome


class _Task:
    id = "org/task"
    cpus = None
    memory_mb = None

    def __init__(self, tests_dir: Path) -> None:
        self.tests_dir = tests_dir


def _manager(tmp_path: Path) -> MagicMock:
    manager = MagicMock()
    manager.build_image.side_effect = lambda context_dir, tag, timeout: tag
    container = MagicMock()
    container.exec_run.return_value = (0, b"done")
    manager.run_sandbox.return_value.__enter__.return_value = container
    return manager


def test_verifier_image_tag_is_unique_per_run(tmp_path: Path) -> None:
    # A stable tag means the first task's image is still on disk when a later
    # agent runs, and `docker run <image> cat /tests/test.patch` reads the answers.
    manager = _manager(tmp_path)
    verifier = HeldOutVerifier(docker_manager=manager)
    task = _Task(tmp_path / "tests")

    first = verifier.build(task)
    second = verifier.build(task)

    assert first != second, "a reused tag leaves a cached answer key on the host"
    assert first.startswith("superstate-eval-verifier/")


def test_verifier_image_is_removed_after_grading(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    logs_dir = tmp_path / "logs"
    (logs_dir / "verifier").mkdir(parents=True)
    (logs_dir / "verifier" / "reward.json").write_text('{"reward": 1}', encoding="utf-8")

    verifier = HeldOutVerifier(docker_manager=manager)
    outcome = verifier.run(task=_Task(tmp_path / "tests"), logs_dir=logs_dir)

    assert isinstance(outcome, VerifierOutcome)
    manager.client.images.remove.assert_called_once()
    removed = manager.client.images.remove.call_args.kwargs["image"]
    assert removed == outcome.image_tag


def test_verifier_image_is_removed_even_when_grading_raises(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    manager.run_sandbox.side_effect = RuntimeError("daemon died mid-run")

    verifier = HeldOutVerifier(docker_manager=manager)
    with pytest.raises(RuntimeError):
        verifier.run(task=_Task(tmp_path / "tests"), logs_dir=tmp_path / "logs")

    manager.client.images.remove.assert_called_once()


def test_keep_image_is_opt_in_for_debugging(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    logs_dir = tmp_path / "logs"
    (logs_dir / "verifier").mkdir(parents=True)
    (logs_dir / "verifier" / "reward.json").write_text('{"reward": 0}', encoding="utf-8")

    verifier = HeldOutVerifier(docker_manager=manager, keep_image=True)
    verifier.run(task=_Task(tmp_path / "tests"), logs_dir=logs_dir)

    manager.client.images.remove.assert_not_called()
