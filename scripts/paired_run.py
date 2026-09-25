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
import os
from pathlib import Path
import sys
import time
from typing import Any

# Ensure current repository/worktree root takes precedence over editable installs in site-packages
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lab.benchmarks.gate_fixtures import is_unmeasurable  # noqa: E402
from lab.engine import mcp_isolation  # noqa: E402
from lab.benchmarks.task_loader import load_benchmark_tasks, load_task_from_dir  # noqa: E402
from lab.benchmarks.task_sets import is_canary, is_discriminating  # noqa: E402
from lab.engine.drivers.agy_cli import AgyCliDriver  # noqa: E402
from lab.engine.drivers.claude_cli import ClaudeCliDriver  # noqa: E402
from lab.engine.drivers.superstate_native import SuperstateNativeDriver  # noqa: E402
from lab.engine.harnesses import BARE_ARM, build_harness, by_harness, render_harness_comparison  # noqa: E402
from lab.engine.governor import ConcurrencyGovernor  # noqa: E402
from lab.engine.reporter import generate_comparison_summary, render_lift_report, render_summary_table  # noqa: E402
from lab.engine.runner import AblationRunner  # noqa: E402
from lab.sandbox.answer_key import AnswerKeyGuard  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("superstate_eval.paired")

DEFAULT_TASKS = Path.home() / ".cache/agent-rules/frontier-eval/tasks"


def harness_jobs(tasks: list, drivers: list, repeats: int) -> list:
    """Jobs for a harness comparison, interleaved (A1 B1 A2 B2 ...) rather than blocked
    (A1..An then B1..Bn). API latency and machine load drift over hours, and a blocked order
    charges that drift to whichever harness runs later. Found 2026-09-25, when a 5x5 comparison
    ran every agy repeat before any blyte one."""
    return [
        (task, BARE_ARM, rep, repeats, drv)
        for task in tasks
        for rep in range(1, repeats + 1)
        for drv in drivers
    ]


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Paired control-plane evaluation")
    ap.add_argument("--task", type=Path, help="Single task directory")
    ap.add_argument("--tasks-root", type=Path, default=DEFAULT_TASKS)
    ap.add_argument("--only-with-verifier", action="store_true",
                    help="Skip tasks that ship no held-out verifier")
    ap.add_argument("--arms", nargs="+", default=["vanilla", "superpowers", "superstate"])
    ap.add_argument("--driver", choices=["agy", "claude", "superstate"], default="agy",
                    help="Worker runtime: agy, claude, or the native superstate harness (default: agy)")
    ap.add_argument("--context", choices=["conversational", "folded"], default="folded",
                    help="Native superstate driver only: context strategy (default: folded)")
    ap.add_argument("--harnesses", nargs="+", default=None,
                    help="Harness-vs-harness mode: compare these harnesses on the bare task, first "
                         "is the baseline, e.g. agy superstate[folded] superstate[folded,tdd,review]. "
                         "Replaces --arms, --driver and --context")
    ap.add_argument("--model", default="gemini-3.8-flash-high")
    ap.add_argument("--budget-sec", type=float, default=None,
                    help="Budget per arm in seconds (default: task declared agent_timeout_sec or 3600.0s)")
    ap.add_argument("--repeats", type=int, default=1, help="Number of repetitions per task/arm")
    ap.add_argument("--concurrency", type=int, default=3, help="Max concurrent workers (default: 3)")
    ap.add_argument("--workspace-root", type=Path,
                    default=Path("/tmp/superstate_eval_runs") / time.strftime("%Y%m%d-%H%M%S"))
    ap.add_argument("--tasks", nargs="+", help="Specific task names or directories")
    ap.add_argument("--tier1", action="store_true", help="Run the 9 Tier-1 Frontier software engineering tasks")
    ap.add_argument("--core", action="store_true",
                    help="Run only tasks that can contribute signal: gradeable, and not at a "
                         "ceiling, floor, or toy puzzle. 9 canonical software engineering repositories. See lab/benchmarks/task_sets.py")
    ap.add_argument("--canary", action="store_true",
                    help="Run the fast 3-task Tri-Language SWE-Canary slice (build-cython-ext, scc, katex; ~15-20 min total)")
    ap.add_argument("--out", type=Path, help="Write results JSON here")
    ap.add_argument(
        "--keep-mcp",
        action="store_true",
        help="Do not strip unrelated MCP servers for this run. They cost ~13,288 fresh input "
             "tokens on EVERY agy invocation (FINDINGS 13.17) and no benchmark task uses "
             "github/notion/slack, so this is only for debugging the harness itself.",
    )
    return ap


