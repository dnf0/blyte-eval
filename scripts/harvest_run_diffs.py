#!/usr/bin/env python3
"""Harvest labelled diffs and execution telemetry from /tmp/blyte_eval_runs.

This script saves the perishable execution history before the 12GB temporary
directory is wiped between benchmark runs.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

RUNS_DIR = Path("/tmp/blyte_eval_runs")
OUTPUT_FILE = Path(__file__).resolve().parent.parent / "data" / "harvested_run_diffs_20260917.json"


def get_git_diff_and_untracked(workspace_dir: Path) -> tuple[str, list[str]]:
    """Extract git diff from initial baseline commit to current state, including untracked files."""
    if not workspace_dir.exists() or not (workspace_dir / ".git").exists():
        return "", []

    try:
        # Get commit history
        commits_out = subprocess.check_output(
            ["git", "-C", str(workspace_dir), "log", "--format=%H"],
            stderr=subprocess.DEVNULL,
        ).decode().strip().split()
        if not commits_out:
            return "", []

        base_commit = commits_out[-1]

        # Get diff against base commit
        # Ignore .agent-state and run-in-container in diff
        diff_out = subprocess.check_output(
            [
                "git",
                "-C",
                str(workspace_dir),
                "diff",
                base_commit,
                "--",
                ".",
                ":(exclude).agent-state",
                ":(exclude)run-in-container",
            ],
            stderr=subprocess.DEVNULL,
        ).decode()

        # Check untracked files
        status_out = subprocess.check_output(
            ["git", "-C", str(workspace_dir), "status", "--porcelain", "-uall"],
            stderr=subprocess.DEVNULL,
        ).decode()

        untracked: list[str] = []
        for line in status_out.splitlines():
            if line.startswith("?? "):
                path = line[3:].strip()
                if not path.startswith(".agent-state") and path != "run-in-container":
                    untracked.append(path)

        return diff_out, untracked
    except Exception as e:
        return f"ERROR extracting diff: {e}", []


def harvest() -> None:
    if not RUNS_DIR.exists():
        print(f"Error: {RUNS_DIR} does not exist.")
        return

    records: list[dict[str, Any]] = []
    batches = sorted([d for d in RUNS_DIR.iterdir() if d.is_dir()])
    print(f"Found {len(batches)} batches in {RUNS_DIR}")

    for batch in batches:
        run_dirs = sorted([d for d in batch.iterdir() if d.is_dir()])
        print(f"Batch {batch.name}: {len(run_dirs)} runs")

        for rdir in run_dirs:
            run_id = rdir.name
            logs_dir = rdir / "logs"
            ws_dir = rdir / "workspace"

            run_json_path = logs_dir / "run.json"
            milestones_path = logs_dir / "milestones.jsonl"

            run_data: dict[str, Any] = {}
            if run_json_path.exists():
                try:
                    with open(run_json_path) as f:
                        run_data = json.load(f)
                except Exception as e:
                    run_data = {"error": f"Failed to parse run.json: {e}"}

            milestones: list[dict[str, Any]] = []
            if milestones_path.exists():
                try:
                    with open(milestones_path) as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                milestones.append(json.loads(line))
                except Exception as e:
                    milestones = [{"error": f"Failed to parse milestones.jsonl: {e}"}]
            model_patch_path = logs_dir / "artifacts" / "model.patch"
            if model_patch_path.is_file():
                diff_str = model_patch_path.read_text(encoding="utf-8", errors="replace")
                untracked = []
            else:
                diff_str, untracked = get_git_diff_and_untracked(ws_dir)

            telemetry = run_data.get("telemetry", {})
            extra = telemetry.get("extra", {})

            task_id = run_data.get("task_id") or extra.get("task_id")
            arm = run_data.get("arm") or telemetry.get("arm")
            grader_passed = telemetry.get("passed")
            agent_succeeded = extra.get("agent_succeeded")
            failure_reason = telemetry.get("failure_reason")

            # Determine gate verdict across milestones
            gate_passed: bool | None = None
            if milestones:
                # If any milestone failed gate, gate didn't pass overall; if all passed, True
                gates = [m.get("gate_passed") for m in milestones if m.get("gate_ran")]
                if gates:
                    gate_passed = all(gates)

            records.append({
                "batch": batch.name,
                "run_id": run_id,
                "task_id": task_id,
                "arm": arm,
                "grader_passed": grader_passed,
                "gate_passed": gate_passed,
                "agent_succeeded": agent_succeeded,
                "failure_reason": failure_reason,
                "wall_clock_sec": telemetry.get("wall_clock_sec"),
                "cost_usd": telemetry.get("cost_usd"),
                "input_tokens": telemetry.get("input_tokens"),
                "output_tokens": telemetry.get("output_tokens"),
                "milestones": milestones,
                "git_diff": diff_str,
                "untracked_files": untracked,
            })

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(records, f, indent=2)

    print(f"\nSuccessfully harvested {len(records)} runs to {OUTPUT_FILE}")
    print(f"File size: {OUTPUT_FILE.stat().st_size / (1024 * 1024):.2f} MB")

    # Summary table
    passed_grader = sum(1 for r in records if r["grader_passed"] is True)
    failed_grader = sum(1 for r in records if r["grader_passed"] is False)
    unknown_grader = sum(1 for r in records if r["grader_passed"] is None)
    with_diff = sum(1 for r in records if r["git_diff"] and not r["git_diff"].startswith("ERROR"))

    print("\nBreakdown:")
    print(f"  Total records: {len(records)}")
    print(f"  With git diff: {with_diff}")
    print(f"  Grader passed: {passed_grader}")
    print(f"  Grader failed: {failed_grader}")
    print(f"  Grader None:   {unknown_grader}")

    # False pass cases: gate_passed is True, but grader_passed is False
    false_passes = [r for r in records if r["gate_passed"] is True and r["grader_passed"] is False]
    print(f"\nCritical subset: Gate Passed (True) but Grader Failed (False): {len(false_passes)} runs")
    for fp in false_passes:
        print(f"  - [{fp['arm']}] {fp['task_id']} (batch: {fp['batch']}) - diff len: {len(fp['git_diff'])}")


if __name__ == "__main__":
    harvest()
