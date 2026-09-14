#!/usr/bin/env python3
"""Merge freshly rerun superstate_agent_mcp results with existing vanilla and superpowers runs."""

from __future__ import annotations

import json
from pathlib import Path
import sys

from lab.engine.budget_policy import RunTelemetry
from lab.engine.reporter import (
    generate_comparison_summary,
    render_economic_tco_table,
    render_lift_report,
    render_summary_table,
)


def main() -> int:
    triad_path = Path("results/frontier_triad_30tasks.json")
    mcp_path = Path("results/frontier_mcp_30tasks.json")
    out_path = Path("results/frontier_triad_30tasks_reverted.json")

    if not triad_path.is_file():
        print(f"Error: {triad_path} not found", file=sys.stderr)
        return 1
    if not mcp_path.is_file():
        print(f"Error: {mcp_path} not found", file=sys.stderr)
        return 1

    with open(triad_path, encoding="utf-8") as f:
        triad_data = json.load(f)
    with open(mcp_path, encoding="utf-8") as f:
        mcp_data = json.load(f)

    # Filter out old superstate_agent_mcp runs
    base_runs = [d for d in triad_data if d.get("arm") in ("vanilla", "superpowers")]
    mcp_runs = [d for d in mcp_data if d.get("arm") == "superstate_agent_mcp"]

    merged_data = base_runs + mcp_runs
    out_path.write_text(json.dumps(merged_data, indent=2, default=str), encoding="utf-8")
    print(f"Merged {len(base_runs)} baseline runs + {len(mcp_runs)} rerun MCP runs into {out_path}")

    # Convert to RunTelemetry objects for report generation
    telemetry_objects = []
    for d in merged_data:
        telemetry_objects.append(
            RunTelemetry(
                task_id=d["task_id"],
                arm=d["arm"],
                passed=bool(d.get("passed")),
                wall_clock_sec=float(d.get("wall_clock_sec", 0.0)),
                cost_usd=float(d.get("cost_usd", 0.0)),
                input_tokens=int(d.get("input_tokens", 0)),
                output_tokens=int(d.get("output_tokens", 0)),
                milestones_completed=int(d.get("milestones_completed", 0)),
                lease_extensions_earned_sec=float(d.get("lease_extensions_earned_sec", 0.0)),
                total_granted_budget_sec=float(d.get("total_granted_budget_sec", 0.0)),
                failure_reason=d.get("failure_reason"),
                extra=d.get("extra", {}) or {},
            )
        )

    summary = generate_comparison_summary(telemetry_objects)
    print("\n" + render_summary_table(summary))
    print("\n" + render_economic_tco_table(summary))
    print("\n" + render_lift_report(telemetry_objects))
    return 0


if __name__ == "__main__":
    sys.exit(main())
