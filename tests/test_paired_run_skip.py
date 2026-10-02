"""Tests for per-attempt logging and end-of-run skip summaries in paired_run."""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from lab.engine.budget_policy import RunTelemetry
from scripts.paired_run import format_attempt_log, print_skip_summary


def test_format_attempt_log_for_infra_skip() -> None:
    """An infra skip log line says 'skipped (infrastructure): <reason>' instead of 'passed=False'."""
    tel = RunTelemetry(
        task_id="canary/katex",
        arm="vanilla",
        passed=False,
        cost_usd=0.0,
        wall_clock_sec=5.0,
        input_tokens=0,
        output_tokens=0,
        failure_reason="infrastructure: Failed to acquire concurrency governor slot within timeout",
        extra={"infra_skip": True},
    )

    msg = format_attempt_log(tel, label="vanilla", rep_tag=" [run 1/2]", elapsed_sec=5.0)
    assert "skipped (infrastructure): Failed to acquire concurrency governor slot within timeout" in msg
    assert "passed=" not in msg


def test_format_attempt_log_for_regular_attempt() -> None:
    """A regular failed attempt says 'passed=False' with failure reason."""
    tel = RunTelemetry(
        task_id="canary/katex",
        arm="vanilla",
        passed=False,
        cost_usd=0.02,
        wall_clock_sec=12.0,
        input_tokens=100,
        output_tokens=20,
        failure_reason="AssertionError: tests failed",
        extra={"turns": 3},
    )

    msg = format_attempt_log(tel, label="vanilla", rep_tag="", elapsed_sec=12.0)
    assert "passed=False" in msg
    assert "skipped (infrastructure)" not in msg
    assert "AssertionError: tests failed" in msg


def test_print_skip_summary_with_all_attempts_skipped() -> None:
    """End-of-run summary prints how many were skipped and notes tasks where every attempt skipped."""
    results = [
        # task1 has both attempts skipped
        RunTelemetry(
            task_id="task1",
            arm="vanilla",
            passed=False,
            cost_usd=0.0,
            wall_clock_sec=1.0,
            input_tokens=0,
            output_tokens=0,
            failure_reason="infrastructure: Failed to acquire concurrency governor slot within timeout",
            extra={"infra_skip": True},
        ),
        RunTelemetry(
            task_id="task1",
            arm="superpowers",
            passed=False,
            cost_usd=0.0,
            wall_clock_sec=1.0,
            input_tokens=0,
            output_tokens=0,
            failure_reason="infrastructure: WorkspaceSeedError: stream error",
            extra={"infra_skip": True},
        ),
        # task2 has 1 pass and 1 skip
        RunTelemetry(
            task_id="task2",
            arm="vanilla",
            passed=True,
            cost_usd=0.20,
            wall_clock_sec=10.0,
            input_tokens=100,
            output_tokens=10,
        ),
        RunTelemetry(
            task_id="task2",
            arm="superpowers",
            passed=False,
            cost_usd=0.0,
            wall_clock_sec=1.0,
            input_tokens=0,
            output_tokens=0,
            failure_reason="infrastructure: governor slot timeout",
            extra={"infra_skip": True},
        ),
    ]

    buf = io.StringIO()
    with redirect_stdout(buf):
        print_skip_summary(results)
    output = buf.getvalue()

    assert "3 skipped (infrastructure)" in output
    assert "Every attempt of task 'task1' was skipped (infrastructure)" in output
    # task2 had one pass, so its attempts were not all skipped
    assert "Every attempt of task 'task2'" not in output
