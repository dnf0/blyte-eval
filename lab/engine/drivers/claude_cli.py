"""A live AgentDriver backed by the Claude Code CLI.

The agent process runs on the host (it needs network to reach the API; the task's
sandbox is deliberately network-isolated) with its working directory set to the
run's workspace, which the runner bind-mounts into the container at /app. Edits
the agent makes are therefore visible to the grader, and vice versa.

Command execution is redirected into the container rather than left on the host.
A host shell would be both wrong (no task toolchain) and unsafe: it can reach the
Docker daemon, and from there read the held-out tests baked into the verifier
image or mount the host filesystem. So when a container is supplied the driver
disallows the CLI's Bash tool and supplies `run_in_container` over MCP instead
(see container_exec_mcp), which can only exec in this run's container.
`--strict-mcp-config` also keeps the operator's own MCP servers out of the run,
which would otherwise vary between arms.

The operator's own Claude Code setup stays out as well: `--setting-sources project,local`
skips the user-level settings, plugins, hooks and `~/.claude/CLAUDE.md`, and
`--disable-slash-commands` removes skills. Without them, the offload smoke run (2026-09-27)
measured the operator's plugins, not the harness: one arm stopped to ask clarifying
questions and the other spent its time writing a plan. `--bare` would isolate more but
requires an API key; these flags keep the CLI's own login.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Optional
import uuid

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.base import AgentDriver, DriverTelemetry

logger = logging.getLogger("superstate_eval.drivers.claude_cli")

# Per-MTok USD, from the current model table. Used only when the CLI does not
# report a cost itself.
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-fable-5-1": (10.00, 50.00),
}

DEFAULT_MODEL = "claude-opus-5"

# MCP server name; the model sees the tool as mcp__task__run_in_container.
MCP_SERVER_NAME = "task"
REPO_ROOT = Path(__file__).resolve().parents[3]

# In the offload v1 run (2026-09-28) arm B spent about 120 s waiting on its own background
# Explore subagent through repeated ScheduleWakeup calls; that is harness noise, not delegation.
DISALLOWED_TOOLS: tuple[str, ...] = ("Agent", "ScheduleWakeup")

CONTAINER_EXEC_SYSTEM_PROMPT = (
    "Command execution: this workspace is mounted into a Docker container that holds "
    "the project's toolchain and dependencies. The host has neither, and you have no "
    "shell on it. Run every build, test and inspection command with the "
    f"`mcp__{MCP_SERVER_NAME}__run_in_container` tool. Read and edit files normally — "
    "the workspace directory and the container's /app are the same files."
)

# Both arms get this. Headless, with the operator's setup left out, Haiku answered the task
# text with "what would you like me to do?" and stopped (offload smoke run, 2026-09-27).
AUTONOMY_SYSTEM_PROMPT = (
    "You are running non-interactively: nobody will read or answer questions. Treat the "
    "request as a task to complete in this repository. Implement it, check it, and stop "
    "when it is done."
)

# The offload arm is told to delegate, as the blyte-implementer skill tells Claude Code. With
# delegation merely allowed, Haiku did everything itself in the smoke run (2026-09-27), so the
# arm measured nothing about offloading.
OFFLOAD_SYSTEM_PROMPT = (
    "Delegate implementation to `dispatch_blyte`. Your part is to understand the task, plan "
    "it, and write each implementation task precisely (the files, the expected behaviour, the "
    "tests that must pass) with a gate command that checks it; then review what blyte "
    "changed. Do not write the implementation yourself. If a dispatch falls short, dispatch a "
    "follow-up that says what is missing. Keep for yourself only one-line fixes found in "
    "review."
)


def _natural_sort_key(path: Path) -> tuple[int, str]:
    m = re.search(r"(\d+)", path.stem)
    return (int(m.group(1)) if m else 0, path.name)


def _aggregate_dispatches(dispatch_dir: Optional[Path]) -> tuple[float, int, list[str]]:
    if dispatch_dir is None or not dispatch_dir.is_dir():
        return 0.0, 0, []
    cost = 0.0
    outcomes: list[str] = []
    report_files = sorted(dispatch_dir.glob("*.json"), key=_natural_sort_key)
    for rf in report_files:
        try:
            data = json.loads(rf.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cost += float(data.get("cost_usd", 0.0) or 0.0)
                if "outcome" in data and data["outcome"] is not None:
                    outcomes.append(str(data["outcome"]))
        except (json.JSONDecodeError, OSError):
            pass
    return cost, len(report_files), outcomes


class ClaudeCliDriverError(RuntimeError):
    """Raised when the Claude Code CLI cannot be located or invoked."""


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Fallback cost estimate when the CLI reports no cost."""
    rates = MODEL_PRICING.get(model)
    if rates is None:
        return 0.0
    in_rate, out_rate = rates
    return (input_tokens / 1_000_000) * in_rate + (output_tokens / 1_000_000) * out_rate


