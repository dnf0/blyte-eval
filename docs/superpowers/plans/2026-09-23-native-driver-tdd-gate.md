# Native Driver TDD Gate Implementation Plan (Part C, eval side)

> **For agentic workers:** Execution is delegated to headless `agy`, one task per dispatch; Claude reviews each task before the next is sent. Steps use checkbox (`- [ ]`) syntax for tracking. Do NOT `git push` or open PRs; commit locally only. NEVER start a benchmark run or call a model API: every test uses a stub `superstate` binary.

**Goal:** Let `SuperstateNativeDriver` run the native harness gated by autonomous TDD (`superstate --tdd`), selectable from `paired_run.py`.

**Spec:** `/Users/danielfisher/repos/superstate/docs/superpowers/specs/2026-09-23-native-harness-autonomous-tdd-design.md` (decision 8).

**Architecture:** One new driver option, `gate: Optional[str]` (`None` or `"tdd"`). It adds `--tdd` to the argv and `tdd` to `harness_name`, because results are pooled by that name. `paired_run.py` gains `--gate {none,tdd}`.

**Tech Stack:** Python 3.12, pytest, ruff, pyright (basic), uv.

## Global Constraints

- Base branch: `feat/native-driver-tdd-gate`. The task runs in the worktree `/Users/danielfisher/repos/superstate-eval--<task>` on branch `wip/<task>`. Run `uv sync` first.
- `make lint && make test` before committing. Known pre-existing failures that are not yours: 10+ E402 in `scripts/paired_run.py` (the `sys.path` bootstrap), 7 pyright errors in `tests/test_arm_input_parity.py`/`tests/test_superstate_daemon_adapter.py`, and `tests/test_governor_sizing.py::test_heavier_tasks_lower_the_concurrency_ceiling` (host RAM). Report them; do not fix them.
- The `superstate --tdd` flag is being built in parallel in the superstate repo. Tests use the existing stub binary, so they do not need it.

---

### Task 1: `gate="tdd"` on the native driver and `paired_run --gate`

**Files:**
- Modify: `lab/engine/drivers/superstate_native.py`, `scripts/paired_run.py`
- Test: `tests/test_superstate_native_driver.py` (append)

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_superstate_native_driver.py`:

```python


def test_tdd_gate_passes_the_flag_and_names_the_harness(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report())
    driver = _driver(tmp_path, stub, gate="tdd")
    assert driver.harness_name == "superstate[state-only,tdd]"
    driver.run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer())
    [argv] = _calls(tmp_path)
    flags = argv[: argv.index("--")]
    assert "--tdd" in flags
    assert "--gate" not in flags and "-g" not in flags


def test_ungated_is_the_default(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report())
    driver = _driver(tmp_path, stub)
    driver.run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer())
    [argv] = _calls(tmp_path)
    assert "--tdd" not in argv


def test_rejects_an_unknown_gate(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report())
    with pytest.raises(SuperstateNativeDriverError):
        _driver(tmp_path, stub, gate="pytest")


def test_harness_name_orders_every_option(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report())
    driver = _driver(tmp_path, stub, context="conversational", loop_breaker=False, gate="tdd")
    assert driver.harness_name == "superstate[conversational,no-loop-breaker,tdd]"


def test_paired_run_accepts_the_tdd_gate() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "paired_run", Path(__file__).resolve().parent.parent / "scripts" / "paired_run.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.build_parser().parse_args(["--gate", "tdd"]).gate == "tdd"
    assert module.build_parser().parse_args([]).gate == "none"
```

- [ ] **Step 2: Run to confirm they fail.** Run: `uv run pytest -q tests/test_superstate_native_driver.py`. Expected: the five new tests fail (`TypeError: ... unexpected keyword argument 'gate'` and a parser error for `--gate`). The 13 existing tests still pass.

- [ ] **Step 3: Add the option to the driver.** In `lab/engine/drivers/superstate_native.py`:
  1. Directly below `CONTEXTS = ("state-only", "conversational")`, add:

```python
#: Gate sources the driver can ask the harness for. None is ungated, like agy under vanilla;
#: "tdd" is the harness's own autonomous TDD (RED then GREEN), never a command we author.
GATES = (None, "tdd")
```

  2. In `__init__`'s signature, add `gate: Optional[str] = None,` directly after `loop_breaker: bool = True,`.
  3. Directly after the `if context not in CONTEXTS:` block (its `raise` included), add:

```python
        if gate not in GATES:
            raise SuperstateNativeDriverError(f"gate must be one of {GATES}, got {gate!r}")
```

  4. After `self.loop_breaker = loop_breaker`, add `self.gate = gate`.
  5. Replace `config = [context] + ([] if loop_breaker else ["no-loop-breaker"])` with:

```python
        config = (
            [context]
            + ([] if loop_breaker else ["no-loop-breaker"])
            + ([gate] if gate else [])
        )
```

  6. In `build_command`, directly after the lines

```python
        if not self.loop_breaker:
            cmd.append("--no-loop-breaker")
```

     add:

```python
        if self.gate == "tdd":
            cmd.append("--tdd")
```

  7. Update the `build_command` docstring to: `"""The argv for one task. Never a --gate: ungated, or the harness's own --tdd."""`

- [ ] **Step 4: Wire `paired_run.py`.**
  1. Directly after the `--no-loop-breaker` argument (both of its lines), add:

```python
    ap.add_argument("--gate", choices=["none", "tdd"], default="none",
                    help="Native superstate driver only: 'tdd' gates by the harness's autonomous TDD (default: none)")
```

  2. In the `SuperstateNativeDriver(...)` call, add `gate=None if args.gate == "none" else args.gate,` directly after `loop_breaker=not args.no_loop_breaker,`.
  3. In the `logger.info("Native superstate driver: …")` call that follows, append `, gate=%s` to the format string's final line (so it ends `"loop_breaker=%s, reports -> %s, gate=%s",`) and add `args.gate` as the last argument.

- [ ] **Step 5: Run the tests.** Run: `uv run pytest -q tests/test_superstate_native_driver.py`. Expected: 18 passed.

- [ ] **Step 6: Full check.** Run: `make lint && make test`. Expected: only the known pre-existing failures listed in Global Constraints. Report the counts.

- [ ] **Step 7: Commit.**

```bash
git add lab/engine/drivers/superstate_native.py scripts/paired_run.py tests/test_superstate_native_driver.py
git commit -m "feat(eval): native driver can gate by the harness's autonomous TDD"
```
