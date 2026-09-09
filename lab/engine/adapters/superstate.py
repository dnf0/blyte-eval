"""Arm C: Superstate (Deterministic State Engine) Adapter.

Executes milestone DAGs with O(1) turnkey context footprints and strict negative constraints.
Directly integrates with the superstate deterministic binary / state engine CLI, enforcing
state transitions, turnkey milestone prompts, and verification gates.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import re
import shutil
import subprocess
from typing import Optional

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.base import AgentAdapter, AgentDriver, TaskRunResult

logger = logging.getLogger("superstate_eval.adapters.superstate")

SUPERSTATE_STEERING_DIRECTIVE = """
## TARGETED EXECUTION CONTRACT (STRICT ENFORCEMENT)
1. **SCOPE BOUNDARY:** Modify ONLY files directly related to this task. Do not touch unrelated files.
2. **TARGETED VERIFICATION ONLY:** Run only the targeted test command. Do not execute full global test suites.
3. **ZERO GLOBAL EXPLORATION:** Do not run recursive grep/find across the whole codebase or dump whole directories.
4. **ZERO-READ AST EXECUTION:** Use targeted symbol lookup or line-bounded reads. Never cat entire files into context.
5. **ATOMIC COMMITS:** Make atomic git commits with conventional commit messages once tests pass.
"""


def find_superstate_binary() -> Optional[Path]:
    """Locate the superstate binary on PATH or standard local paths."""
    which_bin = shutil.which("superstate")
    if which_bin:
        return Path(which_bin)

    candidate_paths = [
        Path.home() / ".local/bin/superstate",
        Path.home() / "repos/superstate/target/release/superstate",
        Path.home() / "repos/superstate/target/debug/superstate",
    ]
    for p in candidate_paths:
        if p.is_file():
            return p
    return None


def _extract_plan_milestones(plan_content: str) -> list[str]:
    """Extract individual milestone headers from a plan markdown document."""
    milestones: list[str] = []
    for line in plan_content.splitlines():
        trimmed = line.strip()
        if re.match(r"^###?\s+Task\s+\d+", trimmed, re.IGNORECASE):
            clean_title = trimmed.lstrip("#").strip()
            milestones.append(clean_title)

    if not milestones:
        milestones = ["Task 1: Complete Feature Implementation"]
    return milestones


def compose_turnkey_milestone_prompt(
    milestone_title: str, plan_content: str, original_task: str
) -> str:
    """Construct an O(1) bounded subagent turnkey prompt with negative constraints."""
    return f"""# Bounded Implementation Turn: {milestone_title}

{SUPERSTATE_STEERING_DIRECTIVE}

## Active Task
You are executing **{milestone_title}**.

## Overall Goal
{original_task}

## Implementation Plan Context
```markdown
{plan_content}
```

