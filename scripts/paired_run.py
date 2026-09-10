#!/usr/bin/env python3
"""Run one or more tasks across all arms and report control-plane lift.

The evaluation is paired: the same harness, model and task are run natively, with
the skill layer, and with the control plane. The headline is the delta between
them, so every task is run through every arm.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
from pathlib import Path
import sys
import time
from typing import Any

from lab.benchmarks.task_loader import load_benchmark_tasks, load_task_from_dir
from lab.engine.drivers.agy_cli import AgyCliDriver
from lab.engine.governor import ConcurrencyGovernor
from lab.engine.reporter import generate_comparison_summary, render_lift_report, render_summary_table
from lab.engine.runner import AblationRunner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("superstate_eval.paired")

DEFAULT_TASKS = Path.home() / ".cache/agent-rules/frontier-eval/tasks"


def main() -> int:
    ap = argparse.ArgumentParser(description="Paired control-plane evaluation")
    ap.add_argument("--task", type=Path, help="Single task directory")
    ap.add_argument("--tasks-root", type=Path, default=DEFAULT_TASKS)
    ap.add_argument("--only-with-verifier", action="store_true",
                    help="Skip tasks that ship no held-out verifier")
    ap.add_argument("--arms", nargs="+", default=["vanilla", "superpowers", "superstate"])
    ap.add_argument("--model", default="gemini-3.8-flash-high")
    ap.add_argument("--budget-sec", type=float, default=None,
                    help="Budget per arm in seconds (default: task declared agent_timeout_sec or 3600.0s)")
    ap.add_argument("--repeats", type=int, default=1, help="Number of repetitions per task/arm")
    ap.add_argument("--concurrency", type=int, default=3, help="Max concurrent workers (default: 3)")
    ap.add_argument("--workspace-root", type=Path,
                    default=Path("/tmp/superstate_eval_runs") / time.strftime("%Y%m%d-%H%M%S"))
    ap.add_argument("--tasks", nargs="+", help="Specific task names or directories")
    ap.add_argument("--tier1", action="store_true", help="Run the 9 Tier-1 Frontier software engineering tasks")
    ap.add_argument("--out", type=Path, help="Write results JSON here")
    args = ap.parse_args()

    tier1_names = {
        "anko-typed-variable-bindings",
        "fastapi-deprecation-response-headers",
        "httpx-multipart-response-parsing",
        "python-statemachine-state-data-scoping",
        "expr-try-catch-errors",
        "scc-bounded-memory-spilling",
        "arktype-json-schema-refs-dependencies",
        "meriyah-explicit-resource-declarations",
        "katex-multicolumn-array-spans",
    }

    if args.task:
        tasks = [load_task_from_dir(args.task)]
    elif args.tasks:
        tasks = []
        for item in args.tasks:
            p = Path(item)
            if not p.is_dir() and (args.tasks_root / item).is_dir():
                p = args.tasks_root / item
            tasks.append(load_task_from_dir(p))
    else:
        tasks = load_benchmark_tasks(args.tasks_root)

    if args.tier1:
        tasks = [t for t in tasks if t.name in tier1_names or t.id.split("/")[-1] in tier1_names]
    if args.only_with_verifier:
        tasks = [t for t in tasks if t.tests_dir]
    if not tasks:
        logger.error("No tasks selected")
        return 1

    driver = AgyCliDriver(model=args.model)
    governor = ConcurrencyGovernor(
        cpus_per_worker=2.0,
        ram_gb_per_worker=4.0,
        ram_headroom_gb=6.0,
    ) if args.concurrency > 1 else None
    runner = AblationRunner(
        workspace_root=args.workspace_root,
        default_driver=driver,
        governor=governor,
    )

    total_runs = len(tasks) * len(args.arms) * args.repeats
    budget_label = f"{args.budget_sec:.0f}s" if args.budget_sec else "task-default"
    logger.info("=" * 78)
    logger.info("Harness=%s  model=%s  tasks=%d  arms=%s  repeats=%d  concurrency=%d",
                driver.harness_name, args.model, len(tasks), ", ".join(args.arms), args.repeats, args.concurrency)
    logger.info("Runs=%d  budget=%s/arm  workspaces=%s",
                total_runs, budget_label, args.workspace_root)
    logger.info("=" * 78)

    jobs = []
    for task in tasks:
        for arm in args.arms:
            for rep in range(1, args.repeats + 1):
                jobs.append((task, arm, rep))

    results = []

    def execute_job(t: Any, a: str, r: int) -> Any:
        rep_tag = f" [run {r}/{args.repeats}]" if args.repeats > 1 else ""
        task_budget = args.budget_sec or t.agent_timeout_sec or 3600.0
        logger.info("-> %s [%s]%s (budget: %.0fs)", t.name, a, rep_tag, task_budget)
        started = time.monotonic()
        tel = runner.run_task(
            task_id=t.id, arm=a, image=t.docker_image,
            base_budget_sec=task_budget, task_spec=t, driver=driver,
        )
        logger.info(
            "   %s%s: passed=%s cost=$%.4f turns=%s %.0fs  %s",
            a, rep_tag, tel.passed, tel.cost_usd, (tel.extra or {}).get("turns"),
            time.monotonic() - started, tel.failure_reason or "",
        )
        return tel

    if args.concurrency > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = [pool.submit(execute_job, t, a, r) for t, a, r in jobs]
            for fut in concurrent.futures.as_completed(futures):
                results.append(fut.result())
    else:
        for t, a, r in jobs:
            results.append(execute_job(t, a, r))

    print()
    print(render_summary_table(generate_comparison_summary(results)))
    print()
    print(render_lift_report(results))

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps([r.to_dict() for r in results], indent=2, default=str), encoding="utf-8"
        )
        print(f"\nResults written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
