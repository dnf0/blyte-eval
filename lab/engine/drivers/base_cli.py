"""Shared plumbing for agent drivers that shell out to a CLI.

Subclasses supply the argv and the response parsing; everything else -- prompt
delivery, timeouts, environment, and turning failures into honest telemetry
rather than fabricated success -- lives here.
"""

from __future__ import annotations

import abc
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

logger = logging.getLogger("blyte_eval.drivers")


class CliDriverError(RuntimeError):
    """Raised when the agent CLI cannot be located or invoked."""


def resolve_cli(cli_path: Optional[str], command_name: str) -> str:
    """Resolve an explicit path or a PATH lookup, failing early either way."""
    if cli_path:
        candidate = Path(cli_path)
        if not (candidate.is_file() and os.access(candidate, os.X_OK)):
            raise CliDriverError(f"cli_path '{cli_path}' is not an executable file")
        return str(candidate)
    resolved = shutil.which(command_name)
    if not resolved:
        raise CliDriverError(
            f"The '{command_name}' CLI is not on PATH. Install it or pass cli_path=."
        )
    return resolved


def first(payload: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Read the first present key. CLI JSON shapes are not stable contracts."""
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return default


def estimate_cost_usd(
    input_tokens: int,
    output_tokens: int,
    input_per_mtok: Optional[float],
    output_per_mtok: Optional[float],
) -> float:
    """Cost from explicit rates. Returns 0.0 when rates are unknown.

    Deliberately never guesses a price: a fabricated cost would flow straight
    into cost-per-solve, which is a headline metric of this evaluation.
    """
    if input_per_mtok is None or output_per_mtok is None:
        return 0.0
    return (input_tokens / 1_000_000) * input_per_mtok + (
        output_tokens / 1_000_000
    ) * output_per_mtok


class BaseCliDriver(AgentDriver):
    """Runs an agent CLI once per turn, with the prompt delivered on stdin."""

    def __init__(
        self,
        model: str,
        cli_path: Optional[str],
        command_name: str,
        extra_args: Optional[list[str]] = None,
        env: Optional[dict[str, str]] = None,
        input_cost_per_mtok: Optional[float] = None,
        output_cost_per_mtok: Optional[float] = None,
    ) -> None:
        self.cli_path = resolve_cli(cli_path, command_name)
        self.model = model
        self.extra_args = list(extra_args or [])
        self.env = env
        self.input_cost_per_mtok = input_cost_per_mtok
        self.output_cost_per_mtok = output_cost_per_mtok

    @abc.abstractmethod
    def build_command(
        self,
        workspace_path: Path,
        conversation_id: Optional[str],
        timeout_sec: float,
        container: Any = None,
    ) -> list[str]:
        """Build argv. The prompt is delivered on stdin, never as a positional."""

    @abc.abstractmethod
    def parse_payload(self, payload: dict[str, Any], measured_duration: float) -> DriverTelemetry:
        """Turn the CLI's JSON result into telemetry."""

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
        cmd = self.build_command(workspace_path, conversation_id, timeout_sec, container)

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
                error_message=f"Failed to invoke {self.cli_path}: {err}",
            )

        duration = time.monotonic() - started

        if proc.returncode != 0:
            return DriverTelemetry(
                success=False,
                raw_response=proc.stdout or "",
                duration_seconds=duration,
                error_message=(
                    f"{Path(self.cli_path).name} exited {proc.returncode}: "
                    f"{(proc.stderr or '').strip()[:500]}"
                ),
            )

        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as err:
            return DriverTelemetry(
                success=False,
                raw_response=proc.stdout,
                duration_seconds=duration,
                error_message=f"Could not parse CLI JSON output: {err}",
            )

        if isinstance(payload, list):
            payload = next(
                (e for e in reversed(payload) if isinstance(e, dict) and "usage" in e),
                payload[-1] if payload else {},
            )

        return self.parse_payload(payload, duration)
