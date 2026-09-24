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
CONTEXTS = ("state-only", "state-window", "conversational", "folded")
#: Gate sources the driver can ask the harness for. None is ungated, like agy under vanilla;
#: "tdd" is the harness's own autonomous TDD (RED then GREEN), never a command we author.
GATES = (None, "tdd")


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


def _text(value: Optional[str | bytes]) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


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
        gate: Optional[str] = None,
        superstate_bin: Optional[str | Path] = None,
        report_dir: Optional[str | Path] = None,
    ) -> None:
        if context not in CONTEXTS:
            raise SuperstateNativeDriverError(
                f"context must be one of {CONTEXTS}, got {context!r}"
            )
        if gate not in GATES:
            raise SuperstateNativeDriverError(f"gate must be one of {GATES}, got {gate!r}")
        if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
            raise SuperstateNativeDriverError(
                "GEMINI_API_KEY (or GOOGLE_API_KEY) must be set: the native harness calls the "
                "model API directly. Failing now, before any arm has run."
            )
        self.model = model
        self.context = context
        self.loop_breaker = loop_breaker
        self.gate = gate
        # Results are pooled by `harness` (runner.py records harness_name), so every
        # configuration that changes behaviour must be in the name. Otherwise a loop-breaker
        # ablation pools its control with its treatment.
        config = (
            [context]
            + ([] if loop_breaker else ["no-loop-breaker"])
            + ([gate] if gate else [])
        )
        self.harness_name = f"superstate[{','.join(config)}]"
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
        self.last_events_path: Optional[Path] = None

    def build_command(
        self, prompt: str, container_id: str, report_path: Path, timeout_sec: float
    ) -> list[str]:
        """The argv for one task. Never a --gate: ungated, or the harness's own --tdd."""
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
        if self.gate == "tdd":
            cmd.append("--tdd")
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
        stdout: Optional[str | bytes] = None
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
            returncode, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired as exc:
            killed, stdout, stderr = True, exc.stdout, exc.stderr
        elapsed = time.monotonic() - start

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
