"""The offload experiment compares Claude alone with Claude + blyte, so the harness comparison
splits the orchestrator's (frontier) cost from blyte's (implementer) cost (2026-09-27)."""

import pytest

from lab.engine.budget_policy import RunTelemetry
from lab.engine.harnesses import BARE_ARM, compare_harnesses, render_harness_comparison


def _run(task: str, harness: str, cost: float, **extra: float) -> RunTelemetry:
    return RunTelemetry(
        task_id=task, arm=BARE_ARM, passed=True, wall_clock_sec=10.0, cost_usd=cost,
        input_tokens=100, output_tokens=10, extra={"harness": harness, **extra},
    )


RUNS = [
    _run("t1", "claude", 3.0),
    _run("t1", "claude+blyte[g]", 2.0, frontier_cost_usd=1.5, implementer_cost_usd=0.5, dispatches=2),
    _run("t2", "claude", 4.0),
    _run("t2", "claude+blyte[g]", 1.0, frontier_cost_usd=0.75, implementer_cost_usd=0.25, dispatches=1),
    _run("t2", "claude+blyte[g]", 3.0, frontier_cost_usd=2.25, implementer_cost_usd=0.75, dispatches=3),
    _run("t1", "blyte", 1.0),
]


def test_the_comparison_sums_mean_split_cost_per_paired_task() -> None:
    cmp = compare_harnesses(RUNS, baseline="claude")
    e = cmp["claude+blyte[g]"]
    assert e["frontier_cost_usd"] == pytest.approx(1.5 + 1.5)
    assert e["implementer_cost_usd"] == pytest.approx(0.5 + 0.5)
    assert e["dispatches"] == pytest.approx(2 + 2)
    assert cmp["blyte"]["frontier_cost_usd"] is None
    assert cmp["blyte"]["dispatches"] is None


def test_the_table_shows_split_cost_before_time_and_blanks_without_it() -> None:
    text = render_harness_comparison(RUNS, baseline="claude")
    assert "| Cost ($) | Frontier cost ($) | Implementer cost ($) | Dispatches | Baseline time (s) |" in text
    rows = {line.split(" | ")[0]: line for line in text.splitlines() if line.startswith("| ")}
    assert "| 3.00 | 1.00 | 4 | 20 | 20 |" in rows["| claude+blyte[g]"]
    assert "| 1.00 |  |  |  | 10 | 10 |" in rows["| blyte"]
    sep = next(line for line in text.splitlines() if line.startswith("|---"))
    assert sep.count("|") == 14
