# Per-Run Harness Metrics, Fold-Budget Option and Cost Cap Implementation Plan

> **For agentic workers:** Execution is delegated to headless `agy`, one task per dispatch; Claude reviews each task before the next is sent. Steps use checkbox (`- [ ]`) syntax for tracking. Do NOT `git push`, open PRs, start any paid or benchmark run, or edit FINDINGS.md or results/; commit locally only.

**Goal:** Every native superstate run records the diagnostics the harness comparison is decided on. Two harness settings become available:
- `superstate[...,fold-budget-16k]`, for the fold budget;
- `paired_run.py --max-cost-usd`, a per-run dollar cap for safety.

The diagnostics:
- reads, and re-reads of unchanged and of changed files;
- repeated shell/search commands;
- fold notes;
- cost per turn;
- fresh input split into calls whose prompt only grew (`appended`) and calls whose prompt was rewritten.

**Why:** FINDINGS 13.41–13.42 were computed by hand with a scratch script over event logs. The next measurement is 3 repeats × 4 cells × 2–3 tasks, so the numbers must come with the results. The superstate binary now reports `turn_usage` (per call: `input`, `cached`, `output`, `thinking`, `prompt_messages`, `appended`, `new_chars`), `fold_notes`, `fold_note_failures` and accepts `--fold-budget N` and `--max-cost-usd X`.

**Tech Stack:** Python 3, pytest, ruff, pyright (`uv run`).

## Global Constraints

