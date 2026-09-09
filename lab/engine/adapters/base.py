"""Base interfaces and data structures for execution adapters and agent drivers."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.approval import resolve_next_turn_prompt

logger = logging.getLogger("superstate_eval.adapters")

# Returns the currently granted budget in seconds, after polling for progress.
BudgetHook = Callable[[], float]


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
    # Arm-specific provenance (e.g. which state engine or skill set actually ran).
    provenance: Dict[str, Any] = field(default_factory=dict)


class AgentDriver(abc.ABC):
    """Abstract driver interface communicating with an underlying agent runtime.

    `container` is the sandbox the evaluation runs in, when one exists. Drivers
    that execute the agent inside the sandbox must use it; drivers that execute
    on the host operate on `workspace_path`, which the runner bind-mounts into
    the container so both views refer to the same files.
    """

    #: Whether this driver can confine the agent's command execution to the
    #: sandbox. False means the agent keeps a host shell and can therefore reach
    #: the Docker daemon and the task directory -- including the held-out tests.
    #: Runs from such a driver are recorded as not isolated rather than being
    #: quietly presented alongside isolated ones.
    provides_isolated_execution: bool = False

    @abc.abstractmethod
    def run(
        self,
        task: TaskSpec,
        workspace_path: Path,
        prompt_override: Optional[str] = None,
        conversation_id: Optional[str] = None,
        timeout_sec: float = 3600.0,
        container: Any = None,
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
        container: Any = None,
        budget_hook: Optional[BudgetHook] = None,
        recorder: Any = None,
    ) -> TaskRunResult:
        """Execute a task in the given workspace using the provided driver."""


class TurnBasedAdapter(AgentAdapter):
    """Base template adapter managing bounded turn execution and mechanical approval."""

    # Loop-breaker, NOT a budget. Per the design spec a run halts when the agent
    # signals completion or exhausts its progress-earned time budget; this only
    # stops a pathological agent from spinning forever. Set high enough that it
    # does not bind on real work, and raise it rather than letting it decide runs.
    max_turns: int = 50

    @abc.abstractmethod
    def prepare_workspace(self, workspace_path: Path) -> None:
        """Configure or sanitize workspace prior to agent invocation."""

    def get_initial_prompt(self, task: TaskSpec) -> str:
        """Provide initial instruction prompt for the task."""
        return task.instruction

    def get_provenance(self) -> Dict[str, Any]:
        """Report arm-specific facts about how this run was actually configured."""
        return {}

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

        completed_cleanly = False
        for _ in range(self.max_turns):
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
                container=container,
            )

            if recorder is not None:
                recorder.record_turn(
                    phase="implementation", prompt=current_prompt, telemetry=telemetry
                )

            duration += telemetry.duration_seconds
            input_tokens += telemetry.input_tokens
            output_tokens += telemetry.output_tokens
            cost_usd += telemetry.cost_usd
            turns += 1
            conversation_id = telemetry.conversation_id or conversation_id
            last_response = telemetry.raw_response

            # Poll for verifiable progress; the budget may grow mid-run as a result.
            if budget_hook is not None:
                budget = max(budget, budget_hook())

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
                error_msg = f"Exhausted maximum turns ({self.max_turns}) without completion"

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
            provenance=self.get_provenance(),
        )
