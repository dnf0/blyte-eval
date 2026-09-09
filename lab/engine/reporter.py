"""Evaluation reporter generating cost-efficiency frontier comparisons."""

from __future__ import annotations

from collections import Counter
import re
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
        total_input_tokens = sum(r.input_tokens for r in arm_runs)
        total_output_tokens = sum(r.output_tokens for r in arm_runs)
        cost_per_solve = round(total_cost / passes, 2) if passes > 0 else None
        input_tokens_per_solve = round(total_input_tokens / passes) if passes > 0 else None
        output_tokens_per_solve = round(total_output_tokens / passes) if passes > 0 else None

        summary[arm] = {
            "total_tasks": total_tasks,
            "passes": passes,
            "pass_rate_pct": pass_rate,
            "total_cost_usd": total_cost,
            "cost_per_solve_usd": cost_per_solve,
            "total_wall_clock_sec": total_wall_clock_sec,
            "total_lease_extensions_sec": total_extensions,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "input_tokens_per_solve": input_tokens_per_solve,
            "output_tokens_per_solve": output_tokens_per_solve,
        }

    return summary


def render_summary_table(summary: Dict[str, Dict[str, Any]]) -> str:
    """Render summary as a formatted text table for reports."""
    lines = [
        "| Paradigm Arm | Tasks | Passes | Strict Pass Rate | Total Cost ($) | Cost/Solve ($) | "
        "Wall-clock (m) | Lease Ext (m) | Tokens In/Solve | Tokens Out/Solve |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for arm, stats in summary.items():
        wall_min = round(stats["total_wall_clock_sec"] / 60.0, 1)
        ext_min = round(stats["total_lease_extensions_sec"] / 60.0, 1)
        cost_solve = (
            f"${stats['cost_per_solve_usd']}" if stats["cost_per_solve_usd"] is not None else "N/A"
        )
        tok_in = stats.get("input_tokens_per_solve")
        tok_out = stats.get("output_tokens_per_solve")
        lines.append(
            f"| {arm} | {stats['total_tasks']} | {stats['passes']} | {stats['pass_rate_pct']}% | "
            f"${stats['total_cost_usd']} | {cost_solve} | {wall_min}m | {ext_min}m | "
            f"{tok_in if tok_in is not None else 'N/A'} | "
            f"{tok_out if tok_out is not None else 'N/A'} |"
        )
    return "\n".join(lines)


def _failure_signature(reason: str | None) -> str:
    """Collapse a failure reason to a comparable class, stripping run-specific detail."""
    if not reason:
        return "unknown"
    first = reason.strip().splitlines()[0]
    # Drop identifiers that differ per run so like failures group together.
    first = re.sub(r"'[^']*'", "'...'", first)
    first = re.sub(r"\b\d+(\.\d+)?\b", "N", first)
    return first[:120]


def summarize_failures(runs: List[RunTelemetry]) -> Dict[str, List[Dict[str, Any]]]:
    """Cluster failures per arm so recurring defects are visible.

    A pass rate says an arm underperformed; this says how it failed and how often,
    which is the signal you act on when improving the state engine.
    """
    per_arm: Dict[str, Counter[str]] = {}
    for run in runs:
        if run.passed:
            continue
        per_arm.setdefault(run.arm, Counter())[_failure_signature(run.failure_reason)] += 1

    return {
        arm: [
            {"signature": sig, "count": count}
            for sig, count in counter.most_common()
        ]
        for arm, counter in per_arm.items()
    }


def render_failure_report(runs: List[RunTelemetry]) -> str:
    """Render clustered failures as text, most frequent first."""
    clusters = summarize_failures(runs)
    if not clusters:
        return "No failures recorded."

    lines = ["## Failure clusters by arm", ""]
    for arm in sorted(clusters):
        entries = clusters[arm]
        lines.append(f"### {arm} ({sum(e['count'] for e in entries)} failures)")
        for entry in entries:
            lines.append(f"- {entry['count']}x  {entry['signature']}")
        lines.append("")
    return "\n".join(lines).rstrip()
