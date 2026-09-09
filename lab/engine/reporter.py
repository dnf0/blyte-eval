"""Evaluation reporter generating cost-efficiency frontier comparisons."""

from __future__ import annotations

from typing import Any, Dict, List

from lab.engine.budget_policy import RunTelemetry


def generate_comparison_summary(runs: List[RunTelemetry]) -> Dict[str, Dict[str, Any]]:
    """Group run telemetry by paradigm arm and calculate core efficiency metrics."""
    arms: Dict[str, List[RunTelemetry]] = {}
    for run in runs:
        arms.setdefault(run.arm, []).append(run)

    summary: Dict[str, Dict[str, Any]] = {}

    for arm, arm_runs in arms.items():
        total_tasks = len(arm_runs)
        passes = sum(1 for r in arm_runs if r.passed)
        pass_rate = round((passes / total_tasks * 100.0) if total_tasks > 0 else 0.0, 1)
        total_cost = round(sum(r.cost_usd for r in arm_runs), 2)
        total_wall_clock_sec = round(sum(r.wall_clock_sec for r in arm_runs), 1)
        total_extensions = round(sum(r.lease_extensions_earned_sec for r in arm_runs), 1)
        cost_per_solve = round(total_cost / passes, 2) if passes > 0 else None

        summary[arm] = {
            "total_tasks": total_tasks,
            "passes": passes,
            "pass_rate_pct": pass_rate,
            "total_cost_usd": total_cost,
            "cost_per_solve_usd": cost_per_solve,
            "total_wall_clock_sec": total_wall_clock_sec,
            "total_lease_extensions_sec": total_extensions,
        }

    return summary


def render_summary_table(summary: Dict[str, Dict[str, Any]]) -> str:
    """Render summary as a formatted text table for reports."""
    lines = [
        "| Paradigm Arm | Tasks | Passes | Strict Pass Rate | Total Cost ($) | Cost/Solve ($) | Wall-clock (m) | Lease Ext (m) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for arm, stats in summary.items():
        wall_min = round(stats["total_wall_clock_sec"] / 60.0, 1)
        ext_min = round(stats["total_lease_extensions_sec"] / 60.0, 1)
        cost_solve = (
            f"${stats['cost_per_solve_usd']}" if stats["cost_per_solve_usd"] is not None else "N/A"
        )
        lines.append(
            f"| {arm} | {stats['total_tasks']} | {stats['passes']} | {stats['pass_rate_pct']}% | "
            f"${stats['total_cost_usd']} | {cost_solve} | {wall_min}m | {ext_min}m |"
        )
    return "\n".join(lines)
