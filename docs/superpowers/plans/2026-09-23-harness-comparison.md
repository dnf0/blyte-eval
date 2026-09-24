# Harness-vs-Harness Comparison Implementation Plan

> **For agentic workers:** Execution is delegated to headless `agy`, one task per dispatch; Claude reviews each task before the next is sent. Steps use checkbox (`- [ ]`) syntax for tracking. Do NOT `git push` or open PRs; commit locally only. NEVER start a benchmark run or call a model API: tests use stubs only.

**Goal:** Make "harness against harness on the same bare task" the evaluation's first-class question: `paired_run.py --harnesses agy superstate[state-only] superstate[state-only,tdd]`.

**Why:** The arm table (`vanilla`, `superpowers`, `superstate_mcp`, `superstate_daemon`, …) comes from the bolt-on era, when the question was "what does a layer add to agy". Superstate is now a harness in its own right. So what matters is how harnesses compare, and a harness's settings are part of its name. Today a native run has to go through the `vanilla` arm, one driver per invocation, and the reporter looks for a `vanilla` baseline arm. Every native smoke run therefore ended with "No paired results".

**Architecture:**
- A new module, `lab/engine/harnesses.py`, parses harness specs, builds a driver for each, and pairs results by task against the first harness.
- `paired_run.py` gains `--harnesses`. Each harness runs through a pass-through arm renamed `bare`, which reuses `VanillaAdapter`.
- `runner.run_task` already takes a driver per call and records `extra.harness`, so the runner only gains the `bare` alias.
- `CLAUDE.md` marks the arm table as legacy.

**Tech Stack:** Python 3.12, pytest, ruff, pyright (basic), uv.

## Global Constraints

