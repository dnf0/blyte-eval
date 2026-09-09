"""Superpowers execution adapter: installs markdown rules and vendored skills."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Optional

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.base import AgentAdapter, AgentDriver, TaskRunResult
from lab.engine.approval import resolve_next_turn_prompt

logger = logging.getLogger("superstate_eval.adapters.superpowers")

SUPERPOWERS_AGENTS_MD: str = """# Engineering Agent Guidance (Superpowers Monolith)

Provider target: Universal

## Superpowers Integration
This repository vendors the superpowers skills into `.agents/skills/`.
Follow the standard development lifecycle (brainstorming, writing-plans, test-driven-development).

## Base Rules
- Write unit tests first before writing production code.
- Run targeted tests to verify your implementation.
- Commit changes with clear, descriptive commit messages.
"""


class SuperpowersAdapter(AgentAdapter):
    """Superpowers evaluation arm: installs AGENTS.md and vendored skills."""

    @property
    def name(self) -> str:
        return "superpowers"

    def setup_workspace(self, workspace_path: Path) -> None:
        """Install AGENTS.md and vendored .agents/skills into workspace."""
        (workspace_path / "AGENTS.md").write_text(SUPERPOWERS_AGENTS_MD, encoding="utf-8")

        # Copy vendored skills if available locally from home or repo
        source_skills = Path.home() / ".config" / "agent-rules-home" / ".agents" / "skills"
        if not source_skills.is_dir():
            # Try repo vendor path
            source_skills = Path.home() / "repos" / "agent-rules" / ".agents" / "skills"

        target_skills = workspace_path / ".agents" / "skills"
        if source_skills.is_dir() and not target_skills.exists():
            shutil.copytree(source_skills, target_skills, dirs_exist_ok=True)
        else:
            target_skills.mkdir(parents=True, exist_ok=True)

    def execute(
        self,
        workspace_path: Path,
        task: TaskSpec,
        driver: AgentDriver,
        timeout_sec: Optional[float] = None,
    ) -> TaskRunResult:
        """Execute task with Superpowers guidance and mechanical human continuation."""
        self.setup_workspace(workspace_path)

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

            # Handle Superpowers approval gates autonomously
            next_prompt = resolve_next_turn_prompt(last_response)
            if next_prompt is None:
                break

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
