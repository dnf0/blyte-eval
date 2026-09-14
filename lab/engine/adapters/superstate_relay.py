import subprocess
from pathlib import Path
from typing import Any, Optional

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.base import AgentAdapter, TaskRunResult, BudgetHook, DriverTelemetry
from lab.engine.drivers.claude_cli import ClaudeCliDriver
from lab.engine.drivers.agy_cli import AgyCliDriver


class SuperstateRelayAdapter(AgentAdapter):
    """Adapter for a two-stage collaboration between Claude and Agy."""

    def __init__(self, max_retries: int = 2) -> None:
        self.max_retries = max_retries

    @property
    def name(self) -> str:
        return "superstate_relay"

    def execute(
        self,
        workspace_path: Path,
        task: TaskSpec,
        driver: Any,
        timeout_sec: Optional[float] = None,
        container: Any = None,
        budget_hook: Optional[BudgetHook] = None,
        recorder: Any = None,
    ) -> TaskRunResult:
        claude_driver = ClaudeCliDriver()
        budget = timeout_sec or getattr(task, "agent_timeout_sec", None) or 3600.0
        return self.run_task(
            task=task,
            workspace_path=workspace_path,
            driver=driver,
            budget_sec=budget,
            claude_driver=claude_driver,
            budget_hook=budget_hook,
        )

    def _run_gate_command(self, cmd: list[str], cwd: Path) -> tuple[bool, int, str]:
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False
            )
            return (result.returncode == 0, result.returncode, result.stdout + result.stderr)
        except Exception as e:
            return (False, -1, str(e))

    def run_task(
        self,
        task: TaskSpec,
        workspace_path: Path,
        driver: Optional[AgyCliDriver | Any],
        budget_sec: float,
        claude_driver: Optional[ClaudeCliDriver | Any],
        budget_hook: Optional[BudgetHook] = None,
    ) -> TaskRunResult:
        # Stage 1: Claude writes a reproduction test
        prompt = (
            f"{task.instruction}\n\n"
            "Please write a reproduction test for this issue and run `superstate state handoff --from claude --to agy`."
        )
        
        if claude_driver is None:
            raise ValueError("claude_driver is required")
        if driver is None:
            raise ValueError("driver is required")

        claude_telemetry: DriverTelemetry = claude_driver.run(
            task=task,
            workspace_path=workspace_path,
            prompt_override=prompt,
            timeout_sec=budget_sec,
        )

        if not claude_telemetry.success:
            return TaskRunResult(
                task_id=task.id,
                harness_name=self.name,
                success=False,
                duration_seconds=claude_telemetry.duration_seconds,
                input_tokens=claude_telemetry.input_tokens,
                output_tokens=claude_telemetry.output_tokens,
                cost_usd=claude_telemetry.cost_usd,
                error_message="Stage 1 failed: Claude returned failure or error"
            )

        # Pre-check handoff
        state_dir = workspace_path / ".agent-state"
        handoff_file = state_dir / "handoff.md"
        
        if not handoff_file.exists():
            return TaskRunResult(
                task_id=task.id,
                harness_name=self.name,
                success=False,
                duration_seconds=claude_telemetry.duration_seconds,
                input_tokens=claude_telemetry.input_tokens,
                output_tokens=claude_telemetry.output_tokens,
                cost_usd=claude_telemetry.cost_usd,
                error_message="Stage 1 failed: No handoff.md found"
            )

        if budget_hook is not None:
            budget_sec = max(budget_sec, budget_hook())

        # Stage 2: Agy implements the fix
        agy_telemetry: DriverTelemetry = driver.run(
            task=task,
            workspace_path=workspace_path,
            prompt_override="Resume from handoff.md",
            timeout_sec=max(0.1, budget_sec - claude_telemetry.duration_seconds),
        )

        total_input_tokens = claude_telemetry.input_tokens + agy_telemetry.input_tokens
        total_output_tokens = claude_telemetry.output_tokens + agy_telemetry.output_tokens
        total_cost_usd = claude_telemetry.cost_usd + agy_telemetry.cost_usd
        total_duration = claude_telemetry.duration_seconds + agy_telemetry.duration_seconds

        success, _, _ = self._run_gate_command(["pytest"], workspace_path)

        return TaskRunResult(
            task_id=task.id,
            harness_name=self.name,
            success=success,
            duration_seconds=total_duration,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            cost_usd=total_cost_usd,
        )
