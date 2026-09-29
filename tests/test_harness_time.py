"""Speed is the main thing the harness comparison is for, so it reports time, and a blyte run's
metrics keep the time breakdown and build from blyte's report (blyte #76, #77)."""

import pytest

from lab.engine.budget_policy import RunTelemetry
from lab.engine.drivers.blyte_native import run_metrics
from lab.engine.harnesses import BARE_ARM, compare_harnesses, render_harness_comparison


def _run(task: str, harness: str, seconds: float, cost: float = 1.0) -> RunTelemetry:
    return RunTelemetry(
        task_id=task, arm=BARE_ARM, passed=True, wall_clock_sec=seconds, cost_usd=cost,
        input_tokens=100, output_tokens=10, extra={"harness": harness},
    )


def test_the_comparison_sums_mean_time_per_paired_task() -> None:
    runs = [
        _run("t1", "agy", 100.0), _run("t1", "agy", 300.0),     # mean 200
        _run("t1", "blyte[folded]", 80.0),
        _run("t2", "agy", 50.0), _run("t2", "blyte[folded]", 40.0),
        _run("t3", "blyte[folded]", 999.0),                      # unpaired: excluded
    ]
    e = compare_harnesses(runs, baseline="agy")["blyte[folded]"]
    assert e["baseline_seconds"] == pytest.approx(250.0)
    assert e["seconds"] == pytest.approx(120.0)


def test_the_rendered_table_shows_time() -> None:
    text = render_harness_comparison(
        [_run("t1", "agy", 200.0), _run("t1", "blyte[folded]", 80.0)], baseline="agy"
    )
    assert "Baseline time (s)" in text and "Time (s)" in text
    row = next(line for line in text.splitlines() if line.startswith("| blyte[folded] |"))
    assert row.rstrip().endswith("| 200 | 80 |"), row


def test_run_metrics_keeps_the_time_breakdown_and_build() -> None:
    report = {
        "schema_version": 1, "outcome": "verified", "turns": 5, "turn_usage": [],
        "model_seconds": 61.5, "tools_seconds": 20.25, "gate_seconds": 33.0, "gate_attempts": 2,
        "tool_counts": {"bash": 4, "read": 3}, "harness_build": "015f0fc",
    }
    m = run_metrics(report, "")
    assert (m["model_seconds"], m["tools_seconds"], m["gate_seconds"]) == (61.5, 20.25, 33.0)
    assert m["gate_attempts"] == 2
    assert m["tool_counts"] == {"bash": 4, "read": 3}
    assert m["harness_build"] == "015f0fc"


def test_run_metrics_tolerates_a_report_without_them() -> None:
    m = run_metrics({"schema_version": 1, "outcome": "verified", "turns": 1}, "")
    assert m["model_seconds"] is None and m["harness_build"] is None
    assert m["tool_counts"] == {}
