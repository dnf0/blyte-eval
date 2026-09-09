"""A live AgentDriver backed by the Claude Code CLI.

The agent process runs on the host (it needs network to reach the API; the task's
sandbox is deliberately network-isolated) with its working directory set to the
run's workspace, which the runner bind-mounts into the container at /app. Edits
the agent makes are therefore visible to the grader, and vice versa.

The tradeoff this makes explicit: the CLI's own shell commands execute on the
host, not inside the task container. For tasks whose toolchain only exists in the
image, pass `exec_in_container=True` so the driver appends a container-exec
instruction to the prompt, or supply a driver that proxies tool calls.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any, Optional

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
    """Drives the Claude Code CLI in non-interactive mode."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        cli_path: Optional[str] = None,
        permission_mode: str = "bypassPermissions",
        extra_args: Optional[list[str]] = None,
        env: Optional[dict[str, str]] = None,
        exec_in_container: bool = False,
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
        self.exec_in_container = exec_in_container

    def _build_command(
        self, prompt: str, workspace_path: Path, conversation_id: Optional[str]
    ) -> list[str]:
        cmd = [
            self.cli_path,
            "--print",
            "--output-format",
            "json",
            "--model",
            self.model,
            "--permission-mode",
            self.permission_mode,
            "--add-dir",
            str(workspace_path),
        ]
        if conversation_id:
            cmd.extend(["--resume", conversation_id])
        cmd.extend(self.extra_args)
        cmd.append(prompt)
        return cmd

    def _augment_prompt(self, prompt: str, container: Any) -> str:
        """Tell the agent to run commands in the task container when asked to."""
        if not self.exec_in_container or container is None:
            return prompt
        container_id = getattr(container, "id", None) or getattr(container, "name", None)
        if not container_id:
            return prompt
        return (
            f"{prompt}\n\n"
            "## Execution environment\n"
            f"The task's toolchain lives in Docker container `{container_id}`, where this "
            "workspace is mounted at /app. Run build and test commands with "
            f"`docker exec {container_id} <cmd>` rather than directly on this host."
        )

    def run(
        self,
        task: TaskSpec,
        workspace_path: Path,
        prompt_override: Optional[str] = None,
        conversation_id: Optional[str] = None,
        timeout_sec: float = 3600.0,
        container: Any = None,
    ) -> DriverTelemetry:
        prompt = self._augment_prompt(prompt_override or task.instruction, container)
        cmd = self._build_command(prompt, workspace_path, conversation_id)

        run_env = dict(os.environ)
        run_env.update(task.env or {})
        if self.env:
            run_env.update(self.env)

        started = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(workspace_path),
                capture_output=True,
                text=True,
                timeout=max(1.0, timeout_sec),
                env=run_env,
            )
        except subprocess.TimeoutExpired:
            return DriverTelemetry(
                success=False,
                raw_response="",
                duration_seconds=time.monotonic() - started,
                error_message=f"Agent turn exceeded {timeout_sec:.0f}s and was terminated",
            )
        except OSError as err:
            return DriverTelemetry(
                success=False,
                raw_response="",
                duration_seconds=time.monotonic() - started,
                error_message=f"Failed to invoke the Claude CLI: {err}",
            )

        duration = time.monotonic() - started

        if proc.returncode != 0:
            return DriverTelemetry(
                success=False,
                raw_response=proc.stdout or "",
                duration_seconds=duration,
                error_message=(
                    f"Claude CLI exited {proc.returncode}: {(proc.stderr or '').strip()[:500]}"
                ),
            )

        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as err:
            return DriverTelemetry(
                success=False,
                raw_response=proc.stdout,
                duration_seconds=duration,
                error_message=f"Could not parse Claude CLI JSON output: {err}",
            )

        if isinstance(payload, list):  # defensive: some formats emit an event array
            payload = next(
                (e for e in reversed(payload) if isinstance(e, dict) and e.get("type") == "result"),
                payload[-1] if payload else {},
            )

        usage = _first(payload, "usage", default={}) or {}
        input_tokens = int(_first(usage, "input_tokens", "inputTokens", default=0) or 0)
        output_tokens = int(_first(usage, "output_tokens", "outputTokens", default=0) or 0)
        cost = _first(payload, "total_cost_usd", "cost_usd", "totalCostUsd")
        cost_usd = (
            float(cost)
            if cost is not None
            else estimate_cost_usd(self.model, input_tokens, output_tokens)
        )

        is_error = bool(_first(payload, "is_error", "isError", default=False))
        text = _first(payload, "result", "text", default="") or ""
        session_id = _first(payload, "session_id", "sessionId")

        return DriverTelemetry(
            success=not is_error,
            raw_response=str(text),
            duration_seconds=duration,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            conversation_id=str(session_id) if session_id else conversation_id,
            error_message=(str(text)[:500] if is_error else None),
        )
