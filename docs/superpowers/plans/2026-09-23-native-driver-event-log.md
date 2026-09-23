# Native Driver Event Log Implementation Plan

> **For agentic workers:** Execution is delegated to headless `agy`, one task per dispatch; Claude reviews each task before the next is sent. Steps use checkbox (`- [ ]`) syntax for tracking. Do NOT `git push` or open PRs; commit locally only. NEVER start a benchmark run or call a model API: every test uses a stub `superstate` binary.

**Goal:** Keep the native harness's turn-by-turn event stream for every run, so a stalled phase can be diagnosed. The TDD smoke run's GREEN phase ran 233 turns with no edits and no gate attempt, and there was no record of what it did, because the driver discarded stdout.

**Architecture:** `SuperstateNativeDriver.run` already captures the harness's stdout and stderr. It writes them to `<report_dir>/<task>-<report stem>.events.log`, next to the saved report, on every exit path. That includes a missing report and a kill, which are exactly the runs that most need a record.

**Tech Stack:** Python 3.12, pytest, ruff, pyright (basic), uv.

## Global Constraints

- Base branch: `feat/native-driver-tdd-gate`. The task runs in the worktree `/Users/danielfisher/repos/superstate-eval--<task>` on branch `wip/<task>`. Run `uv sync` first.
- `make lint && make test` before committing. Known pre-existing failures that are not yours: E402s in `scripts/paired_run.py`, 7 pyright errors in `tests/test_arm_input_parity.py`/`tests/test_superstate_daemon_adapter.py`, and `tests/test_governor_sizing.py::test_heavier_tasks_lower_the_concurrency_ceiling`. Report them; do not fix them.

---

### Task 1: Save the harness event stream next to the report

**Files:**
- Modify: `lab/engine/drivers/superstate_native.py`
- Modify and test: `tests/test_superstate_native_driver.py`

- [ ] **Step 1: Let the stub print to stdout.** In `tests/test_superstate_native_driver.py`, replace the whole `_make_stub` function with:

```python
def _make_stub(
    tmp_path: Path,
    report: Optional[dict[str, Any]],
    exit_code: int = 0,
    stderr: str = "",
    stdout: str = "",
) -> Path:
    """A fake `superstate` that logs its argv, prints `stdout`, and writes `report`."""
    stub = tmp_path / "superstate-stub"
    calls = tmp_path / "calls.jsonl"
    payload = json.dumps(report)
    stub.write_text(
        textwrap.dedent(
            f"""\
            #!{sys.executable}
            import json, sys
            from pathlib import Path
            args = sys.argv[1:]
            with open({str(calls)!r}, "a") as fh:
                fh.write(json.dumps(args) + "\\n")
            payload = {payload!r}
            if payload != "null":
                Path(args[args.index("--report") + 1]).write_text(payload)
            sys.stdout.write({stdout!r})
            sys.stderr.write({stderr!r})
            sys.exit({exit_code})
            """
        ),
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return stub
```

- [ ] **Step 2: Write the failing tests.** Append to `tests/test_superstate_native_driver.py`:

```python


EVENTS = "[Turn 1] looking around\n● read main.go -> 40 lines read\n[Turn 2] done\n"


def test_the_event_stream_is_saved_next_to_the_report(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report(), stdout=EVENTS, stderr="warning: slow\n")
    report_dir = tmp_path / "reports"
    driver = _driver(tmp_path, stub, report_dir=report_dir)
    driver.run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer())

    [report] = list(report_dir.glob("*.json"))
    [events] = list(report_dir.glob("*.events.log"))
    assert events.name == report.name.removesuffix(".json") + ".events.log"
    text = events.read_text()
    assert "● read main.go -> 40 lines read" in text
    assert "warning: slow" in text
    assert driver.last_events_path == events


def test_the_event_stream_is_kept_when_there_is_no_report(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, None, exit_code=1, stdout=EVENTS, stderr="panicked\n")
    report_dir = tmp_path / "reports"
    driver = _driver(tmp_path, stub, report_dir=report_dir)
    t = driver.run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer())

    assert t.success is False
    assert list(report_dir.glob("*.json")) == []
    [events] = list(report_dir.glob("*.events.log"))
    assert "[Turn 2] done" in events.read_text()
    assert "panicked" in events.read_text()


def test_nothing_is_written_without_a_report_dir(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report(), stdout=EVENTS)
    driver = _driver(tmp_path, stub)
    driver.run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer())
    assert driver.last_events_path is None
```

- [ ] **Step 3: Run to confirm they fail.** Run: `uv run pytest -q tests/test_superstate_native_driver.py`. Expected: the three new tests fail (no `.events.log` file; `last_events_path` does not exist). The 18 existing tests still pass.

- [ ] **Step 4: Save the stream in the driver.** In `lab/engine/drivers/superstate_native.py`:
  1. Directly below the `_tail` function, add:

```python
def _text(value: Optional[str | bytes]) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
```

  2. In `__init__`, after `self.last_report: Optional[Dict[str, Any]] = None`, add:

```python
        self.last_events_path: Optional[Path] = None
```

  3. In `run`, replace

```python
        killed = False
        returncode: Optional[int] = None
        stderr: Optional[str | bytes] = None
```

     with

```python
        killed = False
        returncode: Optional[int] = None
        stdout: Optional[str | bytes] = None
        stderr: Optional[str | bytes] = None
```

  4. Replace `returncode, stderr = proc.returncode, proc.stderr` with `returncode, stdout, stderr = proc.returncode, proc.stdout, proc.stderr`.
  5. Replace `killed, stderr = True, exc.stderr` with `killed, stdout, stderr = True, exc.stdout, exc.stderr`.
  6. Directly after the line `elapsed = time.monotonic() - start`, insert:

```python
        # Kept on every exit path, and before the report is checked: a run with no report, or
        # one that was killed, is exactly the run that most needs a record of what it did.
        self.last_events_path = None
        if self.report_dir is not None:
            self.report_dir.mkdir(parents=True, exist_ok=True)
            events_path = self.report_dir / f"{task.name}-{report_path.stem}.events.log"
            events_path.write_text(
                _text(stdout) + "\n--- stderr ---\n" + _text(stderr), encoding="utf-8"
            )
            self.last_events_path = events_path
```

- [ ] **Step 5: Run the tests.** Run: `uv run pytest -q tests/test_superstate_native_driver.py`. Expected: 21 passed.

- [ ] **Step 6: Full check.** Run: `make lint && make test`. Expected: only the known pre-existing failures. Report the counts.

- [ ] **Step 7: Commit.**

```bash
git add lab/engine/drivers/superstate_native.py tests/test_superstate_native_driver.py
git commit -m "feat(eval): keep the native harness event stream next to its report"
```
