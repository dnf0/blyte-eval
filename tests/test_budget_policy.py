"""Tests for Progress-Earned Budget Policy and Telemetry Accounting."""

from __future__ import annotations


from lab.engine.budget_policy import BudgetPolicy, RunTelemetry


def test_budget_policy_initial_allowance() -> None:
    policy = BudgetPolicy(
        base_timeout_sec=900.0,
    )
    assert policy.max_lease_extensions == 5
    assert policy.lease_extension_sec == 1200.0
    assert policy.current_granted_budget_sec == 900.0
    assert policy.milestones_completed == 0
    assert policy.lease_extensions_earned_sec == 0.0


def test_budget_policy_earn_extension_on_progress() -> None:
    policy = BudgetPolicy(
        base_timeout_sec=900.0,
        lease_extension_sec=1200.0,
        max_lease_extensions=3,
    )
    # Milestone 1 completed
    granted = policy.record_milestone_progress("Task 1: Setup")
    assert granted is True
    assert policy.milestones_completed == 1
    assert policy.lease_extensions_earned_sec == 1200.0
    assert policy.current_granted_budget_sec == 2100.0

    # Milestone 2 completed
    granted = policy.record_milestone_progress("Task 2: Implementation")
    assert granted is True
    assert policy.milestones_completed == 2
    assert policy.lease_extensions_earned_sec == 2400.0
    assert policy.current_granted_budget_sec == 3300.0


def test_budget_policy_respects_max_extensions() -> None:
    policy = BudgetPolicy(
        base_timeout_sec=600.0,
        lease_extension_sec=300.0,
        max_lease_extensions=2,
    )
    policy.record_milestone_progress("M1")
    policy.record_milestone_progress("M2")
    assert policy.milestones_completed == 2
    assert policy.current_granted_budget_sec == 1200.0

    # 3rd milestone does not exceed max_lease_extensions
    granted = policy.record_milestone_progress("M3")
    assert granted is False
    assert policy.milestones_completed == 3
    assert policy.current_granted_budget_sec == 1200.0


def test_run_telemetry_serialization() -> None:
    telemetry = RunTelemetry(
        task_id="terminal-bench/chess-best-move",
        arm="superstate",
        passed=True,
        wall_clock_sec=142.5,
        cost_usd=0.34,
        input_tokens=154200,
        output_tokens=3200,
        milestones_completed=3,
        lease_extensions_earned_sec=2400.0,
        total_granted_budget_sec=3300.0,
    )
    data = telemetry.to_dict()
    assert data["task_id"] == "terminal-bench/chess-best-move"
    assert data["arm"] == "superstate"
    assert data["passed"] is True
    assert data["cost_usd"] == 0.34
    assert data["milestones_completed"] == 3
    assert data["total_granted_budget_sec"] == 3300.0