def main() -> int:
    """Strip unrelated MCP servers for the whole run, then execute it.

    Default ON. Every agy invocation otherwise loads github/notion/slack schemas -- 13,288
    fresh input tokens before the task is read, 55% of a trivial turn, for services no
    benchmark task touches (FINDINGS 13.17). `superstate` is kept only for the legacy arms, where
    it is Condition B's transport; a `--harnesses` comparison strips it too.

    Wrapped here rather than inside the runner so that it covers EVERY agy process a run
    spawns, including the daemon's own worker, which bypasses the drivers.
    """
    ap = build_parser()
    args = ap.parse_args()

    keep = mcp_isolation.servers_to_keep(harness_mode=bool(args.harnesses))
    with mcp_isolation.stripped_mcp_servers(keep=keep, enabled=not args.keep_mcp) as stripped:
        if stripped:
            print(f"MCP servers stripped for this run: {', '.join(stripped)} "
                  f"(~13,288 tokens/invocation saved; --keep-mcp to disable)")
        elif args.keep_mcp:
            print("MCP servers LEFT ENABLED (--keep-mcp): expect ~13,288 extra tokens per call")
        return _run(args)


def _run(args) -> int:

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

    # Ensure any held-out tests left sealed by previously aborted or killed runs are restored.
    AnswerKeyGuard().restore_all()

    if args.task:
        tasks = [load_task_from_dir(args.task)]
    elif args.tasks:
        tasks = []
        for item in args.tasks:
            p = Path(item)
            if not p.is_dir():
                candidate = args.tasks_root / item
                if candidate.is_dir():
                    p = candidate
                else:
                    basename = item.split("/")[-1]
                    if (args.tasks_root / basename).is_dir():
                        p = args.tasks_root / basename
            tasks.append(load_task_from_dir(p))
    else:
        tasks = load_benchmark_tasks(args.tasks_root)

    if args.tier1:
        tasks = [t for t in tasks if t.name in tier1_names or t.id.split("/")[-1] in tier1_names]
    if args.core:
        before = len(tasks)
        tasks = [t for t in tasks if is_discriminating(t.name)]
        logger.info(
            "Core set: %d of %d tasks. Excluded are ungradeable (no held-out tests/) or at a "
            "ceiling or floor, so they cannot move an arm-vs-arm result.",
            len(tasks), before,
        )
    if args.canary:
        before = len(tasks)
        tasks = [t for t in tasks if is_canary(t.name)]
        logger.info(
            "Canary slice: %d of %d tasks (%s).",
            len(tasks), before, ", ".join(t.name for t in tasks),
        )
    if args.only_with_verifier:
        tasks = [t for t in tasks if t.tests_dir]
    ungradeable = [(t.name, is_unmeasurable(t.name)) for t in tasks if is_unmeasurable(t.name)]
    if ungradeable:
        logger.warning(
            "%d selected task(s) cannot be graded and will score zero for every arm:",
            len(ungradeable),
        )
        for name, reason in ungradeable:
            logger.warning("    %s -- %s", name, reason)

    if not tasks:
        logger.error("No tasks selected")
        return 1

    drivers: list[Any] = []
    if args.harnesses:
        if (
            args.driver != "agy"
            or args.context != "folded"
        ):
            logger.error(
                "--harnesses spells each harness's settings in its name "
                "(e.g. blyte[conversational]); do not combine it with --driver or --context."
            )
            return 1
        report_dir = (
            args.out.with_suffix(".native_reports") if args.out
            else args.workspace_root / "native_reports"
        )
        drivers = [build_harness(s, args.model, report_dir) for s in args.harnesses]
        driver = drivers[0]
    elif args.driver == "claude":
        model = args.model if args.model != "gemini-3.8-flash-high" else "claude-3-7-sonnet-20250219"
        driver = ClaudeCliDriver(model=model)
    elif args.driver == "superstate":
        # Same --model as every other driver, so model parity holds by construction.
        report_dir = (
            args.out.with_suffix(".native_reports") if args.out
            else args.workspace_root / "native_reports"
        )
        driver = SuperstateNativeDriver(
            model=args.model,
            context=args.context,
            report_dir=report_dir,
        )
        logger.info(
            "Native superstate driver: bin=%s (sha256 %s, copied from %s), context=%s, "
            "reports -> %s",
            driver.superstate_bin, driver.superstate_bin_sha256[:12],
            driver.superstate_bin_source, args.context, report_dir,
        )
    else:
        driver = AgyCliDriver(model=args.model)
    # These runs are LLM-bound, not local-compute-bound: the wall clock is the agent
    # waiting on the model, not this machine working. Measured footprint per worker is
    # ~0.6 GB (task containers sit at 5-25 MiB each; the agy processes dominate at
    # ~100 MB apiece), against the 4.0 GB previously assumed. That over-estimate capped
    # concurrency at 2-4 and made a 9-task sweep a six-hour job.
    #
    # 1.5 GB keeps a wide margin over the measured figure while roughly tripling the
    # worker ceiling. CPU per worker is likewise generous for a process that is mostly
    # blocked on network I/O.
    # Size a worker from what the TASKS actually demand, not a constant. TaskSpec.memory_mb
    # is what runner.py passes to Docker as the container limit: 2048m for terminal-bench but
    # 8192m for the datacurve/tier-1 repos. A fixed 1.5 GB under-counts the latter fivefold,
    # so the governor advertises a ceiling the machine cannot honour. EXP-053 ran at
    # concurrency 5 under that ceiling, swapped 8.5 GB, and lost 12 of 54 runs to workers that
    # waited for a slot, gave up at 300s, and were recorded as task failures.
    declared_gb = [t.memory_mb / 1024 for t in tasks if getattr(t, "memory_mb", None)]
    ram_per_worker = float(
        os.environ.get("SUPERSTATE_EVAL_RAM_PER_WORKER_GB")
        or (max(declared_gb) if declared_gb else 1.5)
    )
    if declared_gb and ram_per_worker > 1.5:
        logger.info(
            "Sizing workers at %.1f GB from the tasks' declared memory_mb (was a flat 1.5 GB)",
            ram_per_worker,
        )
    governor = ConcurrencyGovernor(
        cpus_per_worker=float(os.environ.get("SUPERSTATE_EVAL_CPUS_PER_WORKER", "1.0")),
        ram_gb_per_worker=ram_per_worker,
        ram_headroom_gb=float(os.environ.get("SUPERSTATE_EVAL_RAM_HEADROOM_GB", "4.0")),
    ) if args.concurrency > 1 else None
    if governor is not None:
        ceiling = governor.calculate_max_concurrency()
        if args.concurrency > ceiling:
            logger.error(
                "--concurrency %d exceeds the governor's ceiling of %d for these tasks. "
                "Surplus workers starve, give up at 300s, and are recorded as TASK failures. "
                "Re-run with --concurrency %d or fewer.",
                args.concurrency, ceiling, ceiling,
            )
            return 1

    runner = AblationRunner(
        workspace_root=args.workspace_root,
        default_driver=driver,
        governor=governor,
    )

    parsed_arms: list[tuple[str, int]] = []
    for arm_spec in args.arms:
        if ":" in arm_spec:
            arm_name, _, reps_str = arm_spec.partition(":")
            parsed_arms.append((arm_name.strip(), int(reps_str)))
        else:
            parsed_arms.append((arm_spec.strip(), args.repeats))

    total_runs = len(tasks) * sum(reps for _, reps in parsed_arms)
    arms_label = ", ".join(f"{a}:{r}" if r > 1 else a for a, r in parsed_arms)
    budget_label = f"{args.budget_sec:.0f}s" if args.budget_sec else "task-default"
    if drivers:
        total_runs = len(tasks) * len(drivers) * args.repeats
        arms_label = f"{BARE_ARM} x " + ", ".join(d.harness_name for d in drivers)
    logger.info("=" * 78)
    logger.info("Harness=%s  model=%s  tasks=%d  arms=%s  concurrency=%d",
                driver.harness_name, args.model, len(tasks), arms_label, args.concurrency)
    logger.info("Runs=%d  budget=%s/arm  workspaces=%s",
                total_runs, budget_label, args.workspace_root)
    logger.info("=" * 78)

    jobs = []
    if drivers:
        jobs = harness_jobs(tasks, drivers, args.repeats)
    else:
        for task in tasks:
            for arm, reps in parsed_arms:
                for rep in range(1, reps + 1):
                    jobs.append((task, arm, rep, reps, driver))

    results = []

    def execute_job(t: Any, a: str, r: int, total_reps: int, drv: Any) -> Any:
        rep_tag = f" [run {r}/{total_reps}]" if total_reps > 1 else ""
        label = drv.harness_name if a == BARE_ARM else a
        task_budget = args.budget_sec or t.agent_timeout_sec or 3600.0
        logger.info("-> %s [%s]%s (budget: %.0fs)", t.name, label, rep_tag, task_budget)
        started = time.monotonic()
        tel = runner.run_task(
            task_id=t.id, arm=a, image=t.docker_image,
            base_budget_sec=task_budget, task_spec=t, driver=drv,
        )
        logger.info(
            "   %s%s: passed=%s cost=$%.4f turns=%s %.0fs  %s",
            label, rep_tag, tel.passed, tel.cost_usd, (tel.extra or {}).get("turns"),
            time.monotonic() - started, tel.failure_reason or "",
        )
        return tel

    def _save_incremental(current_results: list[Any]) -> None:
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(
                json.dumps([r.to_dict() for r in current_results], indent=2, default=str),
                encoding="utf-8",
            )

    if args.concurrency > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = [pool.submit(execute_job, *job) for job in jobs]
            for fut in concurrent.futures.as_completed(futures):
                results.append(fut.result())
                _save_incremental(results)
    else:
        for job in jobs:
            results.append(execute_job(*job))
            _save_incremental(results)

    print()
    if drivers:
        print(render_summary_table(generate_comparison_summary(by_harness(results))))
        print()
        print(render_harness_comparison(results, baseline=drivers[0].harness_name))
    else:
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