- Base branch: `feat/native-driver-tdd-gate` (PR #28). The task runs in `/Users/danielfisher/repos/superstate-eval--<task>` on branch `wip/<task>`. Run `uv sync` first.
- `make lint && make test` before committing. Known pre-existing failures that are not yours: E402s in `scripts/paired_run.py`, 7 pyright errors in `tests/test_arm_input_parity.py`/`tests/test_superstate_daemon_adapter.py`, and `tests/test_governor_sizing.py::test_heavier_tasks_lower_the_concurrency_ceiling`. Report them; do not fix them.
- The existing `--arms` path must behave exactly as before.

---

### Task 1: `--harnesses`, the `bare` arm, and per-task harness pairing

**Files:**
- Create: `lab/engine/harnesses.py`
- Modify: `lab/engine/runner.py`, `scripts/paired_run.py`, `CLAUDE.md`
- Test: `tests/test_harnesses.py` (create)

- [ ] **Step 1: Write the failing tests.** Create `tests/test_harnesses.py`:

```python
"""Harness-vs-harness comparison: specs, drivers, and per-task pairing. No model or Docker."""

from __future__ import annotations

from pathlib import Path
import stat

import pytest

from lab.engine.adapters.vanilla import VanillaAdapter
from lab.engine.budget_policy import RunTelemetry
from lab.engine.harnesses import (
    BARE_ARM,
    HarnessSpecError,
    build_harness,
    by_harness,
    compare_harnesses,
    parse_harness_spec,
    render_harness_comparison,
)
from lab.engine.runner import AblationRunner

MODEL = "gemini-3.8-flash-high"


def _run(task: str, harness: str, passed: bool, cost: float = 1.0) -> RunTelemetry:
    return RunTelemetry(
        task_id=task,
        arm=BARE_ARM,
        passed=passed,
        wall_clock_sec=10.0,
        cost_usd=cost,
        input_tokens=100,
        output_tokens=10,
        extra={"harness": harness},
    )


@pytest.fixture
def superstate_stub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    stub = tmp_path / "superstate"
    stub.write_text("#!/bin/sh\nexit 0\n")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("SUPERSTATE_BIN", str(stub))
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    return stub


def test_parse_accepts_bare_names_and_superstate_options() -> None:
    assert parse_harness_spec("agy") == ("agy", [])
    assert parse_harness_spec("claude") == ("claude", [])
    assert parse_harness_spec("superstate") == ("superstate", [])
    assert parse_harness_spec("superstate[conversational,no-loop-breaker,tdd]") == (
        "superstate",
        ["conversational", "no-loop-breaker", "tdd"],
    )


@pytest.mark.parametrize(
    "spec",
    [
        "vanilla",
        "agy[tdd]",
        "superstate[fast]",
        "superstate[state-only,conversational]",
        "superstate state-only",
        "",
    ],
)
def test_parse_rejects_anything_else(spec: str) -> None:
    with pytest.raises(HarnessSpecError):
        parse_harness_spec(spec)


def test_superstate_specs_build_drivers_named_by_their_settings(superstate_stub: Path) -> None:
    assert build_harness("superstate", MODEL).harness_name == "superstate[state-only]"
    built = build_harness("superstate[conversational,no-loop-breaker,tdd]", MODEL)
    assert built.harness_name == "superstate[conversational,no-loop-breaker,tdd]"
    assert built.model == MODEL


def test_claude_refuses_a_gemini_model() -> None:
    with pytest.raises(HarnessSpecError, match="Claude model"):
        build_harness("claude", MODEL)


def test_the_bare_arm_is_the_pass_through_adapter() -> None:
    assert isinstance(AblationRunner._get_adapter(None, BARE_ARM), VanillaAdapter)  # type: ignore[arg-type]


def test_harnesses_pair_by_task_against_the_baseline() -> None:
    runs = [
        _run("t1", "agy", True, cost=1.0),
        _run("t1", "superstate[state-only]", True, cost=2.0),
        _run("t2", "agy", False, cost=1.0),
        _run("t2", "superstate[state-only]", True, cost=3.0),
        # No baseline run for t3: excluded, never compared against nothing.
        _run("t3", "superstate[state-only]", True, cost=5.0),
    ]
    cmp = compare_harnesses(runs, baseline="agy")
    assert list(cmp) == ["superstate[state-only]"]
    e = cmp["superstate[state-only]"]
    assert e["tasks"] == 2
    assert e["baseline_passes"] == 1
    assert e["passes"] == 2
    assert (e["gained"], e["lost"]) == (1, 0)
    assert e["baseline_cost_usd"] == pytest.approx(2.0)
    assert e["cost_usd"] == pytest.approx(5.0)


def test_repeats_count_as_a_pass_rate_per_task() -> None:
    runs = [
        _run("t1", "agy", True),
        _run("t1", "agy", False),
        _run("t1", "superstate[state-only]", True),
        _run("t1", "superstate[state-only]", True),
    ]
    e = compare_harnesses(runs, baseline="agy")["superstate[state-only]"]
    assert e["baseline_passes"] == pytest.approx(0.5)
    assert e["passes"] == pytest.approx(1.0)
    assert (e["gained"], e["lost"]) == (1, 0)


def test_by_harness_relabels_copies_and_leaves_results_untouched() -> None:
    runs = [_run("t1", "agy", True)]
    relabelled = by_harness(runs)
    assert relabelled[0].arm == "agy"
    assert runs[0].arm == BARE_ARM


def test_render_names_the_baseline_and_says_so_when_nothing_pairs() -> None:
    runs = [_run("t1", "agy", True), _run("t1", "superstate[state-only]", False)]
    text = render_harness_comparison(runs, baseline="agy")
    assert "against `agy`" in text
    assert "| superstate[state-only] | 1 |" in text
    empty = render_harness_comparison([_run("t1", "agy", True)], baseline="agy")
    assert empty.startswith("No paired results")


def test_paired_run_accepts_harnesses() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "paired_run", Path(__file__).resolve().parent.parent / "scripts" / "paired_run.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    args = module.build_parser().parse_args(
        ["--harnesses", "agy", "superstate[state-only]", "superstate[state-only,tdd]"]
    )
    assert args.harnesses == ["agy", "superstate[state-only]", "superstate[state-only,tdd]"]
    assert module.build_parser().parse_args([]).harnesses is None
```

- [ ] **Step 2: Run to confirm they fail.** Run: `uv run pytest -q tests/test_harnesses.py`. Expected: collection error, `ModuleNotFoundError: No module named 'lab.engine.harnesses'`.

- [ ] **Step 3: Create the module.** Create `lab/engine/harnesses.py`:

```python
"""Harness-vs-harness comparison: the evaluation's current question.

Superstate is a harness in its own right, so the question is no longer "what does a layer add to
agy" (the arm table in CLAUDE.md, kept for reproducing bolt-on-era results) but "how do harnesses
compare on the same bare task, model and sealed grader". Every harness runs through the `bare`
pass-through arm: the task instruction untouched, guidance files stripped, no gate from the
evaluation. Anything a harness does beyond that (its loop, context strategy, its own gate) is part
of the harness, and is spelled out in its name, e.g. `superstate[state-only,tdd]`.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from lab.engine.budget_policy import RunTelemetry

#: The pass-through arm every harness runs under. An alias of the legacy `vanilla` adapter.
BARE_ARM = "bare"

_SPEC_RE = re.compile(r"^(?P<name>[a-z]+)(?:\[(?P<opts>[a-z,-]*)\])?$")
_SUPERSTATE_OPTIONS = ("state-only", "conversational", "no-loop-breaker", "tdd")


class HarnessSpecError(ValueError):
    """A harness spec that cannot be turned into a valid measurement."""


def parse_harness_spec(spec: str) -> tuple[str, list[str]]:
    """Split `superstate[conversational,tdd]` into `("superstate", ["conversational", "tdd"])`."""
    m = _SPEC_RE.match(spec.strip())
    if not m:
        raise HarnessSpecError(
            f"not a harness spec: {spec!r} (expected e.g. agy, superstate[state-only,tdd])"
        )
    name = m.group("name")
    opts = [o for o in (m.group("opts") or "").split(",") if o]
    if name in ("agy", "claude"):
        if opts:
            raise HarnessSpecError(f"{name} takes no options, got {opts}")
        return name, opts
    if name == "superstate":
        unknown = [o for o in opts if o not in _SUPERSTATE_OPTIONS]
        if unknown:
            raise HarnessSpecError(
                f"unknown superstate option(s) {unknown}; known: {list(_SUPERSTATE_OPTIONS)}"
            )
        if "state-only" in opts and "conversational" in opts:
            raise HarnessSpecError("choose one context: state-only or conversational")
        return name, opts
    raise HarnessSpecError(f"unknown harness {name!r}; known: agy, claude, superstate")


def build_harness(spec: str, model: str, report_dir: Optional[Path] = None) -> Any:
    """The driver for one harness spec. Every harness gets the same model string."""
    name, opts = parse_harness_spec(spec)
    if name == "agy":
        from lab.engine.drivers.agy_cli import AgyCliDriver

        return AgyCliDriver(model=model)
    if name == "claude":
        if model.startswith("gemini"):
            raise HarnessSpecError(
                f"claude needs a Claude model, got {model!r}; compare it in a separate run "
                "with --model claude-…, since harnesses in one run share a model"
            )
        from lab.engine.drivers.claude_cli import ClaudeCliDriver

        return ClaudeCliDriver(model=model)
    from lab.engine.drivers.superstate_native import SuperstateNativeDriver

    return SuperstateNativeDriver(
        model=model,
        context="conversational" if "conversational" in opts else "state-only",
        loop_breaker="no-loop-breaker" not in opts,
        gate="tdd" if "tdd" in opts else None,
        report_dir=report_dir,
    )


def harness_of(run: RunTelemetry) -> str:
    return str((run.extra or {}).get("harness") or "unknown")


def by_harness(runs: List[RunTelemetry]) -> List[RunTelemetry]:
    """Copies of `runs` labelled by harness, so arm-keyed summaries group by harness."""
    return [replace(r, arm=harness_of(r)) for r in runs]


def compare_harnesses(runs: List[RunTelemetry], baseline: str) -> Dict[str, Dict[str, Any]]:
    """Pair every harness with `baseline`, task by task.

    Repeats count as a pass rate per task. A task the baseline did not run is excluded, never
    compared against nothing.
    """
    cells: Dict[str, Dict[str, List[RunTelemetry]]] = {}
    for r in runs:
        cells.setdefault(r.task_id, {}).setdefault(harness_of(r), []).append(r)

    out: Dict[str, Dict[str, Any]] = {}
    for by_h in cells.values():
        base = by_h.get(baseline)
        if not base:
            continue
        b_rate = sum(x.passed for x in base) / len(base)
        b_cost = sum(x.cost_usd for x in base) / len(base)
        for h, h_runs in by_h.items():
            if h == baseline:
                continue
            h_rate = sum(x.passed for x in h_runs) / len(h_runs)
            e = out.setdefault(
                h,
                {
                    "tasks": 0,
                    "baseline_passes": 0.0,
                    "passes": 0.0,
                    "gained": 0,
                    "lost": 0,
                    "baseline_cost_usd": 0.0,
                    "cost_usd": 0.0,
                },
            )
            e["tasks"] += 1
            e["baseline_passes"] += b_rate
            e["passes"] += h_rate
            e["gained"] += int(h_rate > b_rate)
            e["lost"] += int(h_rate < b_rate)
            e["baseline_cost_usd"] += b_cost
            e["cost_usd"] += sum(x.cost_usd for x in h_runs) / len(h_runs)
    return out


def render_harness_comparison(runs: List[RunTelemetry], baseline: str) -> str:
    cmp = compare_harnesses(runs, baseline)
    if not cmp:
        return f"No paired results: no task was run by both `{baseline}` and another harness."
    lines = [
        f"## Harnesses against `{baseline}` (paired by task; same model, prompt and grader)",
        "",
        "| Harness | Paired tasks | Baseline passes | Passes | Gained | Lost | Baseline cost ($) | Cost ($) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for h in sorted(cmp):
        e = cmp[h]
        lines.append(
            f"| {h} | {e['tasks']} | {e['baseline_passes']:g} | {e['passes']:g} | "
            f"{e['gained']} | {e['lost']} | {e['baseline_cost_usd']:.2f} | {e['cost_usd']:.2f} |"
        )
    lines += [
        "",
        "Small n cannot support a claim: report the paired rows, not a headline rate.",
    ]
    return "\n".join(lines)
```

- [ ] **Step 4: Add the `bare` arm.** In `lab/engine/runner.py`, in `_get_adapter`, replace `        if arm == "vanilla":` with `        if arm in ("vanilla", "bare"):`.

- [ ] **Step 5: Wire `paired_run.py`.**
  1. After the line `from lab.engine.drivers.superstate_native import SuperstateNativeDriver`, add:

```python
from lab.engine.harnesses import BARE_ARM, build_harness, by_harness, render_harness_comparison
```

  2. Directly after the `--gate` argument (both of its lines), add:

```python
    ap.add_argument("--harnesses", nargs="+", default=None,
                    help="Harness-vs-harness mode: compare these harnesses on the bare task, first "
                         "is the baseline, e.g. agy superstate[state-only] superstate[state-only,tdd]. "
                         "Replaces --arms, --driver, --context, --gate and --no-loop-breaker")
```

  3. Replace the line `    if args.driver == "claude":` (the first line of the driver-selection block) with:

```python
    drivers: list[Any] = []
    if args.harnesses:
        if (
            args.driver != "agy"
            or args.context != "state-only"
            or args.gate != "none"
            or args.no_loop_breaker
        ):
            logger.error(
                "--harnesses spells each harness's settings in its name "
                "(e.g. superstate[conversational,tdd]); do not combine it with --driver, "
                "--context, --gate or --no-loop-breaker."
            )
            return 1
        report_dir = (
            args.out.with_suffix(".native_reports") if args.out
            else args.workspace_root / "native_reports"
        )
        drivers = [build_harness(s, args.model, report_dir) for s in args.harnesses]
        driver = drivers[0]
    elif args.driver == "claude":
```

  4. Directly after the line `budget_label = f"{args.budget_sec:.0f}s" if args.budget_sec else "task-default"`, add:

```python
    if drivers:
        total_runs = len(tasks) * len(drivers) * args.repeats
        arms_label = f"{BARE_ARM} x " + ", ".join(d.harness_name for d in drivers)
```

  5. Replace the whole jobs block

```python
    jobs = []
    for task in tasks:
        for arm, reps in parsed_arms:
            for rep in range(1, reps + 1):
                jobs.append((task, arm, rep, reps))
```

     with

```python
    jobs = []
    if drivers:
        for task in tasks:
            for drv in drivers:
                for rep in range(1, args.repeats + 1):
                    jobs.append((task, BARE_ARM, rep, args.repeats, drv))
    else:
        for task in tasks:
            for arm, reps in parsed_arms:
                for rep in range(1, reps + 1):
                    jobs.append((task, arm, rep, reps, driver))
```

  6. Replace the whole `def execute_job(t: Any, a: str, r: int, total_reps: int) -> Any:` function with:

```python
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
```

  7. Replace `futures = [pool.submit(execute_job, t, a, r, reps) for t, a, r, reps in jobs]` with `futures = [pool.submit(execute_job, *job) for job in jobs]`, and replace

```python
        for t, a, r, reps in jobs:
            results.append(execute_job(t, a, r, reps))
```

     with

```python
        for job in jobs:
            results.append(execute_job(*job))
```

  8. Replace

```python
    print()
    print(render_summary_table(generate_comparison_summary(results)))
    print()
    print(render_lift_report(results))
```

     with

```python
    print()
    if drivers:
        print(render_summary_table(generate_comparison_summary(by_harness(results))))
        print()
        print(render_harness_comparison(results, baseline=drivers[0].harness_name))
    else:
        print(render_summary_table(generate_comparison_summary(results)))
        print()
        print(render_lift_report(results))
```

- [ ] **Step 6: Mark the arm table as legacy in `CLAUDE.md`.**
  1. Directly above the line `## Arms — check the name before comparing anything`, insert:

```markdown
## Harnesses — the current comparison

Superstate is now a harness in its own right, so the question this evaluation answers is
**harness against harness** on the same bare task, model and sealed grader:

    python scripts/paired_run.py --harnesses agy superstate[state-only] superstate[state-only,tdd] --canary

The first harness is the baseline, and results pair by task (`lab/engine/harnesses.py`). Every
harness runs through the `bare` pass-through arm: the instruction untouched, guidance files
stripped, no gate from the evaluation. What a harness does beyond that is part of the harness
and is spelled out in its name, `superstate[<state-only|conversational>,no-loop-breaker,tdd]`.
`superstate[…,tdd]` gates **itself** by autonomous TDD. Compare it with agy as "a harness with
its own gate", not as an ungated run.

```

  2. Replace the heading line `## Arms — check the name before comparing anything` with `## Arms (legacy, bolt-on era) — check the name before comparing anything`, and directly below it insert:

```markdown

These arms measure a layer attached to agy or Claude Code: the question before superstate was a
harness. They stay runnable to reproduce past results. They are not the current design, and
`vanilla` survives only as the adapter behind `bare`.
```

- [ ] **Step 7: Run the tests.** Run: `uv run pytest -q tests/test_harnesses.py tests/test_superstate_native_driver.py`. Expected: 15 and 21 passed.

- [ ] **Step 8: Full check.** Run: `make lint && make test`. Expected: only the known pre-existing failures. Report the counts.

- [ ] **Step 9: Commit.**

```bash
git add lab/engine/harnesses.py lab/engine/runner.py scripts/paired_run.py CLAUDE.md tests/test_harnesses.py
git commit -m "feat(eval): harness-vs-harness comparison on the bare task (--harnesses)"
```
