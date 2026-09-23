# Superstate Native Driver Implementation Plan (Part B: superstate-eval)

> **For agentic workers:** Execution is delegated to headless `agy`, one task per dispatch; Claude reviews each task before the next is sent. Steps use checkbox (`- [ ]`) syntax for tracking. Do NOT `git push` or open PRs; commit locally only. NEVER start a benchmark run or call a model API: every test uses a stub `superstate` binary.

**Goal:** Let the evaluation run the native superstate harness as a worker runtime (a driver, like agy), so `vanilla` + agy and `vanilla` + superstate can be compared on the same tasks, model and grader.

**Spec:** `/Users/danielfisher/repos/superstate/docs/superpowers/specs/2026-09-23-native-harness-eval-surface-design.md` (Part B, and the report schema it reads).

**Architecture:** A new `SuperstateNativeDriver(AgentDriver)` shells out once per task to `superstate -- <prompt>` with `--container`, `--container-workdir /app`, `--max-seconds` and `--report`. It reads the JSON report and returns `DriverTelemetry` with agy-identical token accounting. `scripts/paired_run.py` gains `--driver superstate`, `--context` and `--no-loop-breaker`.

**Tech Stack:** Python 3.12, pytest, ruff, pyright (basic), uv.

## Global Constraints

- Base branch: `feat/superstate-native-driver`. The task runs in the worktree `/Users/danielfisher/repos/superstate-eval--<task>` on branch `wip/<task>`. Run `uv sync` in the worktree first.
- `make lint && make test` must pass before committing.
- The superstate-side flags (`--report`, `--max-seconds`, `--container-workdir`, `--no-loop-breaker`) are being built in parallel in the superstate repo. This task does not need them: it is tested entirely against a stub binary that honours the report contract.
- The Referee Rule (CLAUDE.md) holds: the driver passes `task.instruction` (or the arm's `prompt_override`) through untouched. It adds no prompt text and no gate.

---

### Task 1: `SuperstateNativeDriver` and `paired_run --driver superstate`

**Files:**
- Create: `lab/engine/drivers/superstate_native.py`
- Modify: `lab/engine/drivers/__init__.py`, `scripts/paired_run.py`
- Test: `tests/test_superstate_native_driver.py`

- [ ] **Step 1: Write the failing tests.** Create `tests/test_superstate_native_driver.py`:

```python
"""Tests for the native superstate harness driver.

Driven against a stub `superstate` that honours the --report contract, so nothing here spends
money, needs credentials, or launches Docker. Contract:
superstate/docs/superpowers/specs/2026-09-23-native-harness-eval-surface-design.md
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import textwrap
from typing import Any, Optional

import pytest

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.vanilla import VanillaAdapter
from lab.engine.drivers.agy_cli import estimate_cost_usd
from lab.engine.drivers.superstate_native import (
    CONTAINER_WORKDIR,
    MAX_TURNS,
    SuperstateNativeDriver,
    SuperstateNativeDriverError,
)

MODEL = "gemini-3.8-flash-high"


def _report(**overrides: Any) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": 1,
        "outcome": "verified",
        "error": None,
        "model_requested": MODEL,
        "model_id": "gemini/gemini-3.8-flash",
        "context": "state-only",
        "loop_breaker": True,
        "gated": False,
        "container": "cnt-1",
        "container_workdir": "/app",
        "duration_seconds": 12.5,
        "turns": 9,
        "empty_turns": 0,
        "tool_calls": 14,
        "gate_attempts": 1,
        "rollbacks": 0,
        "usage": {"input": 1000, "cached": 5000, "output": 200, "thinking": 300},
        "interceptions": {"read": 2, "bash": 0},
        "insists": 1,
        "agent_note_keys": [],
    }
    report.update(overrides)
    return report


def _make_stub(
    tmp_path: Path,
    report: Optional[dict[str, Any]],
    exit_code: int = 0,
    stderr: str = "",
) -> Path:
    """A fake `superstate` that logs its argv and writes `report` to the --report path."""
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
            sys.stderr.write({stderr!r})
            sys.exit({exit_code})
            """
        ),
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return stub


def _calls(tmp_path: Path) -> list[list[str]]:
    path = tmp_path / "calls.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _task(tmp_path: Path) -> TaskSpec:
    return TaskSpec(
        id="org/task",
        name="task",
        instruction="Fix the bug.",
        docker_image="img",
        task_dir=tmp_path,
    )


class FakeContainer:
    def __init__(self, container_id: str = "cnt-1") -> None:
        self.id = container_id
        self.name = f"eval-{container_id}"


@pytest.fixture(autouse=True)
def _api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")


def _driver(tmp_path: Path, stub: Path, **kwargs: Any) -> SuperstateNativeDriver:
    return SuperstateNativeDriver(model=MODEL, superstate_bin=stub, **kwargs)


def test_command_pins_model_container_workdir_and_budget(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report())
    driver = _driver(tmp_path, stub)
    driver.run(_task(tmp_path), tmp_path, timeout_sec=600.0, container=FakeContainer())

    [argv] = _calls(tmp_path)
    flags = argv[: argv.index("--")]
    assert argv[argv.index("--") + 1 :] == ["Fix the bug."]
    assert flags[flags.index("--model") + 1] == MODEL
    assert flags[flags.index("--context") + 1] == "state-only"
    assert flags[flags.index("--container") + 1] == "cnt-1"
    assert flags[flags.index("--container-workdir") + 1] == CONTAINER_WORKDIR == "/app"
    assert flags[flags.index("--max-turns") + 1] == str(MAX_TURNS)
    assert flags[flags.index("--max-seconds") + 1] == "600"
    assert "--report" in flags
    assert "--gate" not in flags and "-g" not in flags
    assert "--no-loop-breaker" not in flags


def test_loop_breaker_ablation_and_context_are_passed(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report())
    driver = _driver(tmp_path, stub, context="conversational", loop_breaker=False)
    driver.run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer())

    [argv] = _calls(tmp_path)
    assert "--no-loop-breaker" in argv
    assert argv[argv.index("--context") + 1] == "conversational"


def test_telemetry_uses_agy_token_accounting(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report())
    report_dir = tmp_path / "reports"
    driver = _driver(tmp_path, stub, report_dir=report_dir)
    t = driver.run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer())

    assert t.success is True
    assert t.error_message is None
    # Fresh input and visible output only: cached and thinking are NOT added, exactly as
    # AgyCliDriver counts only input_tokens and output_tokens.
    assert (t.input_tokens, t.output_tokens) == (1000, 200)
    assert t.cost_usd == estimate_cost_usd(MODEL, 1000, 200)
    assert t.raw_response == ""
    assert t.conversation_id is None
    assert driver.last_report is not None
    assert driver.last_report["usage"]["cached"] == 5000
    [saved] = list(report_dir.glob("*.json"))
    assert json.loads(saved.read_text())["insists"] == 1


def test_an_unverified_outcome_is_a_failure(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report(outcome="budget_exhausted"), exit_code=1)
    t = _driver(tmp_path, stub).run(
        _task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer()
    )
    assert t.success is False
    assert t.error_message is not None and "budget_exhausted" in t.error_message
    assert (t.input_tokens, t.output_tokens) == (1000, 200)


def test_a_missing_report_is_a_failure_never_a_pass(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, None, exit_code=1, stderr="thread 'main' panicked")
    t = _driver(tmp_path, stub).run(
        _task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer()
    )
    assert t.success is False
    assert t.error_message is not None
    assert "no report" in t.error_message
    assert "panicked" in t.error_message


def test_a_report_with_an_unknown_schema_is_a_failure(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report(schema_version=99))
    t = _driver(tmp_path, stub).run(
        _task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer()
    )
    assert t.success is False
    assert t.error_message is not None and "no report" in t.error_message


def test_refuses_to_run_without_a_sandbox(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report())
    t = _driver(tmp_path, stub).run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=None)
    assert t.success is False
    assert t.error_message is not None and "container" in t.error_message
    assert _calls(tmp_path) == []


def test_rejects_an_unknown_context(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report())
    with pytest.raises(SuperstateNativeDriverError):
        _driver(tmp_path, stub, context="stateless")


def test_requires_a_gemini_key_before_any_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    stub = _make_stub(tmp_path, _report())
    with pytest.raises(SuperstateNativeDriverError, match="GEMINI_API_KEY"):
        _driver(tmp_path, stub)


def test_binary_is_copied_to_a_run_scoped_path(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report())
    driver = _driver(tmp_path, stub)
    assert driver.superstate_bin != stub
    assert driver.superstate_bin.read_bytes() == stub.read_bytes()
    # A rebuild of the source mid-run must not change what this run executes (EXP-073).
    stub.write_text("#!/bin/sh\nexit 3\n")
    t = driver.run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer())
    assert t.success is True


def test_vanilla_arm_makes_exactly_one_driver_call(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report())
    driver = _driver(tmp_path, stub)
    result = VanillaAdapter().execute(
        tmp_path, _task(tmp_path), driver, timeout_sec=60.0, container=FakeContainer()
    )
    assert len(_calls(tmp_path)) == 1
    assert result.success is True
    assert result.turns == 1
    assert (result.input_tokens, result.output_tokens) == (1000, 200)


def test_paired_run_accepts_the_superstate_driver() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "paired_run", Path(__file__).resolve().parent.parent / "scripts" / "paired_run.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    args = module.build_parser().parse_args(
        ["--driver", "superstate", "--context", "conversational", "--no-loop-breaker"]
    )
    assert args.driver == "superstate"
    assert args.context == "conversational"
    assert args.no_loop_breaker is True
    defaults = module.build_parser().parse_args([])
    assert defaults.context == "state-only"
    assert defaults.no_loop_breaker is False
```

- [ ] **Step 2: Run to confirm they fail.** Run: `uv run pytest -q tests/test_superstate_native_driver.py`. Expected: collection error, `ModuleNotFoundError: No module named 'lab.engine.drivers.superstate_native'`.

- [ ] **Step 3: Create the driver.** Create `lab/engine/drivers/superstate_native.py`:

```python
"""The native superstate harness as an evaluation driver.

Superstate used to be measured as a layer attached to agy or Claude Code. It is now a harness
in its own right (`superstate "<prompt>"`), so in this evaluation it sits where agy sits: it is
the worker runtime, and any arm can run on it. The first comparison is `vanilla` + agy against
`vanilla` + superstate: same task, model and sealed grader, different harness.

Spec: superstate/docs/superpowers/specs/2026-09-23-native-harness-eval-surface-design.md
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Any, Dict, Optional
import uuid

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.base import AgentDriver, DriverTelemetry
from lab.engine.drivers.agy_cli import estimate_cost_usd

logger = logging.getLogger("superstate_eval.drivers.superstate_native")

#: Where the runner mounts the task repository inside the sandbox (runner.CONTAINER_WORKSPACE).
CONTAINER_WORKDIR = "/app"
#: A loop-breaker, not a budget. agy has no turn cap, so the native harness must not have one
#: either, or the comparison measures the cap. The time budget is what binds.
MAX_TURNS = 1000
#: `--max-seconds` makes the harness stop itself and write its report. A turn already in flight
#: can overrun by a model call plus a command (300s each), so the process is only killed after
#: this grace. A kill loses the report, and with it the tokens (FINDINGS 13.5).
KILL_GRACE_SEC = 900.0
REPORT_SCHEMA_VERSION = 1
CONTEXTS = ("state-only", "conversational")


class SuperstateNativeDriverError(RuntimeError):
    """The driver cannot be configured to produce a valid measurement."""


def _resolve_binary() -> Path:
    # Imported here: drivers -> adapters -> superstate_daemon -> drivers is already a cycle.
    from lab.engine.adapters.superstate import ENGINE_RUST, find_superstate_binary

    found = find_superstate_binary(ENGINE_RUST)
    if found is None:
        raise SuperstateNativeDriverError(
            "No superstate binary found. Build it (`cargo build --release` in the superstate "
            "repo) or set SUPERSTATE_BIN."
        )
    return found


def _tail(text: Optional[str | bytes], limit: int = 800) -> str:
    if text is None:
        return ""
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    return text.strip()[-limit:]


def _read_report(path: Path) -> Optional[Dict[str, Any]]:
    """The report, or None if it is missing, unparseable, or of an unknown schema."""
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Unreadable superstate report %s: %s", path, exc)
        return None
    if not isinstance(data, dict) or data.get("schema_version") != REPORT_SCHEMA_VERSION:
        logger.warning("Superstate report %s has an unknown schema; not trusting it", path)
        return None
    return data


class SuperstateNativeDriver(AgentDriver):
    """Runs a whole task through the native superstate harness in one call."""

    harness_name: str = "superstate"
    # Every tool call is a `docker exec` into the task container; the model never gets a host
    # shell, so it cannot reach the Docker daemon or the held-out tests.
    provides_isolated_execution: bool = True

    def __init__(
        self,
        model: str,
        context: str = "state-only",
        loop_breaker: bool = True,
        superstate_bin: Optional[str | Path] = None,
        report_dir: Optional[str | Path] = None,
    ) -> None:
        if context not in CONTEXTS:
            raise SuperstateNativeDriverError(
                f"context must be one of {CONTEXTS}, got {context!r}"
            )
        if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
            raise SuperstateNativeDriverError(
                "GEMINI_API_KEY (or GOOGLE_API_KEY) must be set: the native harness calls the "
                "model API directly. Failing now, before any arm has run."
            )
        self.model = model
        self.context = context
        self.loop_breaker = loop_breaker
        self.report_dir = Path(report_dir) if report_dir is not None else None

        source = Path(superstate_bin) if superstate_bin is not None else _resolve_binary()
        # Copy to a run-scoped path: `cargo build` rewrites target/*/superstate in place, and a
        # rebuild mid-run would make one run measure two binaries while reporting one (EXP-073).
        self._work_dir = Path(tempfile.mkdtemp(prefix="superstate-native-"))
        self.superstate_bin = self._work_dir / "superstate"
        shutil.copy2(source, self.superstate_bin)
        self.superstate_bin_source = source
        self.superstate_bin_sha256 = hashlib.sha256(self.superstate_bin.read_bytes()).hexdigest()
        self.last_report: Optional[Dict[str, Any]] = None

    def build_command(
        self, prompt: str, container_id: str, report_path: Path, timeout_sec: float
    ) -> list[str]:
        """The argv for one task. No `--gate`: this driver runs ungated, like agy under vanilla."""
        cmd = [
            str(self.superstate_bin),
            "--model",
            self.model,
            "--context",
            self.context,
            "--container",
            container_id,
            "--container-workdir",
            CONTAINER_WORKDIR,
            "--max-turns",
            str(MAX_TURNS),
            "--max-seconds",
            str(max(1, int(timeout_sec))),
            "--report",
            str(report_path),
        ]
        if not self.loop_breaker:
            cmd.append("--no-loop-breaker")
        # `--` so an instruction that starts with a dash is never parsed as a flag.
        cmd += ["--", prompt]
        return cmd

    def run(
        self,
        task: TaskSpec,
        workspace_path: Path,
        prompt_override: Optional[str] = None,
        conversation_id: Optional[str] = None,
        timeout_sec: float = 3600.0,
        container: Any = None,
    ) -> DriverTelemetry:
        start = time.monotonic()
        if container is None:
            return DriverTelemetry(
                success=False,
                raw_response="",
                duration_seconds=0.0,
                error_message=(
                    "superstate native driver requires a sandbox container; "
                    "refusing to run on the host"
                ),
            )
        container_id = str(
            getattr(container, "id", None) or getattr(container, "name", None) or container
        )
        prompt = prompt_override or task.instruction
        report_path = self._work_dir / f"report-{uuid.uuid4().hex}.json"
        cmd = self.build_command(prompt, container_id, report_path, timeout_sec)

        killed = False
        returncode: Optional[int] = None
        stderr: Optional[str | bytes] = None
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(workspace_path),
                capture_output=True,
                text=True,
                timeout=timeout_sec + KILL_GRACE_SEC,
                check=False,
            )
            returncode, stderr = proc.returncode, proc.stderr
        except subprocess.TimeoutExpired as exc:
            killed, stderr = True, exc.stderr
        elapsed = time.monotonic() - start

        report = _read_report(report_path)
        self.last_report = report
        if report is None:
            reason = (
                f"superstate killed after {elapsed:.0f}s with no report"
                if killed
                else f"superstate exited {returncode} with no report"
            )
            return DriverTelemetry(
                success=False,
                raw_response="",
                duration_seconds=elapsed,
                error_message=f"{reason}: {_tail(stderr)}",
            )

        if self.report_dir is not None:
            self.report_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(report_path, self.report_dir / f"{task.name}-{report_path.name}")

        usage = report.get("usage") or {}
        # agy parity: AgyCliDriver counts only fresh input and visible output. Cached and
        # thinking tokens stay in the report (and last_report), not in the totals.
        input_tokens = int(usage.get("input", 0))
        output_tokens = int(usage.get("output", 0))
        success = report.get("outcome") == "verified"
        error_message = None
        if not success:
            error_message = report.get("error") or f"superstate outcome: {report.get('outcome')}"
        return DriverTelemetry(
            success=success,
            raw_response="",
            duration_seconds=elapsed,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=estimate_cost_usd(self.model, input_tokens, output_tokens),
            conversation_id=None,
            error_message=error_message,
        )
```

- [ ] **Step 4: Export it.** Replace `lab/engine/drivers/__init__.py` with:

```python
"""Driver implementations for agent runners."""

from lab.engine.drivers.agy_cli import AgyCliDriver, AgyCliDriverError
from lab.engine.drivers.claude_cli import ClaudeCliDriver, ClaudeCliDriverError
from lab.engine.drivers.superstate_native import (
    SuperstateNativeDriver,
    SuperstateNativeDriverError,
)

__all__ = [
    "AgyCliDriver",
    "AgyCliDriverError",
    "ClaudeCliDriver",
    "ClaudeCliDriverError",
    "SuperstateNativeDriver",
    "SuperstateNativeDriverError",
]
```

- [ ] **Step 5: Wire `paired_run.py`.**
  1. After the line `from lab.engine.drivers.claude_cli import ClaudeCliDriver`, add:
     ```python
     from lab.engine.drivers.superstate_native import SuperstateNativeDriver
     ```
  2. Replace the `--driver` argument with:
     ```python
         ap.add_argument("--driver", choices=["agy", "claude", "superstate"], default="agy",
                         help="Worker runtime: agy, claude, or the native superstate harness (default: agy)")
         ap.add_argument("--context", choices=["state-only", "conversational"], default="state-only",
                         help="Native superstate driver only: context strategy (default: state-only)")
         ap.add_argument("--no-loop-breaker", action="store_true",
                         help="Native superstate driver only: disable the loop-breaker guards (ablation control)")
     ```
  3. Replace the driver-selection block:
     ```python
         if args.driver == "claude":
             model = args.model if args.model != "gemini-3.8-flash-high" else "claude-3-7-sonnet-20250219"
             driver = ClaudeCliDriver(model=model)
         else:
             driver = AgyCliDriver(model=args.model)
     ```
     with:
     ```python
         if args.driver == "claude":
             model = args.model if args.model != "gemini-3.8-flash-high" else "claude-3-7-sonnet-20250219"
             driver = ClaudeCliDriver(model=model)
         elif args.driver == "superstate":
             # Same --model as every other driver, so model parity holds by construction.
             report_dir = (
                 args.out.with_suffix(".native_reports") if args.out
                 else args.workspace_root / "native_reports"
             )
             driver = SuperstateNativeDriver(
                 model=args.model,
                 context=args.context,
                 loop_breaker=not args.no_loop_breaker,
                 report_dir=report_dir,
             )
             logger.info(
                 "Native superstate driver: bin=%s (sha256 %s, copied from %s), context=%s, "
                 "loop_breaker=%s, reports -> %s",
                 driver.superstate_bin, driver.superstate_bin_sha256[:12],
                 driver.superstate_bin_source, args.context, not args.no_loop_breaker, report_dir,
             )
         else:
             driver = AgyCliDriver(model=args.model)
     ```

- [ ] **Step 6: Run the new tests.** Run: `uv run pytest -q tests/test_superstate_native_driver.py`. Expected: 12 passed.

- [ ] **Step 7: Full check.** Run: `make lint && make test`. Expected: ruff clean, pyright 0 errors, all tests pass. If a pre-existing test fails, re-run it on the base branch (`git stash` is NOT allowed; use `git -C /Users/danielfisher/repos/superstate-eval` on the base checkout) to show it fails there too, and report it rather than fixing it.

- [ ] **Step 8: Commit.**

```bash
git add lab/engine/drivers/superstate_native.py lab/engine/drivers/__init__.py scripts/paired_run.py tests/test_superstate_native_driver.py
git commit -m "feat(eval): native superstate harness driver and paired_run --driver superstate"
```
