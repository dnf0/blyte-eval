"""Superstate execution adapter: discrete milestone execution with zero superpowers skills."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Optional

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.base import AgentAdapter, AgentDriver, TaskRunResult

logger = logging.getLogger("superstate_eval.adapters.superstate")


def _extract_plan_milestones(plan_text: str) -> list[str]:
    """Extract list of milestone task titles from markdown plan."""
    milestones: list[str] = []
    for line in plan_text.splitlines():
        trimmed = line.strip()
        if trimmed.startswith("### Task ") or trimmed.startswith("## Task "):
            title = trimmed.lstrip("#").strip()
            milestones.append(title)
    return milestones if milestones else ["Task 1: Complete Feature Implementation"]


def compose_turnkey_milestone_prompt(task_title: str, plan_text: str, instruction: str) -> str:
    """Generate self-contained, bounded turnkey prompt enforcing zero global exploration."""
    return (
        f"You are an Implementer working on **{task_title}**.\n\n"
        f"## Requirement Context\n{instruction}\n\n"
        f"## Plan Overview\n{plan_text}\n\n"
        "## 🎯 TARGETED EXECUTION CONTRACT\n"
        f"- **Active Task:** {task_title}\n"
        "- **Targeted Verification Command:** Run targeted unit tests to verify your implementation.\n\n"
        "## ⛔ NEGATIVE CONSTRAINTS (MANDATORY)\n"
        "1. **SCOPE BOUNDARY:** Edit ONLY files necessary for this milestone.\n"
        "2. **ZERO GLOBAL EXPLORATION:** Do NOT run repo-wide grep, find_by_name, or browse unrelated code.\n"
        "3. **TARGETED VERIFICATION ONLY:** Run only the targeted unit tests for this milestone.\n"
        "4. **DISCIPLINED TDD ENVELOPE:** Test -> minimal code -> pass -> atomic commit.\n"
        "5. **DO NOT READ SKILL OR RULES FILES:** All rules and boundaries are already embedded in this prompt.\n"
        "6. **STOP IMMEDIATELY UPON PASSING:** When tests pass, stop immediately and summarize.\n"
    )


class SuperstateAdapter(AgentAdapter):
    """Superstate evaluation arm: deterministic milestone execution with zero superpowers skills."""

    @property
    def name(self) -> str:
        return "superstate"

    def setup_workspace(self, workspace_path: Path) -> None:
        """Ensure pristine state engine workspace without any superpowers skills."""
        skills_dir = workspace_path / ".agents" / "skills"
        if skills_dir.is_dir():
            shutil.rmtree(skills_dir, ignore_errors=True)

        for pattern in ["AGENTS.md", "GEMINI.md", "CLAUDE.md"]:
            target = workspace_path / pattern
            if target.is_file():
                target.unlink()

    def execute(
        self,
        workspace_path: Path,
        task: TaskSpec,
        driver: AgentDriver,
        timeout_sec: Optional[float] = None,
    ) -> TaskRunResult:
        """Execute task across discrete milestones with O(1) bounded turns."""
        self.setup_workspace(workspace_path)

        budget = timeout_sec or task.agent_timeout_sec or 3600.0
        duration = 0.0
        input_tokens = 0
        output_tokens = 0
        cost_usd = 0.0
        turns = 0
        error_msg: Optional[str] = None

        plan_file = workspace_path / "plan.md"
        plan_text = plan_file.read_text(encoding="utf-8") if plan_file.is_file() else ""

        if not plan_text:
            # Phase 1: Planning turn if no plan exists
            planning_prompt = (
                f"{task.instruction}\n\n"
                "Decompose this task into cohesive milestones. Write `plan.md` using `### Task N: <Title>`."
            )
            telemetry = driver.run(
                task=task,
                workspace_path=workspace_path,
                prompt_override=planning_prompt,
                timeout_sec=min(budget - duration, 600.0),
            )
            duration += telemetry.duration_seconds
            input_tokens += telemetry.input_tokens
            output_tokens += telemetry.output_tokens
            cost_usd += telemetry.cost_usd
            turns += 1

            if plan_file.is_file():
                plan_text = plan_file.read_text(encoding="utf-8")
            else:
                plan_text = telemetry.raw_response

        milestones = _extract_plan_milestones(plan_text)

        # Phase 2: Discrete milestone execution
        for milestone in milestones:
            if duration >= budget:
                error_msg = f"Timed out after {duration:.1f}s (budget: {budget:.1f}s)"
                break

            turnkey_prompt = compose_turnkey_milestone_prompt(
                milestone, plan_text, task.instruction
            )
            turn_timeout = budget - duration
            telemetry = driver.run(
                task=task,
                workspace_path=workspace_path,
                prompt_override=turnkey_prompt,
                timeout_sec=turn_timeout,
            )

            duration += telemetry.duration_seconds
            input_tokens += telemetry.input_tokens
            output_tokens += telemetry.output_tokens
            cost_usd += telemetry.cost_usd
            turns += 1

            if not telemetry.success:
                error_msg = telemetry.error_message or f"Milestone '{milestone}' failed"
                break

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
