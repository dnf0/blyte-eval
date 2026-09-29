"""Tests for economic reporting, TCO, and solve-rate weighted metrics."""

from __future__ import annotations

from lab.engine.budget_policy import RunTelemetry
from lab.engine.reporter import (
    compute_control_plane_lift,
    generate_comparison_summary,
    render_economic_tco_table,
    render_lift_report,
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
