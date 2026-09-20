"""Driver for running evaluation tasks against Google Antigravity CLI (agy).

Executes agent turns using agy's non-interactive print mode, extracting structured
JSON telemetry and providing a workspace-scoped bridge script (`run-in-container`)
for running commands inside the task's Docker sandbox.
"""

from __future__ import annotations

import json
import logging
import math
import os
from pathlib import Path
import shutil
import stat
import subprocess
import time
from typing import Any, Optional

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.base import AgentDriver, DriverTelemetry

logger = logging.getLogger("superstate_eval.drivers.agy_cli")

DEFAULT_MODEL = "gemini-3.8-flash-high"

# Standard pricing table per 1M tokens ($/MTok)
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # model: (input_per_mtok, output_per_mtok)
    # Gemini 3.8 Flash official introductory developer pricing ($0.75 in / $3.75 out per MTok)
    "gemini-3.8-flash-high": (0.75, 3.75),
    "gemini-3.8-flash": (0.75, 3.75),
    "gemini-2.5-flash": (0.15, 0.60),
    "gemini-2.5-pro": (1.25, 5.00),
}

CONTAINER_GUIDANCE_TEMPLATE = """
## Environment & Execution Contract
The project dependencies, compilers, and test runners reside inside the Docker container.
To run commands, tests, or builds in the project environment, use:
  `./run-in-container <command>`
Example: `./run-in-container pytest tests/`
CRITICAL: Confine all inspections, searches, and commands strictly to this workspace directory and the container. Do NOT inspect host processes, parent directories, or external repositories outside this workspace.
"""


class AgyCliDriverError(RuntimeError):
    """Raised when the agy driver fails unrecoverably."""


# agy exposes one model per effort level (gemini-3.8-flash-low/-medium/-high).
# Effort changes how many tokens are spent, not the price per token, so an effort
# variant is priced as its base model rather than needing its own entry.
EFFORT_SUFFIXES = ("-low", "-medium", "-high", "-xhigh", "-max")


