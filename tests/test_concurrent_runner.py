"""Tests for Concurrent Execution Runner with Dynamic Concurrency Governor."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from lab.engine.runner import AblationRunner


def test_ablation_runner_universal_lease_extension() -> None:
    # Verify that all arms (vanilla, superpowers, blyte) can grow their budget on progress
    runner = AblationRunner(docker_manager=MagicMock())

    def fake_executor(policy):
        policy.record_milestone_progress("Milestone 1")
        return {"passed": True, "cost_usd": 1.25, "input_tokens": 100, "output_tokens": 50}

    # Arm is vanilla, but earned progress!
    telemetry = runner.run_task(
        task_id="task-v1",
        arm="vanilla",
        image="test:latest",
        base_budget_sec=900.0,
        lease_extension_sec=1200.0,
        executor_fn=fake_executor,
    )

    assert telemetry.passed is True
    assert telemetry.milestones_completed == 1
    assert telemetry.lease_extensions_earned_sec == 1200.0
    assert telemetry.total_granted_budget_sec == 2100.0


def test_run_cohort_concurrency_governor_dispatch() -> None:
    mock_docker = MagicMock()
    mock_governor = MagicMock()
    mock_governor.calculate_max_concurrency.return_value = 3

    runner = AblationRunner(docker_manager=mock_docker, governor=mock_governor)

    def fake_executor(policy):
        return {"passed": True, "cost_usd": 0.5}

    tasks = [
        {"task_id": f"task-{i}", "image": "ubuntu:latest", "base_budget_sec": 900.0}
        for i in range(5)
    ]
    arms = ["vanilla", "superpowers", "blyte"]

    with patch.object(runner, "run_task") as mock_run_task:
        mock_run_task.return_value = MagicMock(passed=True, cost_usd=0.5)
        results = runner.run_cohort(tasks=tasks, arms=arms, executor_fn=fake_executor)

        mock_governor.calculate_max_concurrency.assert_called_once()
        # 5 tasks * 3 arms = 15 runs
        assert mock_run_task.call_count == 15
        assert len(results) == 15
