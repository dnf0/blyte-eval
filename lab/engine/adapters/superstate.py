"""Arm C: Superstate (Deterministic State Engine) Adapter.

Executes milestone DAGs with O(1) turnkey context footprints and strict negative constraints.
Directly integrates with the superstate deterministic binary / state engine CLI, enforcing
state transitions, turnkey milestone prompts, and verification gates.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Dict, Optional

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.base import AgentAdapter, AgentDriver, BudgetHook, TaskRunResult
from lab.engine.approval import resolve_next_turn_prompt

logger = logging.getLogger("superstate_eval.adapters.superstate")

# Engine provenance values recorded in TaskRunResult.provenance.
ENGINE_BINARY = "superstate_binary"
ENGINE_PYTHON_FALLBACK = "python_fallback"

SUPERSTATE_STEERING_DIRECTIVE = """
## TARGETED EXECUTION CONTRACT (STRICT ENFORCEMENT)
1. **SCOPE BOUNDARY:** Modify ONLY files directly related to this task. Do not touch unrelated files.
2. **TARGETED VERIFICATION ONLY:** Run only the targeted test command. Do not execute full global test suites.
3. **ZERO GLOBAL EXPLORATION:** Do not run recursive grep/find across the whole codebase or dump whole directories.
4. **ZERO-READ AST EXECUTION:** Use targeted symbol lookup or line-bounded reads. Never cat entire files into context.
5. **ATOMIC COMMITS:** Make atomic git commits with conventional commit messages once tests pass.
"""

TASK_HEADING_RE = re.compile(r"^###?\s+Task\s+\d+", re.IGNORECASE)
VERIFY_LINE_RE = re.compile(
    r"^[-*\s]*\**\s*(?:verification\s+command|verify\s+command|verify)\**\s*:\s*(.+)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Milestone:
    """A single plan milestone and its targeted verification gate."""

    title: str
    verify_cmd: Optional[str] = None


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


def _extract_plan_milestones(plan_content: str) -> list[Milestone]:
    """Extract milestone headers and their targeted verification commands from a plan."""
    milestones: list[Milestone] = []
    current_title: Optional[str] = None
    current_verify: Optional[str] = None

    def flush() -> None:
        nonlocal current_title, current_verify
        if current_title is not None:
            milestones.append(Milestone(title=current_title, verify_cmd=current_verify))
        current_title = None
        current_verify = None

    for line in plan_content.splitlines():
        trimmed = line.strip()
        if TASK_HEADING_RE.match(trimmed):
            flush()
            current_title = trimmed.lstrip("#").strip()
            continue
        if current_title is not None and current_verify is None:
            match = VERIFY_LINE_RE.match(trimmed)
            if match:
                current_verify = match.group(1).strip().strip("`")
    flush()

    if not milestones:
        milestones = [Milestone(title="Task 1: Complete Feature Implementation")]
    return milestones


def compose_turnkey_milestone_prompt(
    milestone: Milestone, plan_content: str, original_task: str
) -> str:
    """Construct an O(1) bounded subagent turnkey prompt with negative constraints."""
    verify_line = (
        f"Run `{milestone.verify_cmd}` to verify this milestone."
        if milestone.verify_cmd
        else "Run your targeted test command to verify correctness."
    )
    return f"""# Bounded Implementation Turn: {milestone.title}

{SUPERSTATE_STEERING_DIRECTIVE}

## Active Task
You are executing **{milestone.title}**.

## Overall Goal
{original_task}

## Implementation Plan Context
```markdown
{plan_content}
```