def base_model_name(model: str) -> str:
    """Strip an effort suffix so variants resolve to the base model's pricing."""
    for suffix in EFFORT_SUFFIXES:
        if model.endswith(suffix):
            return model[: -len(suffix)]
    return model


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate USD cost for a given model and token counts.

    Returns 0.0 for an unpriced model rather than guessing: cost per solve is a
    headline metric of this evaluation and a fabricated rate would corrupt it.
    """
    pricing = MODEL_PRICING.get(model) or MODEL_PRICING.get(base_model_name(model))
    if not pricing:
        logger.warning(
            "No pricing for model %s: cost will be reported as $0.00, not estimated.", model
        )
        return 0.0
    in_rate, out_rate = pricing
    return (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000.0


def _resolve_cli_path(candidate: Optional[str] = None) -> str:
    """Locate and validate the agy executable path."""
    if candidate:
        path = Path(candidate)
        if not path.is_file() or not os.access(path, os.X_OK):
            raise AgyCliDriverError(f"Specified agy binary is not an executable file: {candidate}")
        return str(path)

    # Prefer agy.real if present to avoid python wrapper stdin blocking
    common_paths = [
        Path.home() / ".local/bin/agy.real",
        Path.home() / ".local/bin/agy",
        Path("/usr/local/bin/agy.real"),
        Path("/usr/local/bin/agy"),
    ]
    for p in common_paths:
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)

    which_real = shutil.which("agy.real")
    if which_real:
        return which_real

    which_agy = shutil.which("agy")
    if which_agy:
        return which_agy

    raise AgyCliDriverError("Could not locate an executable agy or agy.real binary on PATH.")


class AgyCliDriver(AgentDriver):
    harness_name: str = "agy"
    #: agy has no --disallowedTools and no per-invocation --mcp-config, so its
    #: shell tool cannot be removed. The agent keeps a host shell and can read
    #: the task's tests/ directory directly. See docs for the mitigations.
    provides_isolated_execution: bool = False

    """Driver executing agent sessions via the Antigravity CLI (agy)."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        cli_path: Optional[str] = None,
        extra_args: Optional[list[str]] = None,
        env: Optional[dict[str, str]] = None,
        container_exec: bool = True,
    ) -> None:
        """Initialize the agy driver.

        Args:
            model: Model identifier for agy (defaults to gemini-3.8-flash-high).
            cli_path: Explicit path to the agy or agy.real executable.
            extra_args: Additional command-line flags to pass to agy.
            env: Extra environment variables for the agy process.
            container_exec: If True, writes `./run-in-container` when a container is present.
        """
        self.model = model
        self.cli_path = _resolve_cli_path(cli_path)
        self.extra_args = list(extra_args) if extra_args else []
        self.env = dict(env) if env else {}
        self.container_exec = container_exec

    def _setup_container_bridge(self, workspace_path: Path, container: Any) -> None:
        """Create a `./run-in-container` wrapper script in workspace pointing to container.

        Generates a transparent bridge script that routes commands through
        `superstate shunt` when available to bound token context growth while
        preserving exit codes and fallback semantics.
        """
        # Determine container identifier from container object or string representation
        container_id = getattr(container, "id", None) or getattr(container, "name", str(container))
        script_path = workspace_path / "run-in-container"

        # Build wrapper script checking for superstate availability and shunting toggle
        script_content = (
            "#!/usr/bin/env bash\n"
            "set -o pipefail\n\n"
            'if [ "${SUPERSTATE_SHUNT_ENABLED:-1}" = "1" ] && command -v superstate >/dev/null 2>&1; then\n'
            f'    exec superstate shunt --threshold-lines 50 -- docker exec -i -w /app {container_id} "$@"\n'
            "else\n"
            f'    exec docker exec -i -w /app {container_id} "$@"\n'
            "fi\n"
        )
        script_path.write_text(script_content, encoding="utf-8")

        # Ensure executable permissions: rwxr-xr-x (0o755)
        current_mode = script_path.stat().st_mode
        script_path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    def _build_command(
        self,
        prompt: str,
        conversation_id: Optional[str] = None,
        timeout_sec: float = 3600.0,
        workspace_path: Optional[Path] = None,
    ) -> list[str]:
        """Construct the argv list for the agy invocation."""
        cmd = [
            self.cli_path,
            "--model",
            self.model,
            "--output-format",
            "json",
            "--dangerously-skip-permissions",
            # agy's own --print-timeout defaults to 5m. Without this every turn
            # longer than that is truncated by the CLI regardless of the budget
            # the harness granted, and the arm is scored as having failed.
            "--print-timeout",
            f"{max(60, int(math.ceil(timeout_sec)))}s",
        ]

        # agy resolves file paths against its own project root, not the process
        # cwd. Without this the agent wrote plan.md into the user's home directory
        # and the harness never found it.
        if workspace_path is not None:
            cmd.extend(["--add-dir", str(workspace_path)])

        if conversation_id:
            cmd.extend(["--conversation", conversation_id])

        if self.extra_args:
            cmd.extend(self.extra_args)

        cmd.extend(["--print", prompt])
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
        """Execute a single agent turn using agy."""
        start_time = time.monotonic()
        prompt = prompt_override or task.instruction

        # If a sandbox container is present and container execution is enabled,
        # provision the workspace bridge script and guide the agent.
        if container is not None and self.container_exec:
            self._setup_container_bridge(workspace_path, container)
            prompt = prompt + CONTAINER_GUIDANCE_TEMPLATE

        cmd = self._build_command(
            prompt=prompt,
            conversation_id=conversation_id,
            timeout_sec=timeout_sec,
            workspace_path=workspace_path,
        )
        run_env = os.environ.copy()
        run_env.update(self.env)

        logger.info(
            "Executing agy turn (model=%s, timeout=%.1fs, conversation_id=%s)",
            self.model,
            timeout_sec,
            conversation_id,
        )

        try:
            # Note: stdin=DEVNULL ensures agy does not block waiting for interactive input.
            process = subprocess.Popen(
                cmd,
                cwd=str(workspace_path),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=run_env,
            )
            stdout, stderr = process.communicate(timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            elapsed = time.monotonic() - start_time
            logger.warning("agy turn exceeded timeout of %.1fs", timeout_sec)
            return DriverTelemetry(
                success=False,
                raw_response=stdout or "",
                duration_seconds=elapsed,
                error_message=f"agy turn exceeded timeout of {timeout_sec:.1f}s",
                conversation_id=conversation_id,
            )
        except Exception as exc:
            elapsed = time.monotonic() - start_time
            logger.error("Failed to invoke agy: %s", exc)
            return DriverTelemetry(
                success=False,
                raw_response="",
                duration_seconds=elapsed,
                error_message=f"Driver execution failed: {exc}",
                conversation_id=conversation_id,
            )

        elapsed = time.monotonic() - start_time

        if process.returncode != 0:
            err_msg = (stderr or stdout or "").strip()
            logger.warning("agy process exited with code %d: %s", process.returncode, err_msg)
            return DriverTelemetry(
                success=False,
                raw_response=stdout,
                duration_seconds=elapsed,
                error_message=f"agy exited {process.returncode}: {err_msg}",
                conversation_id=conversation_id,
            )

        try:
            data = json.loads(stdout)
        except Exception as exc:
            logger.warning("Failed to parse agy JSON output: %s", exc)
            return DriverTelemetry(
                success=False,
                raw_response=stdout,
                duration_seconds=elapsed,
                error_message=f"Could not parse agy output as JSON: {exc}",
                conversation_id=conversation_id,
            )

        conv_id = data.get("conversation_id") or conversation_id
        response = data.get("response", "")
        reported_duration = float(data.get("duration_seconds", elapsed))

        usage = data.get("usage", {})
        input_tokens = int(usage.get("input_tokens", 0))
        output_tokens = int(usage.get("output_tokens", 0))

        cost_usd = estimate_cost_usd(self.model, input_tokens, output_tokens)
        status_str = str(data.get("status", "SUCCESS")).upper()
        success = (status_str == "SUCCESS")
        raw_error = data.get("error_message") or data.get("error")
        error_message = None if success else (str(raw_error) if raw_error else (response if response else f"agy exited with status {status_str}"))

        return DriverTelemetry(
            success=success,
            raw_response=response,
            duration_seconds=reported_duration,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            conversation_id=conv_id,
            error_message=error_message,
        )
