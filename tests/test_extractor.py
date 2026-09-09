"""Tests for Blind Extraction and Verification Pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from lab.engine.extractor import extract_and_grade


class MockTask:
    def __init__(self, task_id: str, verification_cmd: str, base_commit: str = "HEAD~1") -> None:
        self.task_id = task_id
        self.verification_cmd = verification_cmd
        self.base_commit = base_commit


def test_extract_and_grade_passing_reward_json(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    verifier_dir = logs_dir / "verifier"
    verifier_dir.mkdir(parents=True)
    reward_file = verifier_dir / "reward.json"
    reward_file.write_text(json.dumps({"reward": 1.0}), encoding="utf-8")

    artifacts_dir = logs_dir / "artifacts"
    artifacts_dir.mkdir(parents=True)
    patch_file = artifacts_dir / "model.patch"
    patch_file.write_text("diff --git a/foo b/foo", encoding="utf-8")

    mock_container = MagicMock()
    # exec_run returns (exit_code, output_bytes)
    mock_container.exec_run.return_value = (0, b"All tests passed")

    task = MockTask(task_id="task-1", verification_cmd="pytest tests/")
    result = extract_and_grade(
        container=mock_container,
        task=task,
        arm="superstate",
        logs_dir=logs_dir,
    )

    assert result.passed is True
    assert result.reward == 1.0
    assert result.exit_code == 0
    assert result.patch_path == patch_file
    assert result.failure_reason is None


def test_extract_and_grade_failing_reward_json(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    verifier_dir = logs_dir / "verifier"
    verifier_dir.mkdir(parents=True)
    reward_file = verifier_dir / "reward.json"
    reward_file.write_text(json.dumps({"reward": 0.0}), encoding="utf-8")

    mock_container = MagicMock()
    mock_container.exec_run.return_value = (1, b"AssertionError: failed")

    task = MockTask(task_id="task-1", verification_cmd="pytest tests/")
    result = extract_and_grade(
        container=mock_container,
        task=task,
        arm="vanilla",
        logs_dir=logs_dir,
    )

    assert result.passed is False
    assert result.reward == 0.0
    assert result.exit_code == 1
    assert "Verification failed" in str(result.failure_reason)


def test_extract_and_grade_missing_reward_json_fails(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True)

    mock_container = MagicMock()
    mock_container.exec_run.return_value = (0, b"OK")

    task = MockTask(task_id="task-1", verification_cmd="pytest tests/")
    result = extract_and_grade(
        container=mock_container,
        task=task,
        arm="superpowers",
        logs_dir=logs_dir,
    )

    # Missing reward.json must fail per evaluation specification
    assert result.passed is False
    assert result.reward is None
    assert result.exit_code == 0
    assert "Missing or invalid verifier/reward.json" in str(result.failure_reason)
