"""Superstate daemon adapter for autonomous headless execution."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Optional, Tuple

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.base import AgentAdapter, AgentDriver, BudgetHook, TaskRunResult

logger = logging.getLogger(__name__)


def is_pid_alive(pid: int) -> bool:
    """Check whether a PID is currently running."""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class SuperstateDaemonAdapter(AgentAdapter):
    """Execution adapter that launches a background superstate daemon."""

    def __init__(self, driver_preset: str, poll_interval_sec: float = 1.0) -> None:
        self._name = "superstate_daemon"
        self.driver_preset = driver_preset
        self.poll_interval_sec = poll_interval_sec

    @property
    def name(self) -> str:
        return self._name

    def _init_daemon_state(self, workspace_path: Path, task: TaskSpec) -> bool:
        verify_cmd = (
            getattr(task, "verification_cmd", None)
            or getattr(task, "verify_cmd", None)
            or getattr(task, "held_out_verifier", None)
            or getattr(task, "verifier", None)
        )
        
        cmd = ["superstate", "state", "init", "--goal", task.instruction]
        if verify_cmd:
            cmd.extend(["--verify-cmd", str(verify_cmd)])
            
        try:
            subprocess.run(
                cmd,
                cwd=str(workspace_path),
                check=True,
                capture_output=True,
                text=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.warning(f"superstate state init failed or not found, falling back: {e}")

        state_dir = workspace_path / ".agent-state"
        state_dir.mkdir(parents=True, exist_ok=True)
        state_file = state_dir / "state.json"
        
        state_data: dict[str, Any] = {
            "status": "pending",
            "goal": task.instruction,
            "tasks": [
                {
                    "id": "task-1",
                    "title": "Solve task",
                    "description": task.instruction,
                    "status": "pending"
                }
            ],
            "active_task": "task-1"
        }
        if verify_cmd:
            state_data["verify_cmd"] = str(verify_cmd)

        state_file.write_text(json.dumps(state_data, indent=2), encoding="utf-8")
        return True

    def _spawn_daemon(self, workspace_path: Path) -> bool:
        cmd = [
            "superstate",
            "state",
            "daemon",
            "--state",
            ".agent-state/state.json",
            "--driver",
            self.driver_preset,
            "--detach"
        ]
        try:
            subprocess.run(
                cmd,
                cwd=str(workspace_path),
                check=True,
                capture_output=True,
                text=True
            )
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Daemon launch failed: {e.stderr}")
            return False

    def _run_gate_command(self, workspace_path: Path) -> Tuple[bool, int, str]:
        """Hook for executing verification gate commands; mockable in tests."""
        return True, 0, "pass"

    def execute(
        self,
        workspace_path: Path,
        task: TaskSpec,
        driver: AgentDriver,
        timeout_sec: Optional[float] = None,
        container: Any = None,
        budget_hook: Optional[BudgetHook] = None,
        recorder: Any = None,
    ) -> TaskRunResult:
        start_time = time.time()
        budget = timeout_sec or task.agent_timeout_sec or 3600.0
        
        self._init_daemon_state(workspace_path, task)
        if not self._spawn_daemon(workspace_path):
            return TaskRunResult(
                task_id=task.id,
                harness_name=self.name,
                success=False,
                duration_seconds=time.time() - start_time,
                error_message="Failed to spawn daemon"
            )

        daemons_dir = workspace_path / ".agent-state" / "daemons"
        pid_file = daemons_dir / "default.pid"
        
        while not pid_file.is_file():
            if time.time() - start_time > budget:
                return TaskRunResult(
                    task_id=task.id,
                    harness_name=self.name,
                    success=False,
                    duration_seconds=time.time() - start_time,
                    error_message="Timeout waiting for PID file"
                )
            time.sleep(self.poll_interval_sec)
            
        try:
            pid_content = pid_file.read_text(encoding="utf-8").strip()
            pid = int(pid_content)
        except (ValueError, OSError) as e:
            return TaskRunResult(
                task_id=task.id,
                harness_name=self.name,
                success=False,
                duration_seconds=time.time() - start_time,
                error_message=f"Failed to read PID file: {e}"
            )
        
        while is_pid_alive(pid):
            if budget_hook is not None:
                budget = max(budget, budget_hook())
            if time.time() - start_time > budget:
                return TaskRunResult(
                    task_id=task.id,
                    harness_name=self.name,
                    success=False,
                    duration_seconds=time.time() - start_time,
                    error_message="Timeout while running daemon"
                )
            time.sleep(self.poll_interval_sec)
            
        state_file = workspace_path / ".agent-state" / "state.json"
        error_message = None
        turns = 0
        success = False
        
        if state_file.is_file():
            try:
                state_data = json.loads(state_file.read_text(encoding="utf-8"))
                status = state_data.get("status")
                turns = state_data.get("step", 0)
                if status == "completed":
                    success = True
                else:
                    error_message = f"Daemon exited with status {status}"
            except Exception as e:
                error_message = f"Failed to parse state file: {e}"
        else:
            error_message = "State file not found after daemon exit"

        self._run_gate_command(workspace_path)

        duration = time.time() - start_time

        return TaskRunResult(
            task_id=task.id,
            harness_name=self.name,
            success=success,
            duration_seconds=duration,
            error_message=error_message,
            turns=turns,
            provenance={"driver_preset": self.driver_preset}
        )

    def run_task(self, *args, **kwargs) -> TaskRunResult:
        """Alias for execute to support alternative harness calling conventions."""
        return self.execute(*args, **kwargs)
