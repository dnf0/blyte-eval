"""Codex CLI as the orchestrating harness (2026-09-30), the counterpart of ClaudeCliDriver.

Same conditions as the Claude arms: the task's toolchain is reached only through the container MCP
server (`run_in_container`, and `dispatch_blyte` when an implementer model is set), Codex's own host
tools are switched off (shell, unified exec, JS REPL, browser, computer use, web search), and the
operator's Codex setup is kept out: HOME and CODEX_HOME point at a fresh directory whose only
content is a symlink to the operator's auth.json, so no config, AGENTS.md, skills or rules load
and the credentials are never copied or read. Under a ChatGPT login Codex reports tokens but no
cost, so the frontier cost is recorded as 0 and the tokens are kept in the metrics.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Optional
import uuid

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.base import AgentDriver, DriverTelemetry
from lab.engine.drivers.claude_cli import (
    AUTONOMY_SYSTEM_PROMPT,
    MCP_SERVER_NAME,
    OFFLOAD_SYSTEM_PROMPT,
    REPO_ROOT,
    _aggregate_dispatches,
)

DEFAULT_MODEL = "gpt-5.6-terra"

# Codex's host-side tools, switched off so the container is the only place commands run.
DISABLED_FEATURES: tuple[str, ...] = ("shell_tool", "unified_exec", "js_repl", "browser_use", "computer_use")

CONTAINER_EXEC_PROMPT = (
    "Command execution: this workspace is mounted into a Docker container that holds the "
    "project's toolchain and dependencies. You have no shell on the host. Run every build, test "
    "and inspection command with the `run_in_container` tool. Edit files with your file-editing "
    "tool: the workspace directory and the container's /app are the same files."
)


class CodexCliDriverError(RuntimeError):
    """Raised when the Codex CLI cannot be used."""


def parse_events(stdout: str) -> tuple[str, dict[str, int], Optional[str], Optional[str]]:
    """From `codex exec --json` output: the last agent message, the summed token usage, the
    thread id, and the error of a failed turn (None when the turn completed)."""
    text, thread, error = "", None, None
    usage = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0, "reasoning_output_tokens": 0}
    for line in stdout.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        kind = e.get("type")
        item = e.get("item") or {}
        if kind == "thread.started":
            thread = e.get("thread_id") or thread
        elif kind == "item.completed" and item.get("type") == "agent_message":
            text = str(item.get("text") or text)
        elif kind == "turn.completed":
            for k in usage:
                usage[k] += int((e.get("usage") or {}).get(k) or 0)
        elif kind == "turn.failed":
            error = str((e.get("error") or {}).get("message") or "turn failed")
    return text, usage, thread, error


class CodexCliDriver(AgentDriver):
    harness_name: str = "codex"
    """Drives `codex exec` non-interactively."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        cli_path: Optional[str] = None,
        reasoning_effort: str = "medium",
        implementer_model: Optional[str] = None,
        report_dir: Optional[Path | str] = None,
        mcp_python: Optional[str] = None,
        auth_file: Optional[Path | str] = None,
    ) -> None:
        resolved = cli_path or shutil.which("codex")
        if not resolved or not os.access(resolved, os.X_OK):
            raise CodexCliDriverError("The 'codex' CLI is not on PATH. Install Codex or pass cli_path=.")
        self.cli_path = str(resolved)
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.implementer_model = implementer_model
        self.report_dir = Path(report_dir) if report_dir is not None else None
        self.mcp_python = mcp_python or sys.executable
        self.auth_file = Path(auth_file) if auth_file else Path.home() / ".codex" / "auth.json"
        self.last_dispatch_dir: Optional[Path] = None
        if implementer_model is not None:
            self.harness_name = "codex+blyte"

    @property
    def provides_isolated_execution(self) -> bool:
        return True

    @staticmethod
    def _container_id(container: Any) -> Optional[str]:
        if container is None:
            return None
        ident = getattr(container, "id", None) or getattr(container, "name", None)
        return str(ident) if ident else None

    def _home(self) -> Path:
        """A fresh HOME/CODEX_HOME holding only a symlink to the operator's auth.json."""
        home = Path(tempfile.mkdtemp(prefix="codex-home-"))
        (home / ".codex").mkdir()
        if self.auth_file.exists():
            (home / ".codex" / "auth.json").symlink_to(self.auth_file)
        return home

    def _prompt(self, instruction: str, container_id: Optional[str]) -> str:
        parts = [AUTONOMY_SYSTEM_PROMPT]
        if container_id:
            parts.append(CONTAINER_EXEC_PROMPT)
            if self.implementer_model:
                parts.append(OFFLOAD_SYSTEM_PROMPT)
        return "\n\n".join(parts) + "\n\n## Task\n\n" + instruction

    def _build_command(
        self, workspace_path: Path, container_id: Optional[str], dispatch_dir: Optional[Path]
    ) -> list[str]:
        cmd = [
            self.cli_path, "exec", "--json", "--skip-git-repo-check",
            "-m", self.model,
            "-c", f"model_reasoning_effort={self.reasoning_effort}",
            "--sandbox", "workspace-write",
            "-C", str(workspace_path),
            "-c", "web_search=disabled",
        ]
        for feature in DISABLED_FEATURES:
            cmd += ["--disable", feature]
        if container_id:
            env = {"BLYTE_EVAL_CONTAINER": container_id, "PYTHONPATH": str(REPO_ROOT)}
            if self.implementer_model and dispatch_dir is not None:
                env["BLYTE_IMPLEMENTER_MODEL"] = self.implementer_model
                env["BLYTE_DISPATCH_DIR"] = str(dispatch_dir)
            env_toml = "{" + ", ".join(f"{k}={json.dumps(v)}" for k, v in env.items()) + "}"
            srv = f"mcp_servers.{MCP_SERVER_NAME}"
            cmd += [
                "-c", f"{srv}.command={json.dumps(self.mcp_python)}",
                "-c", f'{srv}.args=["-m", "lab.engine.drivers.container_exec_mcp"]',
                "-c", f"{srv}.cwd={json.dumps(str(REPO_ROOT))}",
                "-c", f"{srv}.env={env_toml}",
                "-c", f'{srv}.default_tools_approval_mode="approve"',
            ]
        cmd.append("-")  # the prompt comes on stdin
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
        container_id = self._container_id(container)
        dispatch_dir: Optional[Path] = None
        if self.implementer_model:
            name = getattr(task, "name", "task")
            base = self.report_dir or Path(tempfile.gettempdir())
            dispatch_dir = base / f"dispatches-{name}-{uuid.uuid4().hex[:8]}"
            dispatch_dir.mkdir(parents=True, exist_ok=True)
            self.last_dispatch_dir = dispatch_dir
        cmd = self._build_command(workspace_path, container_id, dispatch_dir)
        prompt = self._prompt(prompt_override or task.instruction, container_id)
        home = self._home()
        env = dict(os.environ)
        env.update(task.env or {})
        env.update({"HOME": str(home), "CODEX_HOME": str(home / ".codex")})

        def metrics(usage: dict[str, int]) -> tuple[float, dict[str, Any]]:
            m: dict[str, Any] = {"frontier_tokens": usage}
            if not self.implementer_model:
                return 0.0, m
            implementer_cost, dispatches, outcomes = _aggregate_dispatches(dispatch_dir)
            m.update(frontier_cost_usd=0.0, implementer_cost_usd=implementer_cost,
                     dispatches=dispatches, dispatch_outcomes=outcomes)
            return implementer_cost, m

        started = time.monotonic()
        try:
            proc = subprocess.run(cmd, cwd=str(workspace_path), input=prompt, capture_output=True,
                                  text=True, timeout=max(1.0, timeout_sec), env=env)
        except subprocess.TimeoutExpired:
            cost, m = metrics({})
            t = DriverTelemetry(success=False, raw_response="", duration_seconds=time.monotonic() - started,
                                cost_usd=cost, error_message=f"Agent turn exceeded {timeout_sec:.0f}s and was terminated",
                                metrics=m)
            t.extra = m  # type: ignore[attr-defined]
            return t
        finally:
            shutil.rmtree(home, ignore_errors=True)
        duration = time.monotonic() - started
        text, usage, thread, error = parse_events(proc.stdout or "")
        cost, m = metrics(usage)
        failed = proc.returncode != 0 or error is not None
        t = DriverTelemetry(
            success=not failed,
            raw_response=text,
            duration_seconds=duration,
            input_tokens=usage["input_tokens"],
            output_tokens=usage["output_tokens"] + usage["reasoning_output_tokens"],
            cost_usd=cost,
            conversation_id=thread,
            error_message=(error or (proc.stderr or "").strip()[-500:] or f"codex exited {proc.returncode}") if failed else None,
            metrics=m,
        )
        t.extra = m  # type: ignore[attr-defined]
        return t
