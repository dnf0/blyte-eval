#!/usr/bin/env python3
"""Run one or more tasks across all arms and report control-plane lift.

The evaluation is paired: the same harness, model and task are run natively, with
the skill layer, and with the control plane. The headline is the delta between
them, so every task is run through every arm.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys
import time

from lab.benchmarks.task_loader import load_benchmark_tasks, load_task_from_dir
from lab.engine.drivers.agy_cli import AgyCliDriver
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
    ap.add_argument("--budget-sec", type=float, default=1200.0)
    ap.add_argument("--repeats", type=int, default=1, help="Number of repetitions per task/arm")
    ap.add_argument("--workspace-root", type=Path,
                    default=Path("/tmp/superstate_eval_runs") / time.strftime("%Y%m%d-%H%M%S"))
    ap.add_argument("--out", type=Path, help="Write results JSON here")
    args = ap.parse_args()

    if args.task:
        tasks = [load_task_from_dir(args.task)]
    else:
        tasks = load_benchmark_tasks(args.tasks_root)
    if args.only_with_verifier:
        tasks = [t for t in tasks if t.tests_dir]
    if not tasks:
        logger.error("No tasks selected")
        return 1

    driver = AgyCliDriver(model=args.model)
    runner = AblationRunner(workspace_root=args.workspace_root, default_driver=driver)

    logger.info("=" * 78)
    logger.info("Harness=%s  model=%s  tasks=%d  arms=%s  repeats=%d",
                driver.harness_name, args.model, len(tasks), ", ".join(args.arms), args.repeats)
    logger.info("Runs=%d  budget=%.0fs/arm  workspaces=%s",
                len(tasks) * len(args.arms) * args.repeats, args.budget_sec, args.workspace_root)
    logger.info("=" * 78)

    results = []
    for task in tasks:
        for arm in args.arms:
            for rep in range(1, args.repeats + 1):
                rep_tag = f" [run {rep}/{args.repeats}]" if args.repeats > 1 else ""
                logger.info("-> %s [%s]%s", task.name, arm, rep_tag)
                started = time.monotonic()
                tel = runner.run_task(
                    task_id=task.id, arm=arm, image=task.docker_image,
                    base_budget_sec=args.budget_sec, task_spec=task, driver=driver,
                )
                results.append(tel)
                logger.info(
                    "   %s%s: passed=%s cost=$%.4f turns=%s %.0fs  %s",
                    arm, rep_tag, tel.passed, tel.cost_usd, (tel.extra or {}).get("turns"),
                    time.monotonic() - started, tel.failure_reason or "",
                )

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
