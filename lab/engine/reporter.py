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


# The arm representing the harness with no layer applied: the paired baseline.
BASELINE_ARM = "vanilla"


def _harness_of(run: RunTelemetry) -> str:
    return str((run.extra or {}).get("harness") or "unknown")


def compute_control_plane_lift(
    runs: List[RunTelemetry], baseline_arm: str = BASELINE_ARM
) -> Dict[str, Any]:
    """Measure what each layer adds to a given harness, task by task.

    This evaluation is a paired comparison -- the same harness, model and task run
    with and without a layer on top -- so the headline number is the delta, not the
    absolute pass rate. Pairing is done per (harness, task) and runs without a
    baseline partner are excluded rather than silently compared against nothing.
    """
    # (harness, task) -> {arm: run}
    cells: Dict[tuple[str, str], Dict[str, RunTelemetry]] = {}
    for run in runs:
        cells.setdefault((_harness_of(run), run.task_id), {})[run.arm] = run

    results: Dict[str, Any] = {}
    for (harness, task_id), by_arm in cells.items():
        baseline = by_arm.get(baseline_arm)
        if baseline is None:
            continue
        for arm, run in by_arm.items():
            if arm == baseline_arm:
                continue
            entry = results.setdefault(
                f"{harness}+{arm}",
                {
                    "harness": harness,
                    "arm": arm,
                    "paired_tasks": 0,
                    "baseline_passes": 0,
                    "arm_passes": 0,
                    "gained": [],
                    "lost": [],
                    "baseline_cost_usd": 0.0,
                    "arm_cost_usd": 0.0,
                },
            )
            entry["paired_tasks"] += 1
            entry["baseline_passes"] += int(baseline.passed)
            entry["arm_passes"] += int(run.passed)
            entry["baseline_cost_usd"] += baseline.cost_usd
            entry["arm_cost_usd"] += run.cost_usd
            if run.passed and not baseline.passed:
                entry["gained"].append(task_id)
            elif baseline.passed and not run.passed:
                entry["lost"].append(task_id)

    for entry in results.values():
        n = entry["paired_tasks"]
        entry["baseline_pass_rate_pct"] = round(entry["baseline_passes"] / n * 100, 1) if n else 0.0
        entry["arm_pass_rate_pct"] = round(entry["arm_passes"] / n * 100, 1) if n else 0.0
        entry["lift_pct_points"] = round(
            entry["arm_pass_rate_pct"] - entry["baseline_pass_rate_pct"], 1
        )
        entry["baseline_cost_usd"] = round(entry["baseline_cost_usd"], 2)
        entry["arm_cost_usd"] = round(entry["arm_cost_usd"], 2)
        entry["cost_ratio"] = (
            round(entry["arm_cost_usd"] / entry["baseline_cost_usd"], 2)
            if entry["baseline_cost_usd"]
            else None
        )
    return results


def render_lift_report(runs: List[RunTelemetry], baseline_arm: str = BASELINE_ARM) -> str:
    """Render control-plane lift, with the caveat that small n cannot support it."""
    lift = compute_control_plane_lift(runs, baseline_arm=baseline_arm)
    if not lift:
        return f"No paired results: no runs found for the '{baseline_arm}' baseline arm."

    lines = [
        f"## Control-plane lift over `{baseline_arm}` (paired by harness and task)",
        "",
        "| Configuration | Paired tasks | Baseline | With layer | Lift | Gained | Lost | Cost x |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in sorted(lift):
        e = lift[name]
        ratio = f"{e['cost_ratio']}x" if e["cost_ratio"] is not None else "n/a"
        lines.append(
            f"| {name} | {e['paired_tasks']} | {e['baseline_pass_rate_pct']}% | "
            f"{e['arm_pass_rate_pct']}% | {e['lift_pct_points']:+.1f}pp | "
            f"{len(e['gained'])} | {len(e['lost'])} | {ratio} |"
        )

    smallest = min(e["paired_tasks"] for e in lift.values())
    if smallest < 20:
        step = round(100.0 / smallest, 1)
        lines += [
            "",
            f"> Smallest cell is {smallest} paired tasks, so one task is worth {step}pp. "
            "Treat any lift smaller than a few tasks as noise; the gained/lost columns "
            "are more informative than the percentage at this n.",
        ]
    return "\n".join(lines)
