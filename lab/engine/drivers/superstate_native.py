"""The native superstate harness as an evaluation driver.

Superstate used to be measured as a layer attached to agy or Claude Code. It is now a harness
in its own right (`superstate "<prompt>"`), so in this evaluation it sits where agy sits: it is
the worker runtime, and any arm can run on it. The first comparison is `vanilla` + agy against
`vanilla` + superstate: same task, model and sealed grader, different harness.

Spec: superstate/docs/superpowers/specs/2026-09-23-native-harness-eval-surface-design.md
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import logging
import os
from pathlib import Path
import re
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
CONTEXTS = ("state-only", "state-window", "conversational", "folded", "compact", "adaptive")
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
            "repo) or set BLYTE_BIN."
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
        # The fold budget in force on the last call: an adaptive context's grown budget.
        "final_fold_budget": next(
            (t.get("fold_budget") for t in reversed(usage) if t.get("fold_budget")), None
        ),
    }


class SuperstateNativeDriver(AgentDriver):
    """Runs a whole task through the native superstate harness in one call."""

    harness_name: str = "blyte"
    # Every tool call is a `docker exec` into the task container; the model never gets a host
    # shell, so it cannot reach the Docker daemon or the held-out tests.
    provides_isolated_execution: bool = True

    def __init__(
        self,
        model: str,
        context: str = "folded",
        loop_breaker: bool = True,
        gate: Optional[str] = None,
        review: bool = False,
        fold_notes: bool = False,
        fold_budget: Optional[int] = None,
        max_cost_usd: Optional[float] = None,
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
        self.review = review
        self.fold_notes = fold_notes
        self.fold_budget = fold_budget
        self.max_cost_usd = max_cost_usd
        # Results are pooled by `harness` (runner.py records harness_name), so every
        # configuration that changes behaviour must be in the name. Otherwise a loop-breaker
        # ablation pools its control with its treatment.
        config = (
            [context]
            + ([] if loop_breaker else ["no-loop-breaker"])
            + ([gate] if gate else [])
            + (["review"] if review else [])
            + (["fold-notes"] if fold_notes else [])
            + ([f"fold-budget-{fold_budget // 1000}k"] if fold_budget else [])
        )
        self.harness_name = f"blyte[{','.join(config)}]"
        self.report_dir = Path(report_dir) if report_dir is not None else None

        source = Path(superstate_bin) if superstate_bin is not None else _resolve_binary()
        # Copy to a run-scoped path: `cargo build` rewrites target/*/superstate in place, and a
        # rebuild mid-run would make one run measure two binaries while reporting one (EXP-073).
        self._work_dir = Path(tempfile.mkdtemp(prefix="superstate-native-"))
        self.superstate_bin = self._work_dir / "blyte"
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
        if self.review:
            cmd.append("--review")
        if self.fold_notes:
            cmd.append("--fold-notes")
        if self.fold_budget:
            cmd += ["--fold-budget", str(self.fold_budget)]
        if self.max_cost_usd is not None:
            cmd += ["--max-cost-usd", str(self.max_cost_usd)]
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
        # Same accounting as AgyCliDriver: fresh input, cached input, output and thinking are
        # counted separately and all four are priced.
        input_tokens = int(usage.get("input", 0))
        output_tokens = int(usage.get("output", 0))
        cached_input_tokens = int(usage.get("cached", 0))
        thinking_tokens = int(usage.get("thinking", 0))
        cost_usd = estimate_cost_usd(
            self.model, input_tokens, output_tokens, cached_input_tokens, thinking_tokens
        )
        metrics = run_metrics(report, _text(stdout))
        if metrics["harness_turns"]:
            metrics["cost_per_turn"] = round(cost_usd / metrics["harness_turns"], 6)
        metrics["max_cost_usd"] = self.max_cost_usd
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
            cached_input_tokens=cached_input_tokens,
            thinking_tokens=thinking_tokens,
            cost_usd=cost_usd,
            conversation_id=None,
            error_message=error_message,
            metrics=metrics,
        )
