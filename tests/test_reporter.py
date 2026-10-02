"""Tests for economic reporting, TCO, and solve-rate weighted metrics."""

from __future__ import annotations

from lab.engine.budget_policy import RunTelemetry
from lab.engine.reporter import (
    compute_control_plane_lift,
    generate_comparison_summary,
    render_economic_tco_table,
    render_lift_report,
    render_summary_table,
)


def test_reporter_economic_metrics() -> None:
    runs = [
        # Baseline: Vanilla (1 pass, 1 fail)
        RunTelemetry(
            task_id="t1",
            arm="vanilla",
            passed=True,
            wall_clock_sec=100.0,
            cost_usd=0.20,
            input_tokens=1000,
            output_tokens=100,
            extra={"harness": "agy"},
        ),
        RunTelemetry(
            task_id="t2",
            arm="vanilla",
            passed=False,
            wall_clock_sec=200.0,
            cost_usd=0.30,
            input_tokens=2000,
            output_tokens=200,
            extra={"harness": "agy"},
        ),
        # Arm: Blyte MCP (2 passes, 0 fails)
        RunTelemetry(
            task_id="t1",
            arm="superstate_agent_mcp",
            passed=True,
            wall_clock_sec=110.0,
            cost_usd=0.25,
            input_tokens=1100,
            output_tokens=110,
            extra={"harness": "agy"},
        ),
        RunTelemetry(
            task_id="t2",
            arm="superstate_agent_mcp",
            passed=True,
            wall_clock_sec=150.0,
            cost_usd=0.35,
            input_tokens=1500,
            output_tokens=150,
            extra={"harness": "agy"},
        ),
    ]

    summary = generate_comparison_summary(runs, human_fail_cost_usd=50.0)

    # Vanilla check
    v = summary["vanilla"]
    assert v["passes"] == 1
    assert v["failures"] == 1
    assert v["compute_value_usd"] == 0.20
    assert v["compute_wasted_usd"] == 0.30
    assert v["human_remediation_cost_usd"] == 50.0
    assert v["tco_usd"] == 50.50
    assert v["effective_cost_per_solve_usd"] == 50.50

    # MCP check
    m = summary["superstate_agent_mcp"]
    assert m["passes"] == 2
    assert m["failures"] == 0
    assert m["compute_value_usd"] == 0.60
    assert m["compute_wasted_usd"] == 0.0
    assert m["human_remediation_cost_usd"] == 0.0
    assert m["tco_usd"] == 0.60
    assert m["effective_cost_per_solve_usd"] == 0.30

    # Lift check
    lift = compute_control_plane_lift(runs, baseline_arm="vanilla")
    entry = lift["agy+superstate_agent_mcp"]
    assert entry["delta_passes"] == 1
    assert entry["delta_cost_usd"] == 0.10
    assert entry["marginal_cost_per_win_usd"] == 0.10

    # Table render checks
    tco_table = render_economic_tco_table(summary)
    assert "Total Cost of Ownership" in tco_table
    assert "$50.50" in tco_table

    lift_table = render_lift_report(runs, baseline_arm="vanilla")
    assert "$/Marginal Win" in lift_table
    assert "+1" in lift_table


def test_summary_reports_pass_rate_and_skips_with_infra_skip() -> None:
    """A run list with one pass, one fail, and one infra skip reports 1 of 2 passed and 1 skipped."""
    runs = [
        RunTelemetry(
            task_id="t1",
            arm="vanilla",
            passed=True,
            wall_clock_sec=100.0,
            cost_usd=0.20,
            input_tokens=1000,
            output_tokens=100,
            extra={"harness": "agy"},
        ),
        RunTelemetry(
            task_id="t2",
            arm="vanilla",
            passed=False,
            wall_clock_sec=200.0,
            cost_usd=0.30,
            input_tokens=2000,
            output_tokens=200,
            failure_reason="AssertionError: verification failed",
            extra={"harness": "agy"},
        ),
        RunTelemetry(
            task_id="t3",
            arm="vanilla",
            passed=False,
            wall_clock_sec=50.0,
            cost_usd=0.10,
            input_tokens=500,
            output_tokens=50,
            failure_reason="infrastructure: Failed to acquire concurrency governor slot within timeout",
            extra={"harness": "agy", "infra_skip": True},
        ),
    ]

    summary = generate_comparison_summary(runs, human_fail_cost_usd=50.0)
    v = summary["vanilla"]

    # 1 of 2 scored/passed, not 1 of 3
    assert v["passes"] == 1
    assert v["total_tasks"] == 2
    assert v["failures"] == 1
    assert v["pass_rate_pct"] == 50.0
    assert v["skipped"] == 1
    assert v["infra_skipped"] == 1

    # Infra-skipped run is excluded from cost and time figures
    assert v["total_cost_usd"] == 0.50
    assert v["total_wall_clock_sec"] == 300.0
    assert v["compute_value_usd"] == 0.20
    assert v["compute_wasted_usd"] == 0.30
    assert v["total_input_tokens"] == 3000
    assert v["total_output_tokens"] == 300

    # Human remediation penalty only covers true task failures (1 failure * $50)
    assert v["human_remediation_cost_usd"] == 50.0
    assert v["tco_usd"] == 50.50

    # Summary table renders the skipped count per arm
    table = render_summary_table(summary)
    assert "1 skipped (infrastructure)" in table
    assert "vanilla: 1 skipped (infrastructure)" in table


def test_lift_comparison_excludes_infra_skips() -> None:
    """Paired lift comparisons exclude infra skips from passes, denominators, and cost."""
    runs = [
        # Baseline: vanilla
        RunTelemetry(
            task_id="t1", arm="vanilla", passed=True, cost_usd=0.20, wall_clock_sec=10.0,
            input_tokens=100, output_tokens=10, extra={"harness": "agy"},
        ),
        RunTelemetry(
            task_id="t2", arm="vanilla", passed=False, cost_usd=0.20, wall_clock_sec=10.0,
            input_tokens=100, output_tokens=10, extra={"harness": "agy"},
        ),
        RunTelemetry(
            task_id="t3", arm="vanilla", passed=False, cost_usd=0.20, wall_clock_sec=10.0,
            input_tokens=100, output_tokens=10, extra={"harness": "agy"},
        ),
        # Arm: superpowers
        RunTelemetry(
            task_id="t1", arm="superpowers", passed=True, cost_usd=0.30, wall_clock_sec=15.0,
            input_tokens=150, output_tokens=15, extra={"harness": "agy"},
        ),
        RunTelemetry(
            task_id="t2", arm="superpowers", passed=True, cost_usd=0.30, wall_clock_sec=15.0,
            input_tokens=150, output_tokens=15, extra={"harness": "agy"},
        ),
        # Arm t3 ended with infra skip
        RunTelemetry(
            task_id="t3", arm="superpowers", passed=False, cost_usd=0.05, wall_clock_sec=2.0,
            input_tokens=0, output_tokens=0,
            failure_reason="infrastructure: Failed to acquire concurrency governor slot within timeout",
            extra={"harness": "agy", "infra_skip": True},
        ),
    ]

    lift = compute_control_plane_lift(runs, baseline_arm="vanilla")
    entry = lift["agy+superpowers"]

    assert entry["paired_tasks"] == 2
    assert entry["baseline_passes"] == 1
    assert entry["arm_passes"] == 2
    assert entry["arm_cost_usd"] == 0.60
    assert entry["skipped"] == 1
    assert entry["infra_skipped"] == 1

    report = render_lift_report(runs, baseline_arm="vanilla")
    assert "1 skipped (infrastructure)" in report

