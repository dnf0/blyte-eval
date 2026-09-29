#!/usr/bin/env python3
"""Run a live single-task smoke test using AblationRunner and AgyCliDriver."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys

from lab.benchmarks.task_loader import load_task_from_dir
from lab.engine.drivers.agy_cli import AgyCliDriver
from lab.engine.runner import AblationRunner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("blyte_eval.smoke_cli")


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test for AgyCliDriver with AblationRunner")
    parser.add_argument(
        "--task-path",
        type=Path,
        default=Path.home()
        / ".cache/agent-rules/frontier-eval/tasks/fastapi-deprecation-response-headers",
        help="Path to benchmark task directory",
    )
    parser.add_argument(
        "--arm",
        type=str,
        default="vanilla",
        choices=["vanilla", "superpowers", "blyte"],
        help="Evaluation arm to run",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gemini-3.8-flash-high",
        help="Model to pass to agy",
    )
    parser.add_argument(
        "--budget-sec",
        type=float,
        default=600.0,
        help="Base budget in seconds for smoke test",
    )
    args = parser.parse_args()

    task_dir: Path = args.task_path
    if not task_dir.is_dir():
        logger.error("Task directory not found: %s", task_dir)
        sys.exit(1)

    logger.info("=" * 70)
    logger.info("LIVE SMOKE TEST: Antigravity CLI Driver (agy)")
    logger.info("=" * 70)

    task = load_task_from_dir(task_dir)
    logger.info("Task ID:    %s", task.id)
    logger.info("Image:      %s", task.docker_image)
    logger.info("Arm:        %s", args.arm)
    logger.info("Model:      %s", args.model)
    logger.info("Base Budget: %.1fs", args.budget_sec)
    logger.info("-" * 70)

    driver = AgyCliDriver(model=args.model)
    runner = AblationRunner(default_driver=driver)

    result = runner.run_task(
        task_id=task.id,
        arm=args.arm,
        image=task.docker_image,
        base_budget_sec=args.budget_sec,
        task_spec=task,
    )

    logger.info("=" * 70)
    logger.info("SMOKE TEST COMPLETE")
    logger.info("=" * 70)
    logger.info("Passed:       %s", result.passed)
    logger.info("Wall Clock:   %.2fs", result.wall_clock_sec)
    logger.info("Cost USD:     $%.4f", result.cost_usd)
    logger.info("Input Tokens: %d", result.input_tokens)
    logger.info("Output Tokens:%d", result.output_tokens)
    logger.info("Failure:      %s", result.failure_reason)
    logger.info("Patch Path:   %s", result.extra.get("patch_path"))
    logger.info("Reward:       %s", result.extra.get("reward"))
    logger.info("Turns:        %s", result.extra.get("turns"))

    # Extract granular verifier and test passing metrics from telemetry extra
    test_pass_fraction = result.extra.get("test_pass_fraction")
    f2p_fraction = result.extra.get("f2p_fraction")
    p2p_fraction = result.extra.get("p2p_fraction")
    tests_passed = result.extra.get("tests_passed")
    tests_total = result.extra.get("tests_total")

    # Format and report overall test pass fraction with passed/total test counts
    if test_pass_fraction is not None:
        if tests_passed is not None and tests_total is not None:
            logger.info(
                "Test Pass Frac: %.2f%% (%d/%d)",
                test_pass_fraction * 100,
                tests_passed,
                tests_total,
            )
        else:
            logger.info("Test Pass Frac: %.2f%%", test_pass_fraction * 100)
    else:
        logger.info("Test Pass Frac: N/A")

    # Report fail-to-pass and pass-to-pass suite breakdown if present
    f2p_display = f"{f2p_fraction * 100:.2f}%" if f2p_fraction is not None else "N/A"
    p2p_display = f"{p2p_fraction * 100:.2f}%" if p2p_fraction is not None else "N/A"
    logger.info("F2P Fraction:  %s", f2p_display)
    logger.info("P2P Fraction:  %s", p2p_display)


if __name__ == "__main__":
    main()
