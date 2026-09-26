# Time in the Harness Comparison — Implementation Plan

> **For agentic workers:** Implement exactly one task. Do NOT `git push`, open PRs, start any benchmark or paid run, or call any model API; commit locally only. This plan is shadow-run: agy and blyte each implement it independently.

**Goal:** The harness-vs-harness comparison reports wall time next to passes and cost, and a blyte
run's metrics carry the time breakdown and build that blyte's report now records.

**Why:** the comparison (`compare_harnesses` / `render_harness_comparison`) shows passes and cost
but not time, though speed is the main thing being compared (13.44–13.46 had to be tallied by hand).
blyte's `--report` now records `model_seconds`, `tools_seconds`, `gate_seconds`, `gate_attempts`,
`tool_counts` and `harness_build` (blyte #76, #77); `run_metrics` drops all of them.

**Tech Stack:** Python 3, pytest, ruff, pyright, `uv`.

## Global Constraints

- Work only in your own worktree (already on its own branch). Run `uv sync` first.
- Do NOT edit `FINDINGS.md`, `EXPERIMENTS.md`, `CLAUDE.md`/`AGENTS.md` or anything under `results/`.
- Existing tests must pass unmodified.
- Reports that predate the new blyte fields must still work (the fields are then `None` or `{}`).
- Commit with `--no-gpg-sign` and the exact message below.

---

### Task 1: Time in the comparison and the blyte metrics

**Files:** `lab/engine/harnesses.py`; `lab/engine/drivers/superstate_native.py`; new test `tests/test_harness_time.py`.

**What to add:**
- `compare_harnesses`: each harness entry gains `baseline_seconds` and `seconds`, accumulated per
  paired task exactly like `baseline_cost_usd` and `cost_usd` (the mean `wall_clock_sec` of that
  task's runs, summed over paired tasks).
- `render_harness_comparison`: two more columns after the cost columns, `Baseline time (s)` and
  `Time (s)`, formatted as whole seconds (`{:.0f}`).
- `run_metrics` (in `superstate_native.py`): also return `model_seconds`, `tools_seconds`,
  `gate_seconds` (floats or `None`), `gate_attempts` (int or `None`), `harness_build` (str or `None`)
  and `tool_counts` (dict, `{}` when absent), read from the report's top-level fields of the same names.

- [ ] **Step 1: Write the failing test.** Create `tests/test_harness_time.py`:

```python
"""Speed is the main thing the harness comparison is for, so it reports time, and a blyte run's
metrics keep the time breakdown and build from blyte's report (blyte #76, #77)."""

import pytest

from lab.engine.budget_policy import RunTelemetry
from lab.engine.drivers.superstate_native import run_metrics
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
```

- [ ] **Step 2: Run to confirm it fails.** Run: `uv run pytest -q tests/test_harness_time.py`. Expected: all four fail.

- [ ] **Step 3: Implement** the additions above.

- [ ] **Step 4: Verify.** Run `uv run pytest -q tests/test_harness_time.py tests/test_harnesses.py tests/test_superstate_native_driver.py` (all pass), then `make lint`.

- [ ] **Step 5: Commit.**

```bash
git add -A lab tests
git commit --no-gpg-sign -m "feat(eval): the harness comparison reports time; blyte metrics keep its time breakdown and build"
```