## Instructions
1. Implement the specific changes required for `{milestone.title}`.
2. {verify_line}
3. Once verified, create a commit.
"""


class SuperstateAdapter(AgentAdapter):
    """Adapter executing tasks under the deterministic Superstate engine."""

    max_milestones: int = 10
    # Bounded continuation turns per milestone, mirroring the mechanical approval
    # allowance the Vanilla and Superpowers arms receive.
    max_turns_per_milestone: int = 3

    def __init__(self, superstate_bin: Optional[Path] = None) -> None:
        self.superstate_bin = superstate_bin or find_superstate_binary()
        self.engine_used: Optional[str] = None
        if self.superstate_bin is None:
            logger.warning(
                "SuperstateAdapter: superstate binary not found. Arm C will fall back to the "
                "in-process Python state machine, which is NOT the system under test."
            )

    @property
    def name(self) -> str:
        return "superstate"

    def get_provenance(self) -> Dict[str, Any]:
        """Report which state engine actually drove this run."""
        return {
            "state_engine": self.engine_used,
            "superstate_bin": str(self.superstate_bin) if self.superstate_bin else None,
        }

    def _record_engine(self, engine: str) -> None:
        """Record the engine used, downgrading to the fallback if it is ever hit."""
        if engine == ENGINE_PYTHON_FALLBACK or self.engine_used is None:
            self.engine_used = engine

    def setup_workspace(self, workspace_path: Path) -> None:
        """Sanitize workspace so Arm C sees the same blank slate as the control arm."""
        skills_dir = workspace_path / ".agents" / "skills"
        if skills_dir.is_dir():
            try:
                shutil.rmtree(skills_dir)
            except OSError as err:
                logger.warning("Failed to remove skills dir %s: %s", skills_dir, err)

        # Strip pre-existing guidance files so Arm C is not advantaged over Arm A,
        # which removes the same set.
        for filename in ("AGENTS.md", "GEMINI.md", "CLAUDE.md", ".cursorrules", ".windsurfrules"):
            target = workspace_path / filename
            if target.is_file():
                try:
                    target.unlink()
                except OSError as err:
                    logger.warning("Failed to remove rule file %s: %s", target, err)

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
                    self._record_engine(ENGINE_BINARY)
                    return True
                logger.warning("superstate state init failed: %s", res.stderr)
            except Exception as e:
                logger.warning("Failed to invoke superstate binary: %s", e)

        # Fallback python initialization of state.json
        logger.warning(
            "Arm C falling back to the in-process Python state machine for init; "
            "results do not reflect the superstate binary."
        )
        self._record_engine(ENGINE_PYTHON_FALLBACK)
        state_dir = workspace_path / ".agent-state"
        state_dir.mkdir(parents=True, exist_ok=True)
        milestones = _extract_plan_milestones(plan_path.read_text(encoding="utf-8"))
        titles = [m.title for m in milestones]
        state_data = {
            "status": "in_progress",
            "step": 1,
            "active_task": titles[0] if titles else None,
            "pending_tasks": titles[1:],
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
        """Advance state machine to next milestone through the verification gate."""
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
                    self._record_engine(ENGINE_BINARY)
                    return True
                logger.warning("superstate state next gate failed: %s", res.stderr)
                return False
            except Exception as e:
                logger.warning("Failed to invoke superstate state next: %s", e)
                return False

        # Fallback state advancement
        self._record_engine(ENGINE_PYTHON_FALLBACK)
        state_file = workspace_path / ".agent-state" / "state.json"
        if not state_file.is_file():
            logger.warning("Cannot advance state: %s does not exist", state_file)
            return False
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

    def execute(
        self,
        workspace_path: Path,
        task: TaskSpec,
        driver: AgentDriver,
        timeout_sec: Optional[float] = None,
        container: Any = None,
        budget_hook: Optional[BudgetHook] = None,
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

        def result(success: bool, error: Optional[str]) -> TaskRunResult:
            return TaskRunResult(
                task_id=task.id,
                harness_name=self.name,
                success=success,
                duration_seconds=duration,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                error_message=error,
                turns=turns,
                provenance=self.get_provenance(),
            )

        plan_file = workspace_path / "plan.md"
        plan_text = plan_file.read_text(encoding="utf-8") if plan_file.is_file() else ""

        if not plan_text:
            # Phase 1: Planning turn if no plan exists
            planning_prompt = (
                f"{task.instruction}\n\n"
                "Decompose this task into cohesive milestones. Write `plan.md` using "
                "`### Task N: <Title>` headings, and give every task a "
                "`- Verification Command: <targeted test command>` line."
            )
            telemetry = driver.run(
                task=task,
                workspace_path=workspace_path,
                prompt_override=planning_prompt,
                timeout_sec=min(budget - duration, 600.0),
                container=container,
            )
            duration += telemetry.duration_seconds
            input_tokens += telemetry.input_tokens
            output_tokens += telemetry.output_tokens
            cost_usd += telemetry.cost_usd
            turns += 1

            if budget_hook is not None:
                budget = max(budget, budget_hook())

            if not telemetry.success:
                return result(False, telemetry.error_message or "Planning turn failed")

            if plan_file.is_file():
                plan_text = plan_file.read_text(encoding="utf-8")
            else:
                plan_text = telemetry.raw_response
                plan_file.write_text(plan_text, encoding="utf-8")

        milestones = _extract_plan_milestones(plan_text)[: self.max_milestones]

        # Ensure plan_file has valid Task headings for superstate state init
        if not any(TASK_HEADING_RE.match(line.strip()) for line in plan_text.splitlines()):
            formatted_plan = "\n\n".join(f"### {m.title}\n- Implement {m.title}" for m in milestones)
            plan_file.write_text(formatted_plan, encoding="utf-8")
            plan_text = formatted_plan

        # Initialize deterministic state
        self._init_state(workspace_path, plan_file)

        # Phase 2: Discrete milestone execution
        for milestone in milestones:
            if duration >= budget:
                error_msg = f"Timed out after {duration:.1f}s (budget: {budget:.1f}s)"
                break

            current_prompt = compose_turnkey_milestone_prompt(milestone, plan_text, task.instruction)
            conversation_id: Optional[str] = None
            milestone_failed: Optional[str] = None

            for _ in range(self.max_turns_per_milestone):
                turn_timeout = budget - duration
                if turn_timeout <= 0:
                    milestone_failed = f"Timed out after {duration:.1f}s (budget: {budget:.1f}s)"
                    break

                telemetry = driver.run(
                    task=task,
                    workspace_path=workspace_path,
                    prompt_override=current_prompt,
                    conversation_id=conversation_id,
                    timeout_sec=turn_timeout,
                    container=container,
                )

                duration += telemetry.duration_seconds
                input_tokens += telemetry.input_tokens
                output_tokens += telemetry.output_tokens
                cost_usd += telemetry.cost_usd
                turns += 1
                conversation_id = telemetry.conversation_id or conversation_id

                if budget_hook is not None:
                    budget = max(budget, budget_hook())

                if not telemetry.success:
                    milestone_failed = (
                        telemetry.error_message or f"Milestone '{milestone.title}' failed"
                    )
                    break

                # Mechanical approval, matching the Vanilla and Superpowers arms.
                next_prompt = resolve_next_turn_prompt(telemetry.raw_response)
                if next_prompt is None:
                    break
                current_prompt = next_prompt

            if milestone_failed is not None:
                error_msg = milestone_failed
                break

            # Advance the state machine through the milestone's verification gate.
            if not self._advance_state(workspace_path, milestone.title, milestone.verify_cmd):
                error_msg = f"Verification gate failed for milestone '{milestone.title}'"
                break

        return result(error_msg is None, error_msg)
