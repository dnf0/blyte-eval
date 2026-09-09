"""Tests for end-to-end Pilot Showdown Runner."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.pilot import PilotShowdownRunner


def test_pilot_showdown_runner_executes_all_three_arms(tmp_path: Path) -> None:
    mock_docker = MagicMock()
    mock_container = MagicMock()
    mock_container.id = "cnt-12345"
    mock_docker.create_container.return_value = mock_container

    task = TaskSpec(
        id="datacurve/sample-task",
        name="sample-task",
        instruction="Fix the bug in main.py.",
        docker_image="dummy:latest",
        task_dir=tmp_path,
        base_commit="abc1234",
    )

    runner = PilotShowdownRunner(docker_manager=mock_docker, logs_root=tmp_path / "logs")
    summary = runner.run_pilot(
        task=task, arms=["vanilla", "superpowers", "superstate"], mock_mode=True
    )

    assert summary["task_id"] == "datacurve/sample-task"
    assert len(summary["results"]) == 3

    arm_names = [r["arm"] for r in summary["results"]]
    assert "vanilla" in arm_names
    assert "superpowers" in arm_names
    assert "superstate" in arm_names

    for r in summary["results"]:
        assert r["success"] is True
        assert r["turns"] >= 1
        assert "patch_path" in r
        assert "reward" in r
