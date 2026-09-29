"""The native blyte harness as an evaluation driver.

Blyte used to be measured as a layer attached to agy or Claude Code. It is now a harness
in its own right (`blyte "<prompt>"`), so in this evaluation it sits where agy sits: it is
the worker runtime, and any arm can run on it. The first comparison is `vanilla` + agy against
`vanilla` + blyte: same task, model and sealed grader, different harness.

Spec: blyte/docs/superpowers/specs/2026-09-23-native-harness-eval-surface-design.md
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

logger = logging.getLogger("blyte_eval.drivers.blyte_native")

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
CONTEXTS = ("conversational", "folded")


class BlyteNativeDriverError(RuntimeError):
    """The driver cannot be configured to produce a valid measurement."""


#: Where the native harness is built. The most recently built one wins, so a stale release build
#: never shadows a fresh debug one.
BLYTE_BUILDS = (
    Path.home() / "repos/blyte/target/release/blyte",
    Path.home() / "repos/blyte/target/debug/blyte",
)


def _resolve_binary() -> Path:
    """The `blyte` binary: BLYTE_BIN, else SUPERSTATE_BIN (deprecated pre-rename name, still read
    for older commands), else the newest build. Kept apart from the legacy state engine's
    resolution, which needs pre-rename `superstate` builds (its subcommands no longer exist in `blyte`)."""
    for var in ("BLYTE_BIN", "SUPERSTATE_BIN"):  # SUPERSTATE_BIN: deprecated fallback
        env_path = os.environ.get(var)
        if env_path and Path(env_path).is_file():
            return Path(env_path)
    existing = [c for c in BLYTE_BUILDS if c.is_file()]
    if not existing:
        raise BlyteNativeDriverError(
            "No blyte binary found. Build it (`cargo build --release` in the blyte repo) "
            "or set BLYTE_BIN."
        )
    return max(existing, key=lambda c: c.stat().st_mtime)


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
        logger.warning("Unreadable blyte report %s: %s", path, exc)
        return None
    if not isinstance(data, dict) or data.get("schema_version") != REPORT_SCHEMA_VERSION:
        logger.warning("Blyte report %s has an unknown schema; not trusting it", path)
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
    model_seconds = report.get("model_seconds")
    tools_seconds = report.get("tools_seconds")
    gate_seconds = report.get("gate_seconds")
    gate_attempts = report.get("gate_attempts")
    harness_build = report.get("harness_build")
    tool_counts = report.get("tool_counts")
    return {
        "harness_turns": int(report.get("turns") or 0),
        "reads": reads,
        "unchanged_rereads": unchanged,
        "changed_rereads": changed,
        "repeated_commands": repeated,
        "appended_turns": len(appended),
        "rewritten_turns": len(rewritten),
        "fresh_on_appended": sum(int(t.get("input", 0)) for t in appended),
        "new_tokens_est_on_appended": sum(int(t.get("new_chars", 0)) for t in appended) // 4,
        "fresh_on_rewritten": sum(int(t.get("input", 0)) for t in rewritten),
        # The fold budget in force on the last call.
        "final_fold_budget": next(
            (t.get("fold_budget") for t in reversed(usage) if t.get("fold_budget")), None
        ),
        "model_seconds": float(model_seconds) if model_seconds is not None else None,
        "tools_seconds": float(tools_seconds) if tools_seconds is not None else None,
        "gate_seconds": float(gate_seconds) if gate_seconds is not None else None,
        "gate_attempts": int(gate_attempts) if gate_attempts is not None else None,
        "harness_build": str(harness_build) if harness_build is not None else None,
        "tool_counts": dict(tool_counts) if isinstance(tool_counts, dict) else {},
    }


class BlyteNativeDriver(AgentDriver):
    """Runs a whole task through the native blyte harness in one call."""

    harness_name: str = "blyte"
    # Every tool call is a `docker exec` into the task container; the model never gets a host
    # shell, so it cannot reach the Docker daemon or the held-out tests.
    provides_isolated_execution: bool = True

    def __init__(
        self,
        model: str,
        context: str = "folded",
        fold_budget: Optional[int] = None,
        blyte_bin: Optional[str | Path] = None,
        report_dir: Optional[str | Path] = None,
    ) -> None:
        if context not in CONTEXTS:
            raise BlyteNativeDriverError(
                f"context must be one of {CONTEXTS}, got {context!r}"
            )
        if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
            raise BlyteNativeDriverError(
                "GEMINI_API_KEY (or GOOGLE_API_KEY) must be set: the native harness calls the "
                "model API directly. Failing now, before any arm has run."
            )
        self.model = model
        self.context = context
        self.fold_budget = fold_budget
        # Results are pooled by `harness` (runner.py records harness_name), so every
        # configuration that changes behaviour must be in the name. Otherwise an
        # ablation pools its control with its treatment.
        config = (
            [context]
            + ([f"fold-budget-{fold_budget // 1000}k"] if fold_budget else [])
        )
        self.harness_name = f"blyte[{','.join(config)}]"
        self.report_dir = Path(report_dir) if report_dir is not None else None

        source = Path(blyte_bin) if blyte_bin is not None else _resolve_binary()
        # Copy to a run-scoped path: `cargo build` rewrites target/*/blyte in place, and a
        # rebuild mid-run would make one run measure two binaries while reporting one (EXP-073).
        self._work_dir = Path(tempfile.mkdtemp(prefix="blyte-native-"))
        self.blyte_bin = self._work_dir / "blyte"
        shutil.copy2(source, self.blyte_bin)
        self.blyte_bin_source = source
        self.blyte_bin_sha256 = hashlib.sha256(self.blyte_bin.read_bytes()).hexdigest()
        self.last_report: Optional[Dict[str, Any]] = None
        self.last_events_path: Optional[Path] = None

    def build_command(
        self, prompt: str, container_id: str, report_path: Path, timeout_sec: float
    ) -> list[str]:
        """The argv for one task. Never a --gate: runs are ungated, and the sealed grader decides."""
        cmd = [
            str(self.blyte_bin),
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
        if self.fold_budget:
            cmd += ["--fold-budget", str(self.fold_budget)]
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
                    "blyte native driver requires a sandbox container; "
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
                f"blyte killed after {elapsed:.0f}s with no report"
                if killed
                else f"blyte exited {returncode} with no report"
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
        success = report.get("outcome") == "verified"
        error_message = None
        if not success:
            error_message = report.get("error") or f"blyte outcome: {report.get('outcome')}"
        return DriverTelemetry(
            success=success,
            # blyte's last message: the plan, in a plan-first planning run (offload v2).
            raw_response=str(report.get("final_message") or ""),
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