- Base branch: `feat/run-metrics` (from `main`). The task runs in its own worktree on branch `wip/<task>`. Claude merges back.
- Before committing: `make lint && make test`. **Known pre-existing failure:** `tests/test_governor_sizing.py::test_heavier_tasks_lower_the_concurrency_ceiling` fails on `main` too (it depends on the host's free memory). Ignore it if it is the only failure, and report it.
- Existing tests must pass unmodified. Commit with the exact message below.

---

### Task 1: Run metrics, `fold-budget-Nk`, `--max-cost-usd`

**Files:**
- Modify: `lab/engine/adapters/base.py`, `lab/engine/drivers/superstate_native.py`, `lab/engine/harnesses.py`, `scripts/paired_run.py`
- Test: `tests/test_superstate_native_driver.py`, `tests/test_harnesses.py` (append only)

- [ ] **Step 1: Write the failing tests.**

Append to `tests/test_superstate_native_driver.py`:

```python
EVENTS = (
    "[Turn 1] \n"
    "● read a.py -> 10 lines read\n"
    "● read a.py -> 10 lines read\n"
    "● edit a.py -> replaced 1 line\n"
    "● read a.py -> 10 lines read\n"
    "● bash pytest -q -> exit 1\n"
    "\x1b[31m● bash pytest -q -> exit 1\x1b[0m\n"
    "● grep foo -> 2 matches\n"
)

TURN_USAGE = [
    {"turn": 1, "input": 1000, "cached": 0, "output": 5, "thinking": 0,
     "prompt_messages": 1, "appended": False, "new_chars": 4000},
    {"turn": 2, "input": 300, "cached": 900, "output": 5, "thinking": 0,
     "prompt_messages": 3, "appended": True, "new_chars": 800},
    {"turn": 3, "input": 5000, "cached": 100, "output": 5, "thinking": 0,
     "prompt_messages": 5, "appended": True, "new_chars": 400},
]


def test_run_metrics_counts_rereads_repeats_and_splits_fresh_input() -> None:
    from lab.engine.drivers.superstate_native import run_metrics

    m = run_metrics(_report(turns=3, fold_notes=2, fold_note_failures=1, turn_usage=TURN_USAGE), EVENTS)
    assert m["harness_turns"] == 3
    assert (m["fold_notes"], m["fold_note_failures"]) == (2, 1)
    assert (m["reads"], m["unchanged_rereads"], m["changed_rereads"]) == (3, 1, 1)
    assert m["repeated_commands"] == 1
    assert (m["appended_turns"], m["rewritten_turns"]) == (2, 1)
    assert m["fresh_on_appended"] == 5300
    assert m["new_tokens_est_on_appended"] == 300
    assert m["fresh_on_rewritten"] == 1000


def test_run_metrics_tolerates_an_old_report() -> None:
    from lab.engine.drivers.superstate_native import run_metrics

    m = run_metrics(_report(), "")
    assert m["reads"] == 0 and m["appended_turns"] == 0 and m["fold_notes"] == 0


def test_metrics_reach_the_task_result(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report(turns=3, turn_usage=TURN_USAGE), stdout=EVENTS)
    driver = _driver(tmp_path, stub, max_cost_usd=4.0)
    result = VanillaAdapter().execute(
        tmp_path, _task(tmp_path), driver, timeout_sec=60.0, container=FakeContainer()
    )
    assert result.provenance["unchanged_rereads"] == 1
    assert result.provenance["harness_turns"] == 3
    assert result.provenance["cost_per_turn"] == pytest.approx(result.cost_usd / 3, rel=1e-3)
    assert result.provenance["max_cost_usd"] == 4.0


def test_fold_budget_and_cost_cap_are_passed(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report())
    driver = _driver(tmp_path, stub, context="compact", fold_budget=16000, max_cost_usd=2.5)
    assert driver.harness_name == "superstate[compact,fold-budget-16k]"
    driver.run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer())
    [argv] = _calls(tmp_path)
    flags = argv[: argv.index("--")]
    assert flags[flags.index("--fold-budget") + 1] == "16000"
    assert flags[flags.index("--max-cost-usd") + 1] == "2.5"


def test_no_cap_and_no_budget_pass_no_flags(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report())
    _driver(tmp_path, stub).run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer())
    [argv] = _calls(tmp_path)
    assert "--fold-budget" not in argv and "--max-cost-usd" not in argv


def test_paired_run_accepts_a_cost_cap() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "paired_run", Path(__file__).resolve().parent.parent / "scripts" / "paired_run.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    args = module.build_parser().parse_args(
        ["--harnesses", "superstate[compact]", "--max-cost-usd", "3"]
    )
    assert args.max_cost_usd == 3.0
```

Append to `tests/test_harnesses.py`:

```python
def test_fold_budget_is_a_superstate_option(superstate_stub: Path) -> None:
    built = build_harness("superstate[compact,fold-notes,fold-budget-16k]", MODEL)
    assert built.harness_name == "superstate[compact,fold-notes,fold-budget-16k]"
    assert built.fold_budget == 16000
    with pytest.raises(HarnessSpecError, match="one fold budget"):
        parse_harness_spec("superstate[compact,fold-budget-16k,fold-budget-8k]")
    with pytest.raises(HarnessSpecError, match="unknown superstate option"):
        parse_harness_spec("superstate[compact,fold-budget-lots]")


def test_the_cost_cap_reaches_superstate_harnesses_only(superstate_stub: Path) -> None:
    assert build_harness("superstate[compact]", MODEL, max_cost_usd=2.0).max_cost_usd == 2.0
    assert build_harness("superstate[compact]", MODEL).max_cost_usd is None
```

- [ ] **Step 2: Run to confirm they fail.** Run: `uv run pytest -q tests/test_superstate_native_driver.py tests/test_harnesses.py`. Expected: the new tests fail (`run_metrics`, `fold_budget`, `max_cost_usd` do not exist). The existing tests pass.

- [ ] **Step 3: Metrics travel from driver to result.** In `lab/engine/adapters/base.py`:
  1. In `DriverTelemetry`, after `error_message`, add:

```python
    #: Harness-reported diagnostics for this invocation (merged into the result's provenance).
    metrics: Dict[str, Any] = field(default_factory=dict)
```

     Import `Dict`, `Any` and `field` if they are not already imported.
  2. In `TurnBasedAdapter`'s run method: directly before `for _ in range(self.max_turns):`, add `metrics: Dict[str, Any] = {}`. Directly after `last_response = telemetry.raw_response`, add `metrics.update(telemetry.metrics)`. In the final `return TaskRunResult(...)`, change `provenance=self.get_provenance(),` to `provenance={**self.get_provenance(), **metrics},`.

- [ ] **Step 4: `run_metrics` and the driver.** In `lab/engine/drivers/superstate_native.py`:
  1. Add at module level (with `import re` and `from collections import Counter` among the imports):

```python
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_TOOL_EVENT_RE = re.compile(r"^\s*● (\w+) (.*?) -> ")


def run_metrics(report: Dict[str, Any], events_text: str) -> Dict[str, Any]:
    """Diagnostics for comparing harness configurations, from the run report and event log.

    Re-reads of an unchanged file and repeated identical commands are work a context strategy
    should have made unnecessary (FINDINGS 13.33, 13.42). Fresh input is split by whether the
    call's prompt only grew (`appended`), where a prefix cache can serve all but the new part
    (`new_tokens_est_on_appended`, at 4 characters per token), or was rewritten (a fold), where
    a cache miss is expected. Tolerates reports that predate any of these fields.
    """
    usage = report.get("turn_usage") or []
    appended = [t for t in usage if t.get("appended")]
    rewritten = [t for t in usage if not t.get("appended")]
    reads = unchanged = changed = 0
    seen: set[str] = set()
    edited: set[str] = set()
    counts: Counter[tuple[str, str]] = Counter()
    for raw in events_text.splitlines():
        m = _TOOL_EVENT_RE.match(_ANSI_RE.sub("", raw))
        if not m:
            continue
        tool, target = m.group(1), m.group(2)
        counts[(tool, target)] += 1
        if tool == "read":
            reads += 1
            if target in seen:
                if target in edited:
                    changed += 1
                else:
                    unchanged += 1
            seen.add(target)
            edited.discard(target)
        elif tool in ("edit", "write"):
            edited.add(target)
    repeated = sum(
        c - 1 for (tool, _), c in counts.items() if c > 1 and tool in ("bash", "grep", "glob")
    )
    return {
        "harness_turns": int(report.get("turns") or 0),
        "fold_notes": int(report.get("fold_notes") or 0),
        "fold_note_failures": int(report.get("fold_note_failures") or 0),
        "reads": reads,
        "unchanged_rereads": unchanged,
        "changed_rereads": changed,
        "repeated_commands": repeated,
        "appended_turns": len(appended),
        "rewritten_turns": len(rewritten),
        "fresh_on_appended": sum(int(t.get("input", 0)) for t in appended),
        "new_tokens_est_on_appended": sum(int(t.get("new_chars", 0)) for t in appended) // 4,
        "fresh_on_rewritten": sum(int(t.get("input", 0)) for t in rewritten),
    }
```

  2. In `SuperstateNativeDriver.__init__`, after `fold_notes: bool = False,` add `fold_budget: Optional[int] = None,` and `max_cost_usd: Optional[float] = None,`. Store both (`self.fold_budget = fold_budget`, `self.max_cost_usd = max_cost_usd`). In the harness-name `config` list, append after the fold-notes entry: `+ ([f"fold-budget-{fold_budget // 1000}k"] if fold_budget else [])`. The cost cap is a safeguard, not a behaviour, and stays out of the name.
  3. In `build_command`, after the `--fold-notes` lines, add:

```python
        if self.fold_budget:
            cmd += ["--fold-budget", str(self.fold_budget)]
        if self.max_cost_usd is not None:
            cmd += ["--max-cost-usd", str(self.max_cost_usd)]
```

  4. In `run`, on the path that returns a `DriverTelemetry` from a readable report: compute the cost into a local `cost_usd = estimate_cost_usd(...)` (the same call as now), then build:

```python
        metrics = run_metrics(report, _text(stdout))
        if metrics["harness_turns"]:
            metrics["cost_per_turn"] = round(cost_usd / metrics["harness_turns"], 6)
        metrics["max_cost_usd"] = self.max_cost_usd
```

     Pass `cost_usd=cost_usd` and `metrics=metrics` to that `DriverTelemetry`.

- [ ] **Step 5: The harness spec and `paired_run.py`.** In `lab/engine/harnesses.py`:
  1. Change `_SPEC_RE`'s option class from `[a-z,-]*` to `[a-z0-9,-]*`. Add `_FOLD_BUDGET_RE = re.compile(r"fold-budget-(\d+)k")`.
  2. In `parse_harness_spec`'s superstate branch, compute `unknown = [o for o in opts if o not in _SUPERSTATE_OPTIONS and not _FOLD_BUDGET_RE.fullmatch(o)]`. After the one-context check, add:

```python
        budgets = [o for o in opts if _FOLD_BUDGET_RE.fullmatch(o)]
        if len(budgets) > 1:
            raise HarnessSpecError(f"choose one fold budget, got {budgets}")
```

  3. Give `build_harness` a keyword parameter `max_cost_usd: Optional[float] = None`. In the superstate branch, pass:

```python
        fold_budget=next(
            (int(m.group(1)) * 1000 for o in opts if (m := _FOLD_BUDGET_RE.fullmatch(o))), None
        ),
        max_cost_usd=max_cost_usd,
```

  4. In `scripts/paired_run.py`, add after the `--repeats` argument:

```python
    ap.add_argument("--max-cost-usd", type=float, default=None,
                    help="Per-run dollar cap passed to superstate harnesses (a safeguard; "
                         "the run stops itself and reports budget_exhausted)")
```

     Change `drivers = [build_harness(s, args.model, report_dir) for s in args.harnesses]` to pass `max_cost_usd=args.max_cost_usd`.

- [ ] **Step 6: Run the tests.** Run: `uv run pytest -q tests/test_superstate_native_driver.py tests/test_harnesses.py tests/test_adapters.py`. Expected: all pass.

- [ ] **Step 7: Full check.** Run: `make lint && make test`. Expected: lint clean. Tests pass except the known governor-sizing test.

- [ ] **Step 8: Commit.**

```bash
git add lab tests scripts
git commit -m "feat(eval): per-run harness metrics, fold-budget-Nk option, --max-cost-usd"
```
