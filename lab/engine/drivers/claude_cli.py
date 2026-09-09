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
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
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

# MCP server name; the model sees the tool as mcp__task__run_in_container.
MCP_SERVER_NAME = "task"
REPO_ROOT = Path(__file__).resolve().parents[3]

CONTAINER_EXEC_SYSTEM_PROMPT = (
    "Command execution: this workspace is mounted into a Docker container that holds "
    "the project's toolchain and dependencies. The host has neither, and you have no "
    "shell on it. Run every build, test and inspection command with the "
    f"`mcp__{MCP_SERVER_NAME}__run_in_container` tool. Read and edit files normally — "
    "the workspace directory and the container's /app are the same files."
)


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
        container_exec: bool = True,
        mcp_python: Optional[str] = None,
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

    def _mcp_config(self, container_id: str) -> str:
        """Inline MCP config launching the container-exec server for THIS container."""
        return json.dumps(
            {
                "mcpServers": {
                    MCP_SERVER_NAME: {
                        "command": self.mcp_python,
                        "args": ["-m", "lab.engine.drivers.container_exec_mcp"],
                        "cwd": str(REPO_ROOT),
                        "env": {
                            "SUPERSTATE_EVAL_CONTAINER": container_id,
                            "PYTHONPATH": str(REPO_ROOT),
                        },
                    }
                }
            }
        )

    @staticmethod
    def _container_id(container: Any) -> Optional[str]:
        if container is None:
            return None
        ident = getattr(container, "id", None) or getattr(container, "name", None)
        return str(ident) if ident else None

    def _build_command(
        self,
        workspace_path: Path,
        conversation_id: Optional[str],
        container: Any = None,
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
        ]

        container_id = self._container_id(container) if self.container_exec else None
        if container_id:
            cmd += [
                # No host shell: it lacks the toolchain and can reach the Docker daemon.
                "--disallowedTools",
                "Bash",
                "--mcp-config",
                self._mcp_config(container_id),
                "--strict-mcp-config",
                "--append-system-prompt",
                CONTAINER_EXEC_SYSTEM_PROMPT,
            ]

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
        cmd = self._build_command(workspace_path, conversation_id, container)

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
