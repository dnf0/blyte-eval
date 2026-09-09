"""Tests for Ablation Runner and Reporter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from lab.engine.budget_policy import RunTelemetry
from lab.engine.reporter import generate_comparison_summary


def test_generate_comparison_summary() -> None:
    telemetry_runs = [
        # Arm 1: Vanilla
        RunTelemetry(
            task_id="task-1",
            arm="vanilla",
            passed=False,
            wall_clock_sec=600.0,
            cost_usd=0.50,
            input_tokens=50000,
            output_tokens=2000,
            total_granted_budget_sec=900.0,
        ),
        RunTelemetry(
            task_id="task-2",
            arm="vanilla",
            passed=True,
            wall_clock_sec=400.0,
            cost_usd=0.35,
            input_tokens=40000,
            output_tokens=1500,
            total_granted_budget_sec=900.0,
        ),
        # Arm 2: Superpowers
        RunTelemetry(
            task_id="task-1",
            arm="superpowers",
            passed=True,
            wall_clock_sec=700.0,
            cost_usd=0.80,
            input_tokens=80000,
            output_tokens=3000,
            total_granted_budget_sec=900.0,
        ),
        RunTelemetry(
            task_id="task-2",
            arm="superpowers",
            passed=True,
            wall_clock_sec=500.0,
            cost_usd=0.60,
            input_tokens=60000,
            output_tokens=2500,
            total_granted_budget_sec=900.0,
        ),
        # Arm 3: Superstate (earned lease extension)
        RunTelemetry(
            task_id="task-1",
            arm="superstate",
            passed=True,
            wall_clock_sec=1400.0,
            cost_usd=1.10,
            input_tokens=110000,
            output_tokens=4000,
            milestones_completed=2,
            lease_extensions_earned_sec=1200.0,
            total_granted_budget_sec=2100.0,
        ),
        RunTelemetry(
            task_id="task-2",
            arm="superstate",
            passed=True,
            wall_clock_sec=650.0,
            cost_usd=0.70,
            input_tokens=70000,
            output_tokens=2800,
            milestones_completed=1,
            lease_extensions_earned_sec=1200.0,
            total_granted_budget_sec=2100.0,
        ),
    ]

    summary = generate_comparison_summary(telemetry_runs)
    assert len(summary) == 3

    # Check vanilla metrics
    vanilla = summary["vanilla"]
    assert vanilla["total_tasks"] == 2
    assert vanilla["passes"] == 1
    assert vanilla["pass_rate_pct"] == 50.0
    assert vanilla["total_cost_usd"] == 0.85

    # Check superpowers metrics
    sp = summary["superpowers"]
    assert sp["total_tasks"] == 2
    assert sp["passes"] == 2
    assert sp["pass_rate_pct"] == 100.0
    assert sp["total_cost_usd"] == 1.40

    # Check superstate metrics
    ss = summary["superstate"]
    assert ss["total_tasks"] == 2
    assert ss["passes"] == 2
    assert ss["pass_rate_pct"] == 100.0
    assert ss["total_cost_usd"] == 1.80
    assert ss["total_lease_extensions_sec"] == 2400.0


def test_ablation_runner_execution_and_cleanup() -> None:
    from lab.engine.runner import AblationRunner

    mock_docker_mgr = MagicMock()
    runner = AblationRunner(docker_manager=mock_docker_mgr)

    def mock_executor(policy):
        policy.record_milestone_progress("M1")
        return {"passed": True, "cost_usd": 0.45, "input_tokens": 12000, "output_tokens": 500}

    telemetry = runner.run_task(
        task_id="mock-task-1",
        arm="superstate",
        image="mock:latest",
        base_budget_sec=900.0,
        lease_extension_sec=1200.0,
        executor_fn=mock_executor,
    )

    assert telemetry.passed is True
    assert telemetry.milestones_completed == 1
    assert telemetry.lease_extensions_earned_sec == 1200.0
    assert telemetry.total_granted_budget_sec == 2100.0
    assert telemetry.cost_usd == 0.45

    # Check that disk check and cleanup were called
    mock_docker_mgr.check_disk_space_or_prune.assert_called_once()
    mock_docker_mgr.prune_ephemeral_resources.assert_called_once()