## Instructions
1. Implement the specific changes required for `{milestone_title}`.
2. Run your targeted test command to verify correctness.
3. Once verified, create a commit.
"""


class SuperstateAdapter(AgentAdapter):
    """Adapter executing tasks under the deterministic Superstate engine."""

    def __init__(self, superstate_bin: Optional[Path] = None) -> None:
        self.superstate_bin = superstate_bin or find_superstate_binary()

    @property
    def name(self) -> str:
        return "superstate"

    def setup_workspace(self, workspace_path: Path) -> None:
        """Sanitize workspace and ensure zero superpowers skills exist."""
        skills_dir = workspace_path / ".agents" / "skills"
        if skills_dir.is_dir():
            shutil.rmtree(skills_dir)

    def _init_state(self, workspace_path: Path, plan_path: Path) -> bool:
        """Initialize .agent-state/state.json using superstate binary or fallback."""
        if self.superstate_bin:
            try:
                res = subprocess.run(
                    [str(self.superstate_bin), "state", "init", "--plan", str(plan_path)],
                    cwd=str(workspace_path),
                    capture_output=True,
                    text=True,
                    timeout=30.0,
                )
                if res.returncode == 0:
                    logger.info("Initialized superstate via binary at %s", self.superstate_bin)
                    return True
                logger.warning("superstate state init failed: %s", res.stderr)
            except Exception as e:
                logger.warning("Failed to invoke superstate binary: %s", e)

        # Fallback python initialization of state.json
        state_dir = workspace_path / ".agent-state"
        state_dir.mkdir(parents=True, exist_ok=True)
        milestones = _extract_plan_milestones(plan_path.read_text(encoding="utf-8"))
        state_data = {
            "status": "in_progress",
            "step": 1,
            "active_task": milestones[0] if milestones else None,
            "pending_tasks": milestones[1:] if len(milestones) > 1 else [],
            "completed_tasks": [],
            "modified_files": [],
            "errors": [],
            "plan_path": str(plan_path),
        }
        (state_dir / "state.json").write_text(json.dumps(state_data, indent=2), encoding="utf-8")
        return True

    def _advance_state(
        self, workspace_path: Path, milestone: str, verify_cmd: Optional[str] = None
    ) -> bool:
        """Advance state machine to next milestone with optional verification gate."""
        if self.superstate_bin:
            cmd = [str(self.superstate_bin), "state", "next"]
            if verify_cmd:
                cmd.extend(["--verify-cmd", verify_cmd])
            try:
                res = subprocess.run(
                    cmd,
                    cwd=str(workspace_path),
                    capture_output=True,
                    text=True,
                    timeout=60.0,
                )
                if res.returncode == 0:
                    return True
                logger.warning("superstate state next gate failed: %s", res.stderr)
                return False
            except Exception as e:
                logger.warning("Failed to invoke superstate state next: %s", e)
                return False

        # Fallback state advancement
        state_file = workspace_path / ".agent-state" / "state.json"
        if state_file.is_file():
            try:
                state_data = json.loads(state_file.read_text(encoding="utf-8"))
                completed = state_data.get("completed_tasks", [])
                completed.append(milestone)
                pending = state_data.get("pending_tasks", [])
                next_task = pending.pop(0) if pending else None
                state_data["completed_tasks"] = completed
                state_data["pending_tasks"] = pending
                state_data["active_task"] = next_task
                state_data["step"] = state_data.get("step", 1) + 1
                if not next_task:
                    state_data["status"] = "completed"
                state_file.write_text(json.dumps(state_data, indent=2), encoding="utf-8")
                return True
            except Exception as e:
                logger.warning("Fallback state advance failed: %s", e)
                return False
        return True

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

            if not telemetry.success:
                return TaskRunResult(
                    task_id=task.id,
                    harness_name=self.name,
                    success=False,
                    duration_seconds=duration,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_usd=cost_usd,
                    error_message=telemetry.error_message or "Planning turn failed",
                    turns=turns,
                )

            if plan_file.is_file():
                plan_text = plan_file.read_text(encoding="utf-8")
            else:
                plan_text = telemetry.raw_response
                plan_file.write_text(plan_text, encoding="utf-8")

        milestones = _extract_plan_milestones(plan_text)
        max_milestones = 10
        milestones = milestones[:max_milestones]

        # Ensure plan_file has valid Task headings for superstate state init
        if not re.search(r"^###?\s+Task\s+\d+", plan_text, re.MULTILINE | re.IGNORECASE):
            formatted_plan = "\n\n".join(f"### {m}\n- Implement {m}" for m in milestones)
            plan_file.write_text(formatted_plan, encoding="utf-8")
            plan_text = formatted_plan

        # Initialize deterministic state
        self._init_state(workspace_path, plan_file)

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

            # Advance state machine via superstate state next
            adv_ok = self._advance_state(workspace_path, milestone)
            if not adv_ok:
                error_msg = f"Failed to advance state for milestone '{milestone}'"
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
