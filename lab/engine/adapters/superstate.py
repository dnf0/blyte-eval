"""Arm C: Superstate (Deterministic State Engine) Adapter.

Executes milestone DAGs with O(1) turnkey context footprints and strict negative constraints.
Directly integrates with the superstate deterministic binary / state engine CLI, enforcing
state transitions, turnkey milestone prompts, and verification gates.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
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

TASK_HEADING_RE = re.compile(r"^###?\s+Task\s+\d+", re.IGNORECASE)

# Some drivers hand the agent a host-side bridge script (agy's ./run-in-container)
# for reaching the sandbox. A verification command written in that form cannot run
# where the gate runs -- inside the container itself, which has no docker binary --
# so the wrapper is stripped before the gate executes.
BRIDGE_PREFIX_RE = re.compile(r"(?:^|(?<=[;&|(]))\s*\.?/?run-in-container\s+")
VERIFY_LINE_RE = re.compile(
    r"^[-*\s]*\**\s*(?:verification\s+command|verify\s+command|verify)\**\s*:\s*(.+)$",
    re.IGNORECASE,
)


# Emitted when no `### Task N:` heading could be parsed. A run reduced to this has
# not been decomposed or gated, so it is structurally the baseline arm wearing this
# arm's label -- the worst possible outcome for a comparison, because it does not
# fail, it silently reports the baseline's behaviour as the treatment's.
FALLBACK_MILESTONE_TITLE = "Task 1: Complete Feature Implementation"

TARGETED_EXECUTION_CONTRACT = (
    "## TARGETED EXECUTION CONTRACT (STRICT ENFORCEMENT)\n"
    "1. **SCOPE BOUNDARY:** Modify ONLY files directly related to this task. Do not touch unrelated files.\n"
    "2. **TARGETED VERIFICATION ONLY:** Run only the targeted test command. Do not execute full global test suites.\n"
    "3. **ZERO GLOBAL EXPLORATION:** Do not run recursive grep/find across the whole codebase or dump whole directories.\n"
    "4. **ZERO-READ AST EXECUTION:** Use targeted symbol lookup or line-bounded reads. Never cat entire files into context.\n"
    "5. **ATOMIC COMMITS:** Make atomic git commits with conventional commit messages once tests pass.\n"
    "6. **NO EXTERNAL LINTER PROBING:** Do not run external linters or formatters. Focus solely on making tests pass.\n"
    "7. **DO NOT READ SKILL OR RULES FILES:** Do not inspect GEMINI.md, AGENTS.md, or .cursorrules.\n"
    "8. **STOP IMMEDIATELY UPON PASSING:** When the verification command passes, commit your changes and finish your turn."
)


@dataclass(frozen=True)
class Milestone:
    """A single plan milestone and its targeted verification gate."""

    title: str
    verify_cmd: Optional[str] = None


# `superstate` on PATH is a shim into the agent-rules Python package, so a bare
# PATH lookup silently selects the Python engine while the run is labelled Rust.
# The engine is therefore chosen explicitly and always recorded.
ENGINE_PYTHON = "agent-rules-python"
ENGINE_RUST = "superstate-rust"

ENGINE_PATHS: dict[str, tuple[Path, ...]] = {
    ENGINE_PYTHON: (
        Path.home() / ".local/bin/superstate",
        Path.home() / ".local/bin/agent-rules",
    ),
    ENGINE_RUST: (
        Path.home() / "repos/superstate/target/release/superstate",
        Path.home() / "repos/superstate/target/debug/superstate",
    ),
}

DEFAULT_ENGINE = ENGINE_PYTHON


def find_superstate_binary(engine: str = DEFAULT_ENGINE) -> Optional[Path]:
    """Resolve the state-engine binary for a named implementation.

    Resolution is explicit: SUPERSTATE_BIN if set, else the known paths for the
    requested implementation. Never a bare PATH lookup -- two implementations
    share the name `superstate`, and picking the wrong one is undetectable in the
    results.
    """
    env_path = os.environ.get("SUPERSTATE_BIN")
    if env_path and Path(env_path).is_file():
        return Path(env_path)

    for candidate in ENGINE_PATHS.get(engine, ()):
        if candidate.is_file():
            return candidate
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
        milestones = [Milestone(title=FALLBACK_MILESTONE_TITLE)]
    return milestones




class SuperstateAdapter(AgentAdapter):
    """Adapter executing tasks under the deterministic Superstate engine."""

    # Loop-breaker only. A plan longer than this is a hard failure, never a
    # silent truncation: dropping milestones and still reporting success would
    # score an agent as having solved work it never attempted.
    max_milestones: int = 50
    # Bounded continuation turns per milestone, mirroring the mechanical approval
    # allowance the Vanilla and Superpowers arms receive.
    max_turns_per_milestone: int = 3
    #: Fail rather than run undecomposed. A single fallback milestone with no gate
    #: is not a control-plane run, and recording it as one corrupts the comparison.
    require_decomposition: bool = True
    # Share of the run budget planning may consume. This is not a limit on how long
    # planning is allowed to think -- it exists only so a planning turn cannot starve
    # the implementation it is planning. Set to None to let planning draw on the whole
    # budget; a milestone that then finds no time left reports an honest timeout.
    planning_budget_fraction: float | None = 0.5

    def __init__(
        self,
        superstate_bin: Optional[Path] = None,
        engine: str = DEFAULT_ENGINE,
    ) -> None:
        self.engine = engine
        self.superstate_bin = superstate_bin or find_superstate_binary(engine)
        self.engine_used: Optional[str] = None
        self.plan_source: Optional[str] = None
        self.milestones_planned: int = 0
        self.decomposed: bool = False
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
            # Which implementation was requested, and what actually ran. A result
            # is not interpretable without both.
            "engine": self.engine,
            "superstate_bin": str(self.superstate_bin) if self.superstate_bin else None,
            # Whether this run was actually a control-plane run.
            "plan_source": self.plan_source,
            "milestones_planned": self.milestones_planned,
            "decomposed": self.decomposed,
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

    def _run_engine(
        self, workspace_path: Path, args: list[str], timeout: float = 60.0
    ) -> tuple[int, str]:
        """Invoke the state engine, returning (exit_code, stdout)."""
        if not self.superstate_bin:
            return 1, "no state engine binary resolved"
        try:
            res = subprocess.run(
                [str(self.superstate_bin), "state", *args],
                cwd=str(workspace_path),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if res.returncode != 0:
                logger.warning("state %s failed: %s", args[0], res.stderr.strip()[:200])
            return res.returncode, res.stdout
        except Exception as err:
            logger.warning("state %s could not run: %s", args[0], err)
            return 1, str(err)

    def ready_tasks(self, workspace_path: Path) -> list[str]:
        """Unblocked tasks from the plan's dependency DAG (`state ready --json`).

        This replaces linear iteration over headings: the engine decides what is
        eligible, which is the point of having a DAG.
        """
        code, out = self._run_engine(workspace_path, ["ready", "--json"])
        if code != 0:
            return []
        try:
            data = json.loads(out)
            return [str(t) for t in data] if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    def turnkey_prompt(self, workspace_path: Path, task: Optional[str] = None) -> Optional[str]:
        """The engine's own turnkey prompt (`state prompt --with-graph`).

        Generating this prompt is a core function of the control plane -- bounded
        context, active task spec, recorded decisions, graph context. Substituting a
        local template would measure the template, not the engine.
        """
        args = ["prompt", "--with-graph"]
        if task:
            args += ["--task", task]
        code, out = self._run_engine(workspace_path, args)
        return out.strip() if code == 0 and out.strip() else None

    def record_note(self, workspace_path: Path, message: str) -> bool:
        """Append to the epistemic ledger (`state note`).

        This is what lets a later milestone inherit an earlier one's discoveries;
        without it, bounded context simply loses information between turns.
        """
        code, _ = self._run_engine(workspace_path, ["note", message[:2000]])
        return code == 0

    def _init_state(self, workspace_path: Path, plan_path: Path) -> bool:
        """Initialize .agent-state/state.json using superstate binary or fallback."""
        if self.superstate_bin:
            try:
                # Flag divergence between implementations: Python writes with
                # --out, Rust with --state.
                out_flag = "--state" if self.engine == ENGINE_RUST else "--out"
                state_path = workspace_path / ".agent-state" / "state.json"
                state_path.parent.mkdir(parents=True, exist_ok=True)
                res = subprocess.run(
                    [
                        str(self.superstate_bin), "state", "init",
                        "--plan", str(plan_path),
                        out_flag, str(state_path),
                    ],
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

    @staticmethod
    def normalize_gate_command(verify_cmd: str, in_container: bool) -> str:
        """Strip a host-side bridge wrapper when the gate already runs in the sandbox."""
        if not in_container:
            return verify_cmd
        return BRIDGE_PREFIX_RE.sub(lambda m: m.group(0)[: -len(m.group(0).lstrip())] or "", verify_cmd).strip()

    def _run_gate_command(
        self, workspace_path: Path, verify_cmd: str, container: Any = None
    ) -> tuple[bool, Optional[int], str]:
        """Run a milestone's verification command where the task actually lives.

        With a sandbox present the command must run inside it: the host has neither
        the task's toolchain nor its dependencies, and running it on the host would
        breach the isolation the evaluation depends on.
        """
        verify_cmd = self.normalize_gate_command(verify_cmd, in_container=container is not None)
        if container is not None:
            exec_res = container.exec_run(verify_cmd)
            if isinstance(exec_res, tuple):
                exit_code, raw = exec_res[0], exec_res[1]
            else:
                exit_code = getattr(exec_res, "exit_code", 1)
                raw = getattr(exec_res, "output", b"")
            output = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
            return exit_code == 0, exit_code, output
        try:
            res = subprocess.run(
                verify_cmd,
                shell=True,
                cwd=str(workspace_path),
                capture_output=True,
                text=True,
                timeout=300.0,
            )
            return res.returncode == 0, res.returncode, (res.stdout or "") + (res.stderr or "")
        except Exception as e:
            logger.warning("Verification command failed to run: %s", e)
            return False, None, f"gate command could not be executed: {e}"

    def _advance_state(
        self,
        workspace_path: Path,
        milestone: str,
        verify_cmd: Optional[str] = None,
        container: Any = None,
        gate_detail: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Advance state machine to next milestone through the verification gate."""
        # Evaluate the gate where the task lives, then let the state engine record
        # the verdict. This keeps superstate's gate semantics while ensuring the
        # test itself runs inside the sandbox.
        gate_cmd: Optional[str] = None
        if verify_cmd:
            passed, exit_code, output = self._run_gate_command(
                workspace_path, verify_cmd, container
            )
            if gate_detail is not None:
                gate_detail.update(
                    {"gate_ran": True, "gate_passed": passed,
                     "gate_exit_code": exit_code, "gate_output": output}
                )
            if not passed:
                logger.warning(
                    "Verification gate failed for '%s' (cmd: %s)", milestone, verify_cmd
                )
            gate_cmd = "exit 0" if passed else "exit 1"

        if self.superstate_bin:
            # When the gate passes, auto-commit any uncommitted changes so git HEAD
            # advances and --verify-git-clean passes deterministically.
            if gate_cmd != "exit 1" and (workspace_path / ".git").exists():
                try:
                    status = subprocess.run(
                        ["git", "status", "--porcelain"],
                        cwd=str(workspace_path),
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if status.stdout and status.stdout.strip():
                        subprocess.run(
                            ["git", "add", "-A"], cwd=str(workspace_path), capture_output=True, check=False
                        )
                        subprocess.run(
                            [
                                "git",
                                "-c",
                                "user.name=Agent",
                                "-c",
                                "user.email=agent@eval.local",
                                "commit",
                                "--no-gpg-sign",
                                "-m",
                                f"chore: checkpoint completed milestone {milestone}",
                            ],
                            cwd=str(workspace_path),
                            capture_output=True,
                            check=False,
                        )
                except Exception as exc:
                    logger.debug("Failed auto-committing milestone changes: %s", exc)

            cmd = [str(self.superstate_bin), "state", "next", "--verify-git-clean"]
            if self.engine != ENGINE_RUST:
                cmd.extend(["--ignore-untracked-glob", "run-in-container,plan.md,plan.normalized.md"])
            if gate_cmd:
                cmd.extend(["--verify-cmd", gate_cmd])
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
        if gate_cmd == "exit 1":
            return False
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

    @staticmethod
    def _record_milestone(
        recorder: Any,
        index: int,
        milestone: Milestone,
        turns_used: int,
        gate_detail: Dict[str, Any],
        advanced: bool,
    ) -> None:
        """Persist a milestone attempt and its gate verdict, if tracing is enabled."""
        if recorder is None:
            return
        from lab.engine.trace import MilestoneRecord

        recorder.record_milestone(
            MilestoneRecord(
                index=index,
                title=milestone.title,
                verify_cmd=milestone.verify_cmd,
                turns_used=turns_used,
                advanced=advanced,
                **gate_detail,
            )
        )

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
                "<state-evaluation>\n"
                "State: 2. Spec Exists, Needs Plan\n"
                "Required Skill: writing-plans\n"
                "Status: Specification and requirements are complete. Generate plan.md directly.\n"
                "</state-evaluation>\n\n"
                f"{task.instruction}\n\n"
                "## 🔬 PRE-ASSESSMENT & COHESIVE MODULE DECOMPOSITION PROTOCOL\n"
                "Before writing `plan.md`, dynamically evaluate the architectural surface area and requirement invariants:\n"
                "1. **Cohesive Architectural Modules:**\n"
                "   Decompose the feature into cohesive, independently verifiable architectural modules:\n"
                "   - **Module Boundary:** Each milestone implements a complete cohesive capability within 1-2 tightly related files.\n"
                "   - **Targeted Verification:** Each milestone specifies a targeted verification command using the repository's native test runner (e.g. `go test ./parser/...`, `pytest tests/test_foo.py`).\n"
                "   - **Full TDD Envelope:** The worker executes a red-green-refactor cycle: test -> implementation -> verification -> atomic commit.\n\n"
                "## 📝 PLAN FORMAT REQUIREMENTS\n"
                "Write `plan.md` using `write_to_file`. Format each task as:\n"
                "### Task <number>: <Title>\n"
                "- **Depends on:** <Prerequisite Tasks or none>\n"
                "**Files:**\n"
                "- Modify: `<target_file_path>`\n"
                "- Test: `<test_file_path>`\n"
                "- Verification Command: `<plain command running directly in project environment>`\n"
                "**Goal:** <One-sentence description of the capability delivered>\n\n"
                "Write each verification command as a PLAIN command that runs in the "
                "project environment, e.g. `go test ./parser/...`. Do not prefix it with "
                "any wrapper or helper script -- the command is executed directly in the "
                "project environment, where such a wrapper does not exist.\n\n"
                "## ⛔ CRITICAL DIRECTIVE (MANDATORY)\n"
                "- This is a planning-only turn. Do NOT execute shell commands, do NOT run git, and do NOT explore files.\n"
                "- Based on the specification above, synthesize the plan and call `write_to_file` to write `plan.md` immediately in the workspace."
            )
            remaining = budget - duration
            planning_timeout = (
                remaining
                if self.planning_budget_fraction is None
                else min(remaining, budget * self.planning_budget_fraction)
            )
            telemetry = driver.run(
                task=task,
                workspace_path=workspace_path,
                prompt_override=planning_prompt,
                timeout_sec=planning_timeout,
                container=container,
            )
            if recorder is not None:
                recorder.record_turn(
                    phase="planning", prompt=planning_prompt, telemetry=telemetry
                )

            duration += telemetry.duration_seconds
            input_tokens += telemetry.input_tokens
            output_tokens += telemetry.output_tokens
            cost_usd += telemetry.cost_usd
            turns += 1

            if budget_hook is not None:
                budget = max(budget, budget_hook())

            if not telemetry.success:
                # Say plainly when our own budget share ended the run, rather than
                # reporting it as an agent failure.
                detail = telemetry.error_message or "Planning turn failed"
                if self.planning_budget_fraction is not None and duration >= planning_timeout:
                    detail = (
                        f"Planning exceeded its {self.planning_budget_fraction:.0%} share of "
                        f"the {budget:.0f}s budget ({planning_timeout:.0f}s): {detail}"
                    )
                return result(False, detail)

            if plan_file.is_file():
                plan_text = plan_file.read_text(encoding="utf-8")
                self.plan_source = "plan.md"
            else:
                # The agent may have written the plan somewhere we cannot see --
                # a host-side harness resolves paths against its own project root.
                logger.warning(
                    "No plan.md in the workspace after planning; falling back to the "
                    "response text. Check whether the agent wrote it elsewhere."
                )
                plan_text = telemetry.raw_response
                self.plan_source = "response"

        milestones = _extract_plan_milestones(plan_text)
        self.milestones_planned = len(milestones)
        self.decomposed = not (
            len(milestones) == 1 and milestones[0].title == FALLBACK_MILESTONE_TITLE
        )
        if not self.decomposed and self.require_decomposition:
            return result(
                False,
                "Planning produced no parseable milestones (no '### Task N:' heading "
                f"found in {self.plan_source}), so this run would have executed as a "
                "single ungated milestone -- the baseline's behaviour under this arm's "
                "label. Failing instead of recording a mislabelled result.",
            )
        if len(milestones) > self.max_milestones:
            return result(
                False,
                f"Plan declares {len(milestones)} milestones, exceeding the "
                f"max_milestones loop-breaker ({self.max_milestones})",
            )

        # Always persist what the agent actually produced: it is the evidence for
        # why a run decomposed the way it did.
        if self.plan_source == "response":
            plan_file.write_text(plan_text, encoding="utf-8")

        # The state engine needs `### Task N:` headings. Where the agent's text does
        # not have them, the normalised copy goes to its own file rather than
        # overwriting the agent's plan.
        if not any(TASK_HEADING_RE.match(line.strip()) for line in plan_text.splitlines()):
            plan_file = workspace_path / "plan.normalized.md"
            plan_file.write_text(
                "\n\n".join(f"### {m.title}\n- Implement {m.title}" for m in milestones),
                encoding="utf-8",
            )

        # Initialize deterministic state
        self._init_state(workspace_path, plan_file)

        # Phase 2: engine-driven execution. The engine chooses what is eligible
        # (`state ready`), writes the turnkey prompt (`state prompt`), and decides
        # whether work may advance (`state next`). The harness only carries turns
        # between those calls -- substituting our own logic for any of them would
        # measure the substitute rather than the control plane.
        verify_by_title = {m.title: m.verify_cmd for m in milestones}
        executed: set[str] = set()

        for _ in range(self.max_milestones):
            if duration >= budget:
                error_msg = f"Timed out after {duration:.1f}s (budget: {budget:.1f}s)"
                break

            ready = [t for t in self.ready_tasks(workspace_path) if t not in executed]
            if not ready:
                break
            active = ready[0]
            executed.add(active)
            milestone_index = len(executed)

            current_prompt = self.turnkey_prompt(workspace_path, active)
            if current_prompt is None:
                error_msg = f"State engine produced no prompt for '{active}'"
                break
            current_prompt = f"{current_prompt}\n\n{TARGETED_EXECUTION_CONTRACT}"

            conversation_id: Optional[str] = None
            milestone_failed: Optional[str] = None
            milestone_turns = 0
            last_response = ""
            advanced = False
            milestone = Milestone(title=active, verify_cmd=verify_by_title.get(active))
            gate_detail: Dict[str, Any] = {
                "gate_ran": False,
                "gate_passed": None,
                "gate_exit_code": None,
                "gate_output": None,
            }

            for _turn in range(self.max_turns_per_milestone):
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

                if recorder is not None:
                    recorder.record_turn(
                        phase="milestone",
                        prompt=current_prompt,
                        telemetry=telemetry,
                        milestone=active,
                    )

                duration += telemetry.duration_seconds
                input_tokens += telemetry.input_tokens
                output_tokens += telemetry.output_tokens
                cost_usd += telemetry.cost_usd
                turns += 1
                milestone_turns += 1
                conversation_id = telemetry.conversation_id or conversation_id
                last_response = telemetry.raw_response or ""

                if budget_hook is not None:
                    budget = max(budget, budget_hook())

                # If the agent is asking for approval / input, provide mechanical approval
                next_prompt = resolve_next_turn_prompt(last_response)
                if next_prompt is not None:
                    current_prompt = next_prompt
                    continue

                # The agent concluded its work for this milestone.
                # Evaluate targeted verification gate & rescue: if the targeted verification passes on disk,
                # the milestone succeeded and state advances regardless of driver status quirks.
                advanced = self._advance_state(
                    workspace_path, active, milestone.verify_cmd, container, gate_detail
                )
                if advanced:
                    milestone_failed = None
                    break

                if not telemetry.success:
                    milestone_failed = telemetry.error_message or f"Milestone '{active}' failed"
                    break

                # Agent concluded without asking for user approval, but verification gate failed
                milestone_failed = f"Verification gate failed for milestone '{active}'"
                break

            # Carry what this turn learned into the ledger, so later milestones
            # inherit it rather than starting blind.
            if last_response:
                self.record_note(workspace_path, f"[{active}] {last_response[:1500]}")

            self._record_milestone(
                recorder, milestone_index, milestone, milestone_turns, gate_detail, advanced
            )
            if not advanced:
                error_msg = milestone_failed or f"Verification gate failed for milestone '{active}'"
                break

        return result(error_msg is None, error_msg)
