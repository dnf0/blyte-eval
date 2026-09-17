#!/usr/bin/env python3
"""Offline code review evaluation against harvested false-pass and true-pass runs.

Evaluates whether adversarial static review catches cases where a verification gate
passed but the sealed grader failed (the 17%-precision gate failure mode), and measures
its false alarm rate on true passes.

Usage:
    .venv/bin/python scripts/eval_offline_review.py [--model gemini-3.8-flash-low] [--concurrency 4]
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("eval_offline_review")

CACHE_DIR = Path("results/offline_review_cache")
DIFFS_FILE = Path("results/harvested_run_diffs_20260917.json")
TASKS_DIR = Path.home() / ".cache/agent-rules/frontier-eval/tasks"

REVIEW_SYSTEM_PROMPT = """You are an adversarial zero-noise code reviewer.
CRITICAL CONSTRAINT: Do NOT invoke any tools, shell commands, or external file searches. You are in offline static review mode. Rely SOLELY on the provided task requirements and git diff text.

NOTE ON ENVIRONMENT AND PATHS:
- The candidate git diff is taken from the root of the project repository (mounted at /app or working directory in the execution container). File paths in the diff are relative to this root (e.g. diff for 'move.txt' corresponds to '/app/move.txt').
- Build outputs, global package installations, or external assets may already exist in the environment. Focus your evaluation strictly on defects, errors, and missing logic within the diff itself.

Review the following git diff against the task requirements, architectural contracts, regression risks, resource leaks, and edge cases.
Format your response as strict JSON conforming to:
{
  "summary": "<one sentence overview>",
  "findings": [
    {
      "severity": "Critical" | "High" | "Medium" | "Low",
      "file": "<path>",
      "line_range": [<start>, <end>],
      "problem": "<root issue>",
      "suggested_fix": "<actionable fix>"
    }
  ],
  "has_blocking_issues": true | false
}
Do not produce conversational text or praise. If there are no issues, set findings to [] and has_blocking_issues to false."""


def get_task_instruction(task_id: str) -> str:
    """Retrieve the task instruction markdown."""
    task_name = task_id.split("/")[-1]
    inst_path = TASKS_DIR / task_name / "instruction.md"
    if inst_path.is_file():
        return inst_path.read_text(encoding="utf-8", errors="replace")
    return f"Task instruction file missing for {task_name}."


def clean_json_response(raw: str) -> str:
    """Extract clean JSON text from LLM response."""
    text = raw.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def run_review_single(
    run_record: dict[str, Any],
    model: str,
    timeout_sec: float = 60.0,
) -> dict[str, Any]:
    """Execute review for a single harvested run record."""
    run_id = run_record["run_id"]
    model_slug = model.replace(".", "_").replace("-", "_")
    cache_path = CACHE_DIR / f"{run_id}_{model_slug}.json"

    if cache_path.is_file():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    task_id = run_record["task_id"]
    instruction = get_task_instruction(task_id)
    diff = run_record.get("git_diff", "")

    # Cap diff at 120,000 characters if extraordinarily large
    max_diff_len = 120_000
    if len(diff) > max_diff_len:
        diff = diff[:max_diff_len] + f"\n\n[... truncated {len(diff) - max_diff_len} characters ...]"

    prompt = f"""{REVIEW_SYSTEM_PROMPT}

# TASK REQUIREMENTS
{instruction}

