#!/usr/bin/env python3
"""Run a pilot benchmark showdown across Vanilla, Superpowers, and Superstate.

Verifies end-to-end task loading, container isolation, adapter workflows,
mechanical continuation, and blind patch/reward extraction.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys

from lab.benchmarks.task_loader import load_task_from_dir
from lab.engine.pilot import PilotShowdownRunner
from lab.sandbox.docker_manager import DockerManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("superstate_eval.pilot_cli")


def main() -> None:
    parser = argparse.ArgumentParser(description="Pilot Showdown Dry-Run across evaluation arms")
    parser.add_argument(
        "--task-path",
        type=Path,
        default=Path.home()
        / ".cache/agent-rules/frontier-eval/tasks/fastapi-deprecation-response-headers",
        help="Path to benchmark task directory containing task.toml and instruction.md",
    )
    parser.add_argument(
        "--arms",
        nargs="+",
        default=["vanilla", "superpowers"],
        help="Evaluation arms to execute",
    )
    parser.add_argument(
        "--live-docker",
        action="store_true",
        help="Run real Docker containers instead of mock container sandbox",
    )
    parser.add_argument(
        "--logs-dir",
        type=Path,
        default=Path("/tmp/superstate_pilot_logs"),
        help="Root directory for isolated host log volumes",
    )
    args = parser.parse_args()

    task_dir: Path = args.task_path
    if not task_dir.is_dir():
        logger.error(f"Task directory does not exist: {task_dir}")
        sys.exit(1)

    logger.info("=" * 80)
    logger.info("SUPERSTATE-EVAL PILOT SHOWDOWN")
    logger.info("=" * 80)

    task = load_task_from_dir(task_dir)
    logger.info(f"Loaded Task: {task.id}")
    logger.info(f"Image: {task.docker_image}")
    logger.info(f"Base Commit: {task.base_commit}")
    logger.info(f"Timeout: {task.timeout_sec}s (Agent: {task.agent_timeout_sec}s)")
    logger.info(f"Arms: {', '.join(args.arms)}")
    logger.info("-" * 80)

    docker_mgr = DockerManager() if args.live_docker else None
    runner = PilotShowdownRunner(docker_manager=docker_mgr, logs_root=args.logs_dir)

    summary = runner.run_pilot(
        task=task,
        arms=args.arms,
        mock_mode=not args.live_docker,
    )

    logger.info("=" * 80)
    logger.info(f"PILOT SHOWDOWN COMPLETE FOR TASK: {summary['task_id']}")
    if summary.get("mock_mode"):
        logger.warning(
            "SIMULATED RUN (mock_mode=True): the sandbox verifier always reports success. "
            "These rows exercise the pipeline and are NOT evaluation results. "
            "Use --live-docker for a real run."
        )
    logger.info("=" * 80)

    headers = f"{'ARM':<15} | {'SUCCESS':<8} | {'TURNS':<6} | {'DURATION':<10} | {'REWARD':<8} | {'PATCH PATH'}"
    logger.info(headers)
    logger.info("-" * 80)

    for r in summary["results"]:
        status = "PASS" if r.get("passed", r.get("success", False)) else "FAIL"
        duration = r.get("duration_sec", r.get("duration_seconds", 0.0))
        row = (
            f"{r['arm']:<15} | {status:<8} | {r['turns']:<6} | "
            f"{duration:<9.1f}s | {str(r.get('reward')):<8} | {r.get('patch_path')}"
        )
        logger.info(row)

    logger.info("=" * 80)
    print("\nFull JSON Summary:")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