def _first(payload: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Read the first present key. The CLI's JSON shape is not a stable contract."""
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return default


class ClaudeCliDriver(AgentDriver):
    harness_name: str = "claude-code"
    """Drives the Claude Code CLI in non-interactive mode."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        cli_path: Optional[str] = None,
        permission_mode: str = "bypassPermissions",
        extra_args: Optional[list[str]] = None,
        env: Optional[dict[str, str]] = None,
        container_exec: bool = True,
        mcp_python: Optional[str] = None,
        implementer_model: Optional[str] = None,
        report_dir: Optional[Path | str] = None,
        dispatch_dir: Optional[Path | str] = None,
    ) -> None:
        if cli_path:
            # An explicit path must actually be runnable; failing here beats
            # failing per-turn once a cohort is already burning budget.
            candidate = Path(cli_path)
            if not (candidate.is_file() and os.access(candidate, os.X_OK)):
                raise ClaudeCliDriverError(
                    f"cli_path '{cli_path}' is not an executable file"
                )
            resolved = str(candidate)
        else:
            resolved = shutil.which("claude")
            if not resolved:
                raise ClaudeCliDriverError(
                    "The 'claude' CLI is not on PATH. Install Claude Code or pass cli_path=."
                )
        self.cli_path = resolved
        self.model = model
        self.permission_mode = permission_mode
        self.extra_args = list(extra_args or [])
        self.env = env
        self.container_exec = container_exec
        self.mcp_python = mcp_python or sys.executable
        self.implementer_model = implementer_model
        self.report_dir = Path(report_dir) if report_dir is not None else None
        self.dispatch_dir = Path(dispatch_dir) if dispatch_dir is not None else None
        self.last_dispatch_dir: Optional[Path] = None
        if implementer_model is not None:
            self.harness_name = "claude+blyte"

    @property
    def provides_isolated_execution(self) -> bool:
        """Isolated only with container_exec on: that is what removes host Bash."""
        return self.container_exec

    def _mcp_config(
        self,
        container_id: Optional[str],
        dispatch_dir: Optional[Path] = None,
    ) -> str:
        """Inline MCP config launching configured MCP servers for this run.

        Parameters:
            container_id: Optional Docker container identifier for container_exec server.
            dispatch_dir: Optional directory for blyte dispatch reports.

        Returns:
            JSON-encoded string suitable for --mcp-config argument.
        """
        servers: dict[str, Any] = {}

        # Configure container execution MCP server if running in sandbox
        if container_id:
            env = {
                "SUPERSTATE_EVAL_CONTAINER": container_id,
                "PYTHONPATH": str(REPO_ROOT),
            }
            if self.implementer_model:
                env["BLYTE_IMPLEMENTER_MODEL"] = self.implementer_model
                effective_dispatch_dir = (
                    dispatch_dir
                    or self.dispatch_dir
                    or (self.report_dir / "dispatches" if self.report_dir else None)
                )
                if effective_dispatch_dir is None:
                    effective_dispatch_dir = Path(tempfile.gettempdir()) / "blyte-dispatches"
                effective_dispatch_dir.mkdir(parents=True, exist_ok=True)
                env["BLYTE_DISPATCH_DIR"] = str(effective_dispatch_dir)

            servers[MCP_SERVER_NAME] = {
                "command": self.mcp_python,
                "args": ["-m", "lab.engine.drivers.container_exec_mcp"],
                "cwd": str(REPO_ROOT),
                "env": env,
            }

        return json.dumps({"mcpServers": servers})

    @staticmethod
    def _container_id(container: Any) -> Optional[str]:
        if container is None:
            return None
        ident = getattr(container, "id", None) or getattr(container, "name", None)
        return str(ident) if ident else None

    def _system_prompt(self, container_id: Optional[str]) -> str:
        """Everything this run appends to Claude Code's system prompt, as one string."""
        parts = [AUTONOMY_SYSTEM_PROMPT]
        if container_id:
            parts.append(CONTAINER_EXEC_SYSTEM_PROMPT)
            if self.implementer_model:
                parts.append(OFFLOAD_SYSTEM_PROMPT)
        return "\n\n".join(parts)

    def _build_command(
        self,
        workspace_path: Path,
        conversation_id: Optional[str],
        container: Any = None,
        dispatch_dir: Optional[Path] = None,
    ) -> list[str]:
        """Build the argv. The prompt is NOT included: it goes on stdin.

        Several of these flags are variadic (--add-dir, --disallowedTools,
        --mcp-config), so a trailing positional prompt gets swallowed as another
        value for whichever one came last. Piping the prompt avoids that entirely.
        """
        cmd = [
            self.cli_path,
            "--print",
            "--output-format",
            "json",
            "--model",
            self.model,
            "--permission-mode",
            self.permission_mode,
            "--setting-sources",
            "project,local",
            "--disable-slash-commands",
        ]

        # Restrict host execution if container sandbox is active
        container_id = self._container_id(container) if self.container_exec else None
        disallowed = list(DISALLOWED_TOOLS)
        if container_id:
            # No host shell: it lacks the toolchain and can reach the Docker daemon.
            disallowed.append("Bash")
        cmd += ["--disallowedTools", *disallowed]

        # Pass MCP configuration if container execution is active
        if container_id:
            cmd += [
                "--mcp-config",
                self._mcp_config(container_id, dispatch_dir=dispatch_dir),
                "--strict-mcp-config",
            ]

        # One --append-system-prompt: the CLI keeps only the last when it is repeated, so the
        # offload arm silently lost its container instructions (found 2026-09-27).
        cmd += ["--append-system-prompt", self._system_prompt(container_id)]

        if conversation_id:
            cmd += ["--resume", conversation_id]
        cmd += self.extra_args
        # Keep --add-dir last among our flags; it is variadic, but nothing
        # positional follows it because the prompt is piped.
        cmd += ["--add-dir", str(workspace_path)]
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
        prompt = prompt_override or task.instruction

        run_dispatch_dir: Optional[Path] = None
        if self.implementer_model:
            if self.dispatch_dir is not None:
                run_dispatch_dir = self.dispatch_dir
            elif self.report_dir is not None:
                task_name = getattr(task, "name", "task")
                run_dispatch_dir = self.report_dir / f"dispatches-{task_name}-{uuid.uuid4().hex[:8]}"
            else:
                task_name = getattr(task, "name", "task")
                run_dispatch_dir = Path(tempfile.mkdtemp(prefix=f"blyte-dispatches-{task_name}-"))
            run_dispatch_dir.mkdir(parents=True, exist_ok=True)
            self.last_dispatch_dir = run_dispatch_dir

        cmd = self._build_command(
            workspace_path, conversation_id, container, dispatch_dir=run_dispatch_dir
        )

        def _telemetry_metrics(cli_cost: float) -> tuple[float, dict[str, Any]]:
            if not self.implementer_model:
                return cli_cost, {}
            frontier_cost_usd = cli_cost
            implementer_cost_usd, dispatches, dispatch_outcomes = _aggregate_dispatches(
                run_dispatch_dir
            )
            total = frontier_cost_usd + implementer_cost_usd
            metrics = {
                "frontier_cost_usd": frontier_cost_usd,
                "implementer_cost_usd": implementer_cost_usd,
                "dispatches": dispatches,
                "dispatch_outcomes": dispatch_outcomes,
            }
            return total, metrics

        run_env = dict(os.environ)
        run_env.update(task.env or {})
        if self.env:
            run_env.update(self.env)

        started = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(workspace_path),
                input=prompt,
                capture_output=True,
                text=True,
                timeout=max(1.0, timeout_sec),
                env=run_env,
            )
        except subprocess.TimeoutExpired:
            cost_usd, metrics = _telemetry_metrics(0.0)
            telem = DriverTelemetry(
                success=False,
                raw_response="",
                duration_seconds=time.monotonic() - started,
                cost_usd=cost_usd,
                error_message=f"Agent turn exceeded {timeout_sec:.0f}s and was terminated",
                metrics=metrics,
            )
            if self.implementer_model:
                telem.extra = metrics  # type: ignore[attr-defined]
            return telem
        except OSError as err:
            cost_usd, metrics = _telemetry_metrics(0.0)
            telem = DriverTelemetry(
                success=False,
                raw_response="",
                duration_seconds=time.monotonic() - started,
                cost_usd=cost_usd,
                error_message=f"Failed to invoke the Claude CLI: {err}",
                metrics=metrics,
            )
            if self.implementer_model:
                telem.extra = metrics  # type: ignore[attr-defined]
            return telem

        duration = time.monotonic() - started

        if proc.returncode != 0:
            cost_usd, metrics = _telemetry_metrics(0.0)
            telem = DriverTelemetry(
                success=False,
                raw_response=proc.stdout or "",
                duration_seconds=duration,
                cost_usd=cost_usd,
                error_message=(
                    f"Claude CLI exited {proc.returncode}: {(proc.stderr or '').strip()[:500]}"
                ),
                metrics=metrics,
            )
            if self.implementer_model:
                telem.extra = metrics  # type: ignore[attr-defined]
            return telem

        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as err:
            cost_usd, metrics = _telemetry_metrics(0.0)
            telem = DriverTelemetry(
                success=False,
                raw_response=proc.stdout,
                duration_seconds=duration,
                cost_usd=cost_usd,
                error_message=f"Could not parse Claude CLI JSON output: {err}",
                metrics=metrics,
            )
            if self.implementer_model:
                telem.extra = metrics  # type: ignore[attr-defined]
            return telem

        if isinstance(payload, list):  # defensive: some formats emit an event array
            payload = next(
                (e for e in reversed(payload) if isinstance(e, dict) and e.get("type") == "result"),
                payload[-1] if payload else {},
            )

        usage = _first(payload, "usage", default={}) or {}
        input_tokens = int(_first(usage, "input_tokens", "inputTokens", default=0) or 0)
        output_tokens = int(_first(usage, "output_tokens", "outputTokens", default=0) or 0)
        cost = _first(payload, "total_cost_usd", "cost_usd", "totalCostUsd")
        cli_cost = (
            float(cost)
            if cost is not None
            else estimate_cost_usd(self.model, input_tokens, output_tokens)
        )
        cost_usd, metrics = _telemetry_metrics(cli_cost)

        is_error = bool(_first(payload, "is_error", "isError", default=False))
        text = _first(payload, "result", "text", default="") or ""
        session_id = _first(payload, "session_id", "sessionId")

        telem = DriverTelemetry(
            success=not is_error,
            raw_response=str(text),
            duration_seconds=duration,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            conversation_id=str(session_id) if session_id else conversation_id,
            error_message=(str(text)[:500] if is_error else None),
            metrics=metrics,
        )
        if self.implementer_model:
            telem.extra = metrics  # type: ignore[attr-defined]
        return telem
