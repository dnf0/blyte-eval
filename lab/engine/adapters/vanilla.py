"""Vanilla execution adapter: unguided baseline with zero rules and zero skills."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Optional

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.base import AgentAdapter, AgentDriver, TaskRunResult
from lab.engine.approval import resolve_next_turn_prompt

logger = logging.getLogger("superstate_eval.adapters.vanilla")


class VanillaAdapter(AgentAdapter):
    """Unguided evaluation arm. Completely strips guidance and skills."""

    @property
    def name(self) -> str:
        return "vanilla"

    def clean_workspace(self, workspace_path: Path) -> None:
        """Strip all rules, instructions, and skills from workspace."""
        for pattern in [
            "AGENTS.md",
            "GEMINI.md",
            "CLAUDE.md",
            ".cursorrules",
            ".cursor/rules",
            "PROMPT.md",
        ]:
            target = workspace_path / pattern
            if target.is_file():
                target.unlink()

        skills_dir = workspace_path / ".agents" / "skills"
        if skills_dir.is_dir():
            shutil.rmtree(skills_dir, ignore_errors=True)

    def execute(
        self,
        workspace_path: Path,
        task: TaskSpec,
        driver: AgentDriver,
        timeout_sec: Optional[float] = None,
    ) -> TaskRunResult:
        """Execute task in an unguided environment with autonomous continuation."""
        self.clean_workspace(workspace_path)

        budget = timeout_sec or task.agent_timeout_sec or 3600.0
        duration = 0.0
        input_tokens = 0
        output_tokens = 0
        cost_usd = 0.0
        turns = 0
        conversation_id: Optional[str] = None
        current_prompt: Optional[str] = task.instruction
        error_msg: Optional[str] = None
        last_response = ""

        max_turns = 10
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
                # Finished autonomously
                break

            # Dispatched mechanical approval prompt for next turn
            current_prompt = next_prompt

        success = error_msg is None
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
