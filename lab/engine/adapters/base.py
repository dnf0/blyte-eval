"""Base interfaces and data structures for execution adapters and agent drivers."""

from __future__ import annotations

import abc
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Optional

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.approval import resolve_next_turn_prompt

logger = logging.getLogger("superstate_eval.adapters")


@dataclass
class DriverTelemetry:
    """Outcome and telemetry metrics from a single driver invocation turn."""

    success: bool
    raw_response: str
    duration_seconds: float
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    conversation_id: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class TaskRunResult:
    """Outcome and telemetry metrics for a complete task execution run."""

    task_id: str
    harness_name: str
    success: bool
    duration_seconds: float
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    error_message: Optional[str] = None
    turns: int = 0
    reward: Optional[float] = None


class AgentDriver(abc.ABC):
    """Abstract driver interface communicating with an underlying agent runtime."""

    @abc.abstractmethod
    def run(
        self,
        task: TaskSpec,
        workspace_path: Path,
        prompt_override: Optional[str] = None,
        conversation_id: Optional[str] = None,
        timeout_sec: float = 3600.0,
    ) -> DriverTelemetry:
        """Run an agent session or turn within the target workspace."""


class AgentAdapter(abc.ABC):
    """Abstract evaluation adapter configuring workspace guidance and managing turns."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Name of the evaluation arm."""

    @abc.abstractmethod
    def execute(
        self,
        workspace_path: Path,
        task: TaskSpec,
        driver: AgentDriver,
        timeout_sec: Optional[float] = None,
    ) -> TaskRunResult:
        """Execute a task in the given workspace using the provided driver."""


class TurnBasedAdapter(AgentAdapter):
    """Base template adapter managing bounded turn execution and mechanical approval."""

    @abc.abstractmethod
    def prepare_workspace(self, workspace_path: Path) -> None:
        """Configure or sanitize workspace prior to agent invocation."""

    def get_initial_prompt(self, task: TaskSpec) -> str:
        """Provide initial instruction prompt for the task."""
        return task.instruction

    def execute(
        self,
        workspace_path: Path,
        task: TaskSpec,
        driver: AgentDriver,
        timeout_sec: Optional[float] = None,
    ) -> TaskRunResult:
        """Execute task across sequential turns with bounded caps and autonomous approval."""
        self.prepare_workspace(workspace_path)

        budget = timeout_sec or task.agent_timeout_sec or 3600.0
        duration = 0.0
        input_tokens = 0
        output_tokens = 0
        cost_usd = 0.0
        turns = 0
        conversation_id: Optional[str] = None
        current_prompt: Optional[str] = self.get_initial_prompt(task)
        error_msg: Optional[str] = None
        last_response = ""

        max_turns = 10
        completed_cleanly = False
        for _ in range(max_turns):
            if duration >= budget:
                error_msg = f"Timed out after {duration:.1f}s (budget: {budget:.1f}s)"
                break

            turn_timeout = budget - duration
            telemetry = driver.run(
                task=task,
                workspace_path=workspace_path,
                prompt_override=current_prompt,
                conversation_id=conversation_id,
                timeout_sec=turn_timeout,
            )

            duration += telemetry.duration_seconds
            input_tokens += telemetry.input_tokens
            output_tokens += telemetry.output_tokens
            cost_usd += telemetry.cost_usd
            turns += 1
            conversation_id = telemetry.conversation_id or conversation_id
            last_response = telemetry.raw_response

            if not telemetry.success:
                error_msg = telemetry.error_message or "Agent turn failed"
                break

            # Check if agent requires approval or is asking clarifying questions
            next_prompt = resolve_next_turn_prompt(last_response)
            if next_prompt is None:
                completed_cleanly = True
                break

            current_prompt = next_prompt
        else:
            # Exhausted all turns without agent finishing
            if error_msg is None and not completed_cleanly:
                error_msg = f"Exhausted maximum turns ({max_turns}) without completion"

        success = error_msg is None and completed_cleanly
        return TaskRunResult(
            task_id=task.id,
            harness_name=self.name,
            success=success,
            duration_seconds=duration,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            error_message=error_msg,
            turns=turns,
        )
