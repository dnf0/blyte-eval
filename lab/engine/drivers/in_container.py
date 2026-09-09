"""An AgentDriver that runs the agent CLI inside the task sandbox.

This is the isolated execution path. The harness uses the Docker API from the
host to start the turn; the agent itself runs wholly inside the container, where
there is no Docker socket, no host filesystem, and no path to the task's tests/
directory. Nothing needs to be restricted, because nothing is reachable.

Consequences worth noting:
* The agent's shell is the task toolchain, so no bridge script and no MCP shim.
* The CLI's own Bash tool is safe to leave enabled -- it is already confined.
* The prompt is piped in through a file written inside the container, so no
  host path is shared and nothing lands in /app to pollute the graded diff.
"""

from __future__ import annotations

import base64
import json
import logging
import math
import shlex
import time
from pathlib import Path
from typing import Any, Optional

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.base import AgentDriver, DriverTelemetry

logger = logging.getLogger("superstate_eval.drivers.in_container")

DEFAULT_MODEL = "claude-opus-5"
AGENT_CLI = "/opt/agent/bin/claude"
PROMPT_PATH = "/tmp/superstate-eval-prompt"

# Per-MTok USD. Used only when the CLI reports no cost of its own; never guessed.
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
}


class InContainerDriverError(RuntimeError):
    """Raised when the in-container agent cannot be invoked."""


def _first(payload: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return default


class InContainerClaudeDriver(AgentDriver):
    harness_name: str = "claude-code"
    """Runs Claude Code inside the task container via the Docker exec API."""

    provides_isolated_execution: bool = True

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        cli_path: str = AGENT_CLI,
        permission_mode: str = "bypassPermissions",
        env: Optional[dict[str, str]] = None,
        extra_args: Optional[list[str]] = None,
        user: str = "agent",
    ) -> None:
        self.model = model
        self.cli_path = cli_path
        self.permission_mode = permission_mode
        self.env = dict(env or {})
        self.extra_args = list(extra_args or [])
        # The CLI refuses to bypass permission prompts as root, and an unattended
        # agent should not be root regardless.
        self.user = user

    def _shell_command(
        self, prompt: str, timeout_sec: float, conversation_id: Optional[str] = None
    ) -> str:
        """Build the shell line executed inside the container.

        The prompt is base64'd so no quoting or newline in it can alter the
        command, and `timeout` bounds the turn from inside -- docker exec has no
        timeout of its own, so without it a hung agent would block forever.
        """
        encoded = base64.b64encode(prompt.encode("utf-8")).decode("ascii")
        argv = [
            self.cli_path,
            "--print",
            "--output-format",
            "json",
            "--model",
            self.model,
            "--permission-mode",
            self.permission_mode,
        ]
        if conversation_id:
            argv += ["--resume", conversation_id]
        argv += self.extra_args
        cli = " ".join(shlex.quote(part) for part in argv)
        bounded = max(60, int(math.ceil(timeout_sec)))
        return (
            f"printf %s {shlex.quote(encoded)} | base64 -d > {PROMPT_PATH} && "
            f"cd /app && timeout {bounded}s {cli} < {PROMPT_PATH}"
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
        if container is None:
            raise InContainerDriverError(
                "InContainerClaudeDriver requires a container: it exists precisely so "
                "the agent never runs on the host."
            )

        prompt = prompt_override or task.instruction
        command = self._shell_command(prompt, timeout_sec, conversation_id)

        env = dict(self.env)
        env.update(task.env or {})

        started = time.monotonic()
        try:
            exec_res = container.exec_run(
                ["/bin/sh", "-lc", command],
                workdir="/app",
                environment=env or None,
                user=self.user,
                demux=True,
            )
        except Exception as err:
            return DriverTelemetry(
                success=False,
                raw_response="",
                duration_seconds=time.monotonic() - started,
                error_message=f"Failed to exec the agent inside the container: {err}",
            )
        duration = time.monotonic() - started

        exit_code, streams = (
            (exec_res[0], exec_res[1]) if isinstance(exec_res, tuple) else (
                getattr(exec_res, "exit_code", 1), getattr(exec_res, "output", (b"", b""))
            )
        )
        stdout_raw, stderr_raw = streams if isinstance(streams, tuple) else (streams, b"")
        stdout = (stdout_raw or b"").decode("utf-8", errors="replace")
        stderr = (stderr_raw or b"").decode("utf-8", errors="replace")

        if exit_code == 124:
            return DriverTelemetry(
                success=False,
                raw_response=stdout,
                duration_seconds=duration,
                error_message=f"Agent turn exceeded {timeout_sec:.0f}s and was terminated",
            )
        if exit_code != 0:
            return DriverTelemetry(
                success=False,
                raw_response=stdout,
                duration_seconds=duration,
                error_message=f"Agent CLI exited {exit_code}: {stderr.strip()[:500]}",
            )

        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError as err:
            return DriverTelemetry(
                success=False,
                raw_response=stdout,
                duration_seconds=duration,
                error_message=f"Could not parse agent JSON output: {err}",
            )

        usage = _first(payload, "usage", default={}) or {}
        input_tokens = int(_first(usage, "input_tokens", "inputTokens", default=0) or 0)
        output_tokens = int(_first(usage, "output_tokens", "outputTokens", default=0) or 0)
        cost = _first(payload, "total_cost_usd", "cost_usd")
        if cost is None:
            rates = MODEL_PRICING.get(self.model)
            cost_usd = (
                0.0
                if rates is None
                else (input_tokens / 1e6) * rates[0] + (output_tokens / 1e6) * rates[1]
            )
        else:
            cost_usd = float(cost)

        is_error = bool(_first(payload, "is_error", "isError", default=False))
        text = str(_first(payload, "result", "response", "text", default="") or "")
        session_id = _first(payload, "session_id", "sessionId")

        return DriverTelemetry(
            success=not is_error,
            raw_response=text,
            duration_seconds=duration,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            conversation_id=str(session_id) if session_id else conversation_id,
            error_message=text[:500] if is_error else None,
        )