# GIT CANDIDATE DIFF
```diff
{diff}
```
"""

    start_time = time.monotonic()
    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [
            "/Users/danielfisher/.local/bin/agy",
            "--model",
            model,
            "--output-format",
            "json",
            "--dangerously-skip-permissions",
            "--print",
            prompt,
        ]
        try:
            proc = subprocess.run(
                cmd,
                cwd=tmpdir,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
        except subprocess.TimeoutExpired:
            return {
                "run_id": run_id,
                "task_id": task_id,
                "error": f"Review timed out after {timeout_sec}s",
                "duration_seconds": time.monotonic() - start_time,
                "has_blocking_issues": False,
                "findings": [],
            }
        except Exception as exc:
            return {
                "run_id": run_id,
                "task_id": task_id,
                "error": f"Invocation error: {exc}",
                "duration_seconds": time.monotonic() - start_time,
                "has_blocking_issues": False,
                "findings": [],
            }

    duration = time.monotonic() - start_time
    if proc.returncode != 0:
        return {
            "run_id": run_id,
            "task_id": task_id,
            "error": f"agy exited with {proc.returncode}: {proc.stderr[:300]}",
            "duration_seconds": duration,
            "has_blocking_issues": False,
            "findings": [],
        }

    try:
        agy_resp = json.loads(proc.stdout)
        resp_text = agy_resp.get("response", "")
        clean_text = clean_json_response(resp_text)
        report = json.loads(clean_text)
    except Exception as exc:
        return {
            "run_id": run_id,
            "task_id": task_id,
            "error": f"JSON parse error: {exc}",
            "raw_response": proc.stdout[:500],
            "duration_seconds": duration,
            "has_blocking_issues": False,
            "findings": [],
        }

    findings = report.get("findings", [])
    has_blocking = report.get("has_blocking_issues", False)
    # Check if any finding has Critical or High severity
    crit_or_high = [
        f for f in findings if isinstance(f, dict) and str(f.get("severity", "")).lower() in ("critical", "high", "blocker")
    ]
    if crit_or_high:
        has_blocking = True

    result = {
        "run_id": run_id,
        "task_id": task_id,
        "arm": run_record.get("arm"),
        "gate_passed": run_record.get("gate_passed"),
        "grader_passed": run_record.get("grader_passed"),
        "has_blocking_issues": has_blocking,
        "blocking_findings_count": len(crit_or_high),
        "total_findings_count": len(findings),
        "summary": report.get("summary", ""),
        "findings": findings,
        "duration_seconds": duration,
    }

    # Save to cache
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate offline review on false and true passes.")
    parser.add_argument("--model", default="gemini-3.8-flash-low", help="Model to evaluate")
    parser.add_argument("--concurrency", type=int, default=4, help="Parallel reviews")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of runs evaluated")
    parser.add_argument("--family", default=None, choices=["terminal-bench", "datacurve"], help="Filter family")
    args = parser.parse_args()

    if not DIFFS_FILE.is_file():
        logger.error("Missing harvested diffs file: %s", DIFFS_FILE)
        sys.exit(1)

    with open(DIFFS_FILE, "r", encoding="utf-8") as f:
        all_runs = json.load(f)

    # Filter down to runs where gate passed
    gate_passed_runs = [r for r in all_runs if r.get("gate_passed") is True]

    if args.family:
        gate_passed_runs = [r for r in gate_passed_runs if args.family in r.get("task_id", "")]

    if args.limit:
        gate_passed_runs = gate_passed_runs[: args.limit]

    false_passes = [r for r in gate_passed_runs if r.get("grader_passed") is False]
    true_passes = [r for r in gate_passed_runs if r.get("grader_passed") is True]

    logger.info(
        "Evaluating %d total runs (False passes: %d, True passes: %d) with model %s (concurrency=%d)",
        len(gate_passed_runs),
        len(false_passes),
        len(true_passes),
        args.model,
        args.concurrency,
    )

    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = {
            executor.submit(run_review_single, r, args.model): r["run_id"] for r in gate_passed_runs
        }
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            results.append(res)
            status = "BLOCKED" if res.get("has_blocking_issues") else "PASSED"
            err = f" [ERROR: {res['error']}]" if "error" in res else ""
            logger.info("Reviewed %s -> %s (%d findings)%s", res["task_id"], status, res.get("total_findings_count", 0), err)

    # Compute Metrics
    # 1. False passes: how many were blocked (True Positives for review)?
    fp_runs = [res for res in results if res.get("grader_passed") is False]
    tp_review = [res for res in fp_runs if res.get("has_blocking_issues") is True]

    # 2. True passes: how many were blocked (False Positives for review)?
    tp_runs = [res for res in results if res.get("grader_passed") is True]
    fp_review = [res for res in tp_runs if res.get("has_blocking_issues") is True]
    tn_review = [res for res in tp_runs if res.get("has_blocking_issues") is False]

    bug_recall = len(tp_review) / len(fp_runs) if fp_runs else 0.0
    false_alarm_rate = len(fp_review) / len(tp_runs) if tp_runs else 0.0

    # Gate precision: baseline vs post-review
    baseline_prec = len(tp_runs) / len(results) if results else 0.0
    unblocked_runs = [res for res in results if res.get("has_blocking_issues") is False]
    post_review_prec = len(tn_review) / len(unblocked_runs) if unblocked_runs else 0.0

    print("\n" + "=" * 80)
    print("OFFLINE REVIEW EVALUATION RESULTS")
    print("=" * 80)
    print(f"Model: {args.model}")
    print(f"Total Runs Evaluated: {len(results)}")
    print(f"  - False Passes (Gate=True, Grader=False): {len(fp_runs)}")
    print(f"  - True Passes (Gate=True, Grader=True):   {len(tp_runs)}")
    print("-" * 80)
    print("PERFORMANCE METRICS:")
    print(f"  Bug Recall (False Passes Caught / Total False Passes): {len(tp_review)}/{len(fp_runs)} ({bug_recall:.1%})")
    print(f"  False Alarm Rate (True Passes Blocked / Total True Passes): {len(fp_review)}/{len(tp_runs)} ({false_alarm_rate:.1%})")
    print(f"  Gate Precision (Baseline):    {len(tp_runs)}/{len(results)} ({baseline_prec:.1%})")
    print(f"  Gate+Review Precision:        {len(tn_review)}/{len(unblocked_runs)} ({post_review_prec:.1%})")
    print("-" * 80)

    # Breakdown by family
    for fam in ("terminal-bench", "datacurve"):
        fam_results = [r for r in results if fam in r.get("task_id", "")]
        if not fam_results:
            continue
        fam_fp = [r for r in fam_results if r.get("grader_passed") is False]
        fam_tp = [r for r in fam_results if r.get("grader_passed") is True]
        fam_caught = [r for r in fam_fp if r.get("has_blocking_issues") is True]
        fam_false_alarms = [r for r in fam_tp if r.get("has_blocking_issues") is True]
        fam_unblocked = [r for r in fam_results if r.get("has_blocking_issues") is False]
        fam_unblocked_tp = [r for r in fam_unblocked if r.get("grader_passed") is True]

        fam_recall = len(fam_caught) / len(fam_fp) if fam_fp else 0.0
        fam_fa = len(fam_false_alarms) / len(fam_tp) if fam_tp else 0.0
        fam_base_p = len(fam_tp) / len(fam_results) if fam_results else 0.0
        fam_post_p = len(fam_unblocked_tp) / len(fam_unblocked) if fam_unblocked else 0.0

        print(f"\nFAMILY BREAKDOWN: {fam.upper()} (n={len(fam_results)})")
        print(f"  False Passes: {len(fam_fp)} | True Passes: {len(fam_tp)}")
        print(f"  Bug Recall:             {len(fam_caught)}/{len(fam_fp)} ({fam_recall:.1%})")
        print(f"  False Alarm Rate:       {len(fam_false_alarms)}/{len(fam_tp)} ({fam_fa:.1%})")
        print(f"  Base Gate Precision:    {len(fam_tp)}/{len(fam_results)} ({fam_base_p:.1%})")
        print(f"  Gate+Review Precision:  {len(fam_unblocked_tp)}/{len(fam_unblocked)} ({fam_post_p:.1%})")

    print("=" * 80)

    # Save summary artifact
    out_file = Path("results/offline_review_eval_20260917.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "model": args.model,
                "total_evaluated": len(results),
                "bug_recall": bug_recall,
                "false_alarm_rate": false_alarm_rate,
                "baseline_precision": baseline_prec,
                "gate_review_precision": post_review_prec,
                "results": results,
            },
            f,
            indent=2,
        )
    logger.info("Saved full evaluation results to %s", out_file)


if __name__ == "__main__":
    main()
