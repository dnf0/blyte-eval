# State-Window Harness Option Implementation Plan

> **For agentic workers:** Execution is delegated to headless `agy`, one task per dispatch; Claude reviews each task before the next is sent. Steps use checkbox (`- [ ]`) syntax for tracking. Do NOT `git push` or open PRs; commit locally only. NEVER start a benchmark run or call a model API: tests use stubs only.

**Goal:** Accept `superstate[state-window]` as a harness: the native harness's new context strategy, which keeps the last 8 tool results in view. The superstate side (`--context state-window`) is being built in parallel.

**Why:** It lets the next canary compare `agy`, `superstate[state-only]` and `superstate[state-window]` on the same task, model and grader. That tests whether `state-only`'s one-turn memory is what makes the native harness repeat itself (FINDINGS §13.33).

**Tech Stack:** Python 3.12, pytest, ruff, pyright (basic), uv.

## Global Constraints

- Base branch: `feat/native-driver-tdd-gate` (PR #28). The task runs in `/Users/danielfisher/repos/superstate-eval--<task>` on branch `wip/<task>`. Run `uv sync` first.
- `make lint && make test` before committing. Known pre-existing failures that are not yours: E402s in `scripts/paired_run.py`, and 7 pyright errors in `tests/test_arm_input_parity.py`/`tests/test_superstate_daemon_adapter.py`. Report them; do not fix them.

---

### Task 1: `state-window` as a superstate context option

**Files:**
- Modify: `lab/engine/drivers/superstate_native.py`, `lab/engine/harnesses.py`, `scripts/paired_run.py`
- Test: `tests/test_harnesses.py` (append), `tests/test_superstate_native_driver.py` (append)

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_harnesses.py`:

```python


def test_state_window_is_a_superstate_context(superstate_stub: Path) -> None:
    assert parse_harness_spec("superstate[state-window,tdd]") == (
        "superstate",
        ["state-window", "tdd"],
    )
    assert build_harness("superstate[state-window]", MODEL).harness_name == "superstate[state-window]"


@pytest.mark.parametrize(
    "spec",
    [
        "superstate[state-window,state-only]",
        "superstate[state-window,conversational]",
    ],
)
def test_only_one_context_per_harness(spec: str) -> None:
    with pytest.raises(HarnessSpecError, match="one context"):
        parse_harness_spec(spec)
```

Append to `tests/test_superstate_native_driver.py`:

```python


def test_state_window_context_is_passed_through(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report())
    driver = _driver(tmp_path, stub, context="state-window")
    assert driver.harness_name == "superstate[state-window]"
    driver.run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer())
    [argv] = _calls(tmp_path)
    assert argv[argv.index("--context") + 1] == "state-window"
```

- [ ] **Step 2: Run to confirm they fail.** Run: `uv run pytest -q tests/test_harnesses.py tests/test_superstate_native_driver.py`. Expected: the four new tests fail. `state-window` is rejected as an unknown option or context, and the parametrised contradiction cases don't raise. The existing tests still pass.

- [ ] **Step 3: Driver.** In `lab/engine/drivers/superstate_native.py`, replace `CONTEXTS = ("state-only", "conversational")` with `CONTEXTS = ("state-only", "state-window", "conversational")`.

- [ ] **Step 4: Harness specs.** In `lab/engine/harnesses.py`:
  1. Replace `_SUPERSTATE_OPTIONS = ("state-only", "conversational", "no-loop-breaker", "tdd")` with:

```python
_SUPERSTATE_CONTEXTS = ("state-only", "state-window", "conversational")
_SUPERSTATE_OPTIONS = _SUPERSTATE_CONTEXTS + ("no-loop-breaker", "tdd")
```

  2. Replace

```python
        if "state-only" in opts and "conversational" in opts:
            raise HarnessSpecError("choose one context: state-only or conversational")
```

     with

```python
        contexts = [o for o in opts if o in _SUPERSTATE_CONTEXTS]
        if len(contexts) > 1:
            raise HarnessSpecError(
                f"choose one context, got {contexts}; one of {list(_SUPERSTATE_CONTEXTS)}"
            )
```

  3. Replace `        context="conversational" if "conversational" in opts else "state-only",` with:

```python
        context=next((o for o in opts if o in _SUPERSTATE_CONTEXTS), "state-only"),
```

- [ ] **Step 5: `paired_run.py`.** Replace `choices=["state-only", "conversational"]` in the `--context` argument with `choices=["state-only", "state-window", "conversational"]`.

- [ ] **Step 6: Run the tests.** Run: `uv run pytest -q tests/test_harnesses.py tests/test_superstate_native_driver.py`. Expected: 18 and 22 passed. The existing test `test_parse_rejects_anything_else` still passes, including `superstate[state-only,conversational]`, which the new message ("choose one context, got …") still matches with `HarnessSpecError`.

- [ ] **Step 7: Full check.** Run: `make lint && make test`. Expected: only the known pre-existing failures. Report the counts.

- [ ] **Step 8: Commit.**

```bash
git add lab/engine/drivers/superstate_native.py lab/engine/harnesses.py scripts/paired_run.py tests/test_harnesses.py tests/test_superstate_native_driver.py
git commit -m "feat(eval): superstate[state-window] as a harness context"
```
