"""Harness-level adapter for Superstate orchestration over stdio JSON-RPC MCP.

Executes milestone DAGs using SuperstateMcpClient over stdio JSON-RPC instead of
subprocess CLI invocations. Provides deterministic state tracking, bounded turnkey
prompts, targeted verification gates, automated checkpoint commits, and worktree cleanup.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import re
import shlex
import subprocess
from typing import Any, Dict, Optional

from lab.benchmarks.gate_fixtures import agent_gate_for
from lab.benchmarks.task_loader import TaskSpec
from lab.engine.condition_b import conversation_id_for
from lab.engine.prompt_contracts import apply_contract
from lab.engine.adapters.base import (
    AgentAdapter,
    AgentDriver,
    BudgetHook,
    TaskRunResult,
    strip_preexisting_guidance,
)
from lab.engine.adapters.superstate import (
    FALLBACK_MILESTONE_TITLE,
    Milestone,
    TARGETED_EXECUTION_CONTRACT,
    TARGETED_EXECUTION_CONTRACT_INPLACE,
    TASK_HEADING_RE,
    _extract_plan_milestones,
)
from lab.engine.approval import resolve_next_turn_prompt
from lab.engine.mcp.client import SuperstateMcpClient

logger = logging.getLogger("superstate_eval.adapters.superstate_mcp")

BRIDGE_PREFIX_RE = re.compile(r"(?:^|(?<=[;&|(]))\s*\.?/?run-in-container\s+")


class SuperstateMcpAdapter(AgentAdapter):
    """Adapter executing tasks under the deterministic Superstate engine via stdio MCP."""

    # Maximum milestones permitted before halting as a loop-breaker
    max_milestones: int = 50
    # Bounded continuation turns per milestone
    max_turns_per_milestone: int = 3
    # Fail rather than run undecomposed
    require_decomposition: bool = True
    # Share of run budget planning may consume
    planning_budget_fraction: float | None = 0.5

    # Harness bookkeeping files excluded from git tracking
    HARNESS_UNTRACKED = (
        ".agent-state/",
        "plan.md",
        "plan.normalized.md",
        "run-in-container",
    )

    def __init__(
        self,
        superstate_bin: Optional[Path | str] = None,
        no_worktree: bool = True,
        worktree: bool = False,
        zero_turn_planning: bool = True,
        name: str = "superstate_mcp",
        max_turns_per_milestone: int = 3,
        max_milestones: int = 50,
        require_decomposition: bool = True,
        planning_budget_fraction: float | None = 0.5,
    ) -> None:
        """Initialize the Superstate MCP adapter configuration."""
        self.superstate_bin = Path(superstate_bin) if superstate_bin is not None else None
        self.no_worktree = no_worktree
        self.worktree = worktree
        self.zero_turn_planning = zero_turn_planning
        self._name = name
        self.max_turns_per_milestone = max_turns_per_milestone
        self.max_milestones = max_milestones
        self.require_decomposition = require_decomposition
        self.planning_budget_fraction = planning_budget_fraction

        self.plan_source: Optional[str] = None
        self.milestones_planned: int = 0
        self.decomposed: bool = False
        self.mcp_tools_discovered: int = 0

    @property
    def name(self) -> str:
        """Name of the evaluation arm."""
        return self._name

    def get_provenance(self) -> Dict[str, Any]:
        """Report state engine, transport, and discovered tools provenance."""
        return {
            "engine": "superstate_rust_mcp",
            "transport": "mcp_stdio",
            "mcp_tools_discovered": self.mcp_tools_discovered,
            "superstate_bin": str(self.superstate_bin) if self.superstate_bin else None,
            "no_worktree": self.no_worktree,
            "worktree": self.worktree,
            "zero_turn_planning": self.zero_turn_planning,
            "plan_source": self.plan_source,
            "milestones_planned": self.milestones_planned,
            "decomposed": self.decomposed,
        }

    def _exclude_harness_artifacts(self, workspace_path: Path) -> None:
        """Keep harness files from dirtying the tree that git verification gates inspect."""
        exclude = workspace_path / ".git" / "info" / "exclude"
        if not exclude.parent.parent.is_dir():
            return
        try:
            exclude.parent.mkdir(parents=True, exist_ok=True)
            existing = exclude.read_text(encoding="utf-8") if exclude.is_file() else ""
            missing = [a for a in self.HARNESS_UNTRACKED if a not in existing]
            if missing:
                with exclude.open("a", encoding="utf-8") as fh:
                    fh.write("\n" + "\n".join(missing) + "\n")
        except OSError as err:
            logger.warning("Could not exclude harness artifacts from git: %s", err)

    def setup_workspace(self, workspace_path: Path) -> None:
        """Sanitize workspace by stripping legacy guidance and excluding harness artifacts."""
        self._exclude_harness_artifacts(workspace_path)
        strip_preexisting_guidance(workspace_path)

    def active_worktree(self, workspace_path: Path) -> Optional[Path]:
        """Resolve active worktree path from state.json if provisioned."""
        if self.no_worktree:
            return None
        state_file = workspace_path / ".agent-state" / "state.json"
        if not state_file.is_file():
            return None
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
            raw = data.get("active_worktree")
            if not raw:
                return None
            path = Path(raw)
            if not path.is_absolute():
                path = workspace_path / path
            return path if path.exists() else None
        except Exception as exc:
            logger.debug("Failed reading active_worktree from %s: %s", state_file, exc)
            return None

    @staticmethod
    def normalize_gate_command(verify_cmd: str, in_container: bool) -> str:
        """Strip a host-side bridge wrapper when the gate already runs in the sandbox."""
        if not in_container:
            return verify_cmd
        return BRIDGE_PREFIX_RE.sub(
            lambda m: m.group(0)[: -len(m.group(0).lstrip())] or "", verify_cmd
        ).strip()

    def _run_gate_command(
        self, workspace_path: Path, verify_cmd: str, container: Any = None
    ) -> tuple[bool, Optional[int], str]:
        """Execute a milestone verification command on the host or inside a container."""
        verify_cmd = self.normalize_gate_command(verify_cmd, in_container=container is not None)
        wt = self.active_worktree(workspace_path)
        target_dir = wt if (wt and wt.is_dir()) else workspace_path

        if container is not None:
            container_workdir = "/app"
            if "/tests/" in verify_cmd or verify_cmd.startswith("bash /tests"):
                try:
                    chk = container.exec_run(["test", "-d", "/tests"])
                    chk_code = chk[0] if isinstance(chk, tuple) else getattr(chk, "exit_code", 0)
                    if chk_code != 0:
                        logger.info(
                            "Held-out test path /tests is sealed during agent phase; skipping gate"
                        )
                        return True, 0, "Held-out test path /tests is sealed during agent phase"
                except Exception as exc:
                    logger.debug("Failed testing for /tests in container: %s", exc)

            shell_cmd = ["/bin/sh", "-c", verify_cmd]
            try:
                exec_res = container.exec_run(shell_cmd, workdir=container_workdir)
            except TypeError:
                fallback_cmd = [
                    "/bin/sh",
                    "-c",
                    f"cd {shlex.quote(str(container_workdir))} && {verify_cmd}",
                ]
                exec_res = container.exec_run(fallback_cmd)
            except Exception as e:
                logger.warning("Container exec_run failed: %s", e)
                return False, None, f"gate command could not be executed in container: {e}"

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
                cwd=str(target_dir),
                capture_output=True,
                text=True,
                timeout=300.0,
            )
            passed = res.returncode == 0
            output = (res.stdout or "") + (res.stderr or "")
            if not passed and wt and wt.is_dir() and str(workspace_path) in verify_cmd:
                alt_cmd = verify_cmd.replace(str(workspace_path), str(wt))
                if alt_cmd != verify_cmd:
                    try:
                        alt_res = subprocess.run(
                            alt_cmd,
                            shell=True,
                            cwd=str(target_dir),
                            capture_output=True,
                            text=True,
                            timeout=300.0,
                        )
                        if alt_res.returncode == 0:
                            logger.info(
                                "Host verification gate passed via worktree path substitution"
                            )
                            return True, 0, (alt_res.stdout or "") + (alt_res.stderr or "")
                    except Exception as exc:
                        logger.debug("Worktree alternate gate check failed: %s", exc)
            return passed, res.returncode, output
        except Exception as e:
            logger.warning("Verification command failed to run: %s", e)
            return False, None, f"gate command could not be executed: {e}"

    def _switch_container_workspace(
        self,
        container: Any,
        workspace_path: Path,
        active_wt: Optional[Path],
    ) -> None:
        """Dynamically repoint /app inside container to the active worktree or /workspace_root."""
        if container is None:
            return
        try:
            target = "/workspace_root"
            if active_wt and active_wt.is_dir() and not self.no_worktree:
                try:
                    rel = active_wt.resolve().relative_to(workspace_path.resolve())
                    target = f"/workspace_root/{rel}"
                except ValueError as err:
                    logger.warning(
                        "Worktree %s not relative to %s: %s; falling back to root",
                        active_wt,
                        workspace_path,
                        err,
                    )
            res = container.exec_run(
                ["sh", "-c", f"ln -sfn {shlex.quote(target)} /app"], workdir="/"
            )
            code = res[0] if isinstance(res, tuple) else getattr(res, "exit_code", 0)
            if code != 0:
                out = res[1] if isinstance(res, tuple) else getattr(res, "output", b"")
                logger.warning("ln -sfn to %s failed with exit code %s: %s", target, code, out)
        except Exception as exc:
            logger.warning("Failed to switch container workspace symlink: %s", exc)

    @staticmethod
    def _distill_finding(response: str) -> str:
        """Extract a clean, concise finding from the turn response to keep prompt bounded."""
        if not response:
            return ""
        summary_match = re.search(
            r"^#+\s*.*summary[^\n]*\n(.*)",
            response,
            re.MULTILINE | re.IGNORECASE | re.DOTALL,
        )
        candidate = summary_match.group(1).strip() if summary_match else response.strip()
        lines = [
            line.strip()
            for line in candidate.splitlines()
            if line.strip()
            and not line.strip().startswith("#")
            and not line.strip().startswith("```")
        ]
        compact = " ".join(lines)
        if len(compact) > 250:
            return compact[:247].rstrip() + "..."
        return compact

    def _auto_commit_if_dirty(self, workspace_path: Path, milestone: str) -> None:
        """Auto-commit any uncommitted changes so git HEAD advances and --verify-git-clean passes."""
        if not (workspace_path / ".git").exists():
            return
        wt = self.active_worktree(workspace_path)
        target_dir = wt if (wt and wt.is_dir()) else workspace_path
        try:
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(target_dir),
                capture_output=True,
                text=True,
                check=False,
            )
            if status.stdout and status.stdout.strip():
                subprocess.run(
                    ["git", "add", "-A"], cwd=str(target_dir), capture_output=True, check=False
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
                    cwd=str(target_dir),
                    capture_output=True,
                    check=False,
                )
        except Exception as exc:
            logger.debug("Failed auto-committing milestone changes: %s", exc)

    def _advance_state(
        self,
        client: SuperstateMcpClient,
        workspace_path: Path,
        milestone: str,
        verify_cmd: Optional[str] = None,
        container: Any = None,
        gate_detail: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Advance the milestone state machine via SuperstateMcpClient."""
        state_file = workspace_path / ".agent-state" / "state.json"
        if state_file.is_file():
            try:
                sdata = json.loads(state_file.read_text(encoding="utf-8"))
                completed_ids_or_titles = {
                    t.get("id") for t in sdata.get("completed_tasks", []) if isinstance(t, dict)
                } | {
                    t.get("title") for t in sdata.get("completed_tasks", []) if isinstance(t, dict)
                } | {
                    t for t in sdata.get("completed_tasks", []) if isinstance(t, str)
                }
                is_milestone_done = (
                    sdata.get("status") == "completed"
                    or milestone in completed_ids_or_titles
                    or (sdata.get("active_task") is None and sdata.get("completed_tasks"))
                )
                if is_milestone_done:
                    logger.info("Milestone '%s' was already advanced to completed", milestone)
                    self._switch_container_workspace(container, workspace_path, None)
                    return True
            except Exception as exc:
                logger.debug("Failed checking agent-completed state: %s", exc)

        gate_cmd: Optional[str] = None
        if verify_cmd:
            passed, exit_code, output = self._run_gate_command(
                workspace_path, verify_cmd, container
            )
            if gate_detail is not None:
                gate_detail.update(
                    {
                        "gate_ran": True,
                        "gate_passed": passed,
                        "gate_exit_code": exit_code,
                        "gate_output": output,
                    }
                )
            if not passed:
                logger.warning(
                    "Verification gate failed for '%s' (cmd: %s)", milestone, verify_cmd
                )
                return False
            gate_cmd = "exit 0"

        # Gate passed or unconfigured: auto-commit uncommitted changes
        self._auto_commit_if_dirty(workspace_path, milestone)

        has_git = (workspace_path / ".git").exists()
        try:
            adv_ok = client.state_next(
                repo=workspace_path,
                verify_git_clean=has_git,
                verify_cmd=gate_cmd,
            )
            if adv_ok:
                self._switch_container_workspace(container, workspace_path, None)
                return True

            if state_file.is_file():
                try:
                    sdata = json.loads(state_file.read_text(encoding="utf-8"))
                    if sdata.get("status") == "completed" or (
                        sdata.get("active_task") is None and sdata.get("completed_tasks")
                    ):
                        logger.info("State was already completed; advancing successfully")
                        self._switch_container_workspace(container, workspace_path, None)
                        return True
                except Exception:
                    pass

            logger.warning("MCP client state_next failed for '%s'", milestone)
            return False
        except Exception as err:
            logger.warning("Exception during client.state_next: %s", err)
            if gate_detail is not None:
                gate_detail["engine_error"] = str(err)
            return False

    @staticmethod
    def _get_git_diff_stat(workspace_path: Path) -> str:
        """Get git diff --stat plus untracked files for diagnostic feedback."""
        if not (workspace_path / ".git").exists():
            return "No git repository found"
        try:
            diff = subprocess.run(
                ["git", "diff", "--stat", "HEAD"],
                cwd=str(workspace_path),
                capture_output=True,
                text=True,
                check=False,
            )
            out = diff.stdout.strip()
            untracked = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(workspace_path),
                capture_output=True,
                text=True,
                check=False,
            )
            untracked_lines = [
                line for line in untracked.stdout.splitlines() if line.startswith("??")
            ]
            if untracked_lines:
                out = f"{out}\nUntracked files:\n" + "\n".join(untracked_lines)
            return out.strip() or "No modified files detected on disk"
        except Exception as e:
            return f"Error reading git diff: {e}"

    @staticmethod
    def _record_milestone(
        recorder: Any,
        index: int,
        milestone: Milestone,
        turns_used: int,
        gate_detail: Dict[str, Any],
        advanced: bool,
    ) -> None:
        """Persist a milestone attempt and its gate verdict if tracing is enabled."""
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
                gate_ran=gate_detail.get("gate_ran", False),
                gate_passed=gate_detail.get("gate_passed", False),
                gate_exit_code=gate_detail.get("gate_exit_code"),
                gate_output=gate_detail.get("gate_output", ""),
                extra={
                    k: v
                    for k, v in gate_detail.items()
                    if k not in {"gate_ran", "gate_passed", "gate_exit_code", "gate_output"}
                },
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
        """Execute task across discrete milestones using stdio MCP state orchestration."""
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

        client = SuperstateMcpClient(
            superstate_bin=self.superstate_bin,
            cwd=workspace_path,
        )

        try:
            client.start()
            self.mcp_tools_discovered = len(client.tools)
            if self.superstate_bin is None and client.superstate_bin is not None:
                self.superstate_bin = client.superstate_bin

            plan_file = workspace_path / "plan.md"
            plan_text = plan_file.read_text(encoding="utf-8") if plan_file.is_file() else ""
            if plan_text:
                self.plan_source = "plan.md"

            # Every arm must receive the SAME verification command, or the comparison
            # measures the gate rather than the execution model. This arm was missed when
            # fixtures were added, so it ran on `true` while the daemon ran on a strict
            # gate -- and the daemon "lost" 5-0 purely because of that asymmetry.
            vcmd = agent_gate_for(getattr(task, "name", "") or "")
            if not vcmd:
                vcmd = getattr(task, "verification_cmd", None)
                if vcmd and ("/tests/" in vcmd or vcmd.startswith("bash /tests")):
                    vcmd = None
            effective_vcmd = vcmd if vcmd and vcmd.strip() else "true"

            # Phase 0: Zero-turn planning or planning turn
            if not plan_text and self.zero_turn_planning:
                client.state_init(
                    repo=workspace_path,
                    goal=task.instruction,
                    verify_cmd=effective_vcmd,
                    no_worktree=self.no_worktree or not self.worktree,
                    worktree=self.worktree and not self.no_worktree,
                )
                self.plan_source = "direct_state_handoff"
                self.decomposed = True
                self.milestones_planned = 1
                logger.info(
                    "Initialized MCP state directly with gate '%s' (zero-turn planning)",
                    effective_vcmd,
                )

            if not plan_text and self.plan_source != "direct_state_handoff":
                planning_prompt = (
                    "<state-evaluation>\n"
                    "State: 2. Spec Exists, Needs Plan\n"
                    "Required Skill: writing-plans\n"
                    "Status: Specification and requirements are complete. Generate plan.md directly.\n"
                    "</state-evaluation>\n\n"
                    f"{task.instruction}\n\n"
                    "## 🔬 PRE-ASSESSMENT & ADAPTIVE DECOMPOSITION PROTOCOL\n"
                    "Before writing `plan.md`, dynamically evaluate the architectural surface area:\n"
                    "1. **Adaptive Granularity:** For atomic, single-objective tasks create at most 1 to 2 milestones.\n"
                    "2. **Direct Invariant Verification:** Each milestone specifies a targeted verification command.\n\n"
                    "## 📝 PLAN FORMAT REQUIREMENTS\n"
                    "Write `plan.md` using `write_to_file`. Format each task as:\n"
                    "### Task <number>: <Title>\n"
                    "- **Depends on:** <Prerequisite Tasks or none>\n"
                    "**Files:**\n"
                    "- Modify: `<target_file_path>`\n"
                    "- Verification Command: `<plain command running directly in project environment>`\n"
                    "**Goal:** <One-sentence description of the capability delivered>\n\n"
                    "## ⛔ CRITICAL DIRECTIVE (MANDATORY)\n"
                    "- This is a planning-only turn. Do NOT execute shell commands or git.\n"
                    "- Synthesize the plan and call `write_to_file` to write `plan.md` immediately."
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
                    detail = telemetry.error_message or "Planning turn failed"
                    return result(False, detail)

                if plan_file.is_file():
                    plan_text = plan_file.read_text(encoding="utf-8")
                    self.plan_source = "plan.md"
                else:
                    plan_text = telemetry.raw_response
                    self.plan_source = "response"

            if self.plan_source == "direct_state_handoff":
                verify_by_title = {
                    f"task-1: {task.instruction}": effective_vcmd,
                    task.instruction: effective_vcmd,
                    "task-1": effective_vcmd,
                }
            else:
                milestones = _extract_plan_milestones(plan_text)
                self.milestones_planned = len(milestones)
                self.decomposed = not (
                    len(milestones) == 1 and milestones[0].title == FALLBACK_MILESTONE_TITLE
                )
                if not self.decomposed and self.require_decomposition:
                    return result(
                        False,
                        "Planning produced no parseable milestones (no '### Task N:' heading found)",
                    )
                if len(milestones) > self.max_milestones:
                    return result(
                        False,
                        f"Plan declares {len(milestones)} milestones, exceeding {self.max_milestones}",
                    )

                if self.plan_source == "response":
                    plan_file.write_text(plan_text, encoding="utf-8")

                if not any(TASK_HEADING_RE.match(line.strip()) for line in plan_text.splitlines()):
                    plan_file = workspace_path / "plan.normalized.md"
                    plan_file.write_text(
                        "\n\n".join(f"### {m.title}\n- Implement {m.title}" for m in milestones),
                        encoding="utf-8",
                    )

                client.state_init(
                    repo=workspace_path,
                    plan=plan_file,
                    no_worktree=self.no_worktree or not self.worktree,
                    worktree=self.worktree and not self.no_worktree,
                )
                verify_by_title = {m.title: m.verify_cmd for m in milestones}

            executed: set[str] = set()

            # Milestone execution loop
            for _ in range(self.max_milestones):
                if duration >= budget:
                    error_msg = f"Timed out after {duration:.1f}s (budget: {budget:.1f}s)"
                    break

                ready = [t for t in client.state_ready(workspace_path) if t not in executed]
                if not ready:
                    status = client.state_status(workspace_path)
                    is_completed = (
                        isinstance(status, dict)
                        and (
                            status.get("status") == "completed"
                            or (status.get("active_task") is None and status.get("completed_tasks"))
                        )
                    )
                    if is_completed:
                        break

                    active_task_raw = status.get("active_task") if isinstance(status, dict) else None
                    if active_task_raw:
                        candidate_title = (
                            f"{active_task_raw.get('id', '')}: {active_task_raw.get('title', '')}".strip(": ")
                            if isinstance(active_task_raw, dict)
                            else str(active_task_raw)
                        )
                        if candidate_title not in executed:
                            ready = [candidate_title]

                    if not ready:
                        break

                active = ready[0]
                executed.add(active)
                milestone_index = len(executed)

                current_prompt = client.state_prompt(
                    repo=workspace_path,
                    with_graph=True,
                    task=active,
                    no_worktree=self.no_worktree,
                )
                if not current_prompt:
                    current_prompt = client.state_prompt(
                        repo=workspace_path,
                        with_graph=True,
                        no_worktree=self.no_worktree,
                    )
                if not current_prompt:
                    error_msg = f"State engine produced no prompt for '{active}'"
                    break

                if "TARGETED EXECUTION CONTRACT" not in current_prompt:
                    contract = (
                        TARGETED_EXECUTION_CONTRACT_INPLACE
                        if (self.no_worktree or not self.worktree)
                        else TARGETED_EXECUTION_CONTRACT
                    )
                    # Off by default; see lab/engine/prompt_contracts.py.
                    current_prompt = apply_contract(current_prompt, contract, self.name)

                wt = self.active_worktree(workspace_path)
                turn_workspace = (
                    wt if (wt and wt.is_dir() and not self.no_worktree) else workspace_path
                )
                self._switch_container_workspace(container, workspace_path, wt)

                conversation_id: Optional[str] = None
                milestone_failed: Optional[str] = None
                milestone_turns = 0
                last_response = ""

                # Resolve verification command for active milestone
                active_cmd: Optional[str] = verify_by_title.get(active)
                if not active_cmd:
                    status_info = client.state_status(workspace_path)
                    if isinstance(status_info, dict):
                        act = status_info.get("active_task")
                        if isinstance(act, dict) and act.get("verification_cmd"):
                            active_cmd = act["verification_cmd"]
                if not active_cmd and self.plan_source == "direct_state_handoff":
                    active_cmd = effective_vcmd

                milestone = Milestone(title=active, verify_cmd=active_cmd)
                gate_detail: Dict[str, Any] = {
                    "gate_ran": False,
                    "gate_passed": None,
                    "gate_exit_code": None,
                    "gate_output": None,
                }
                advanced = False

                for _turn in range(self.max_turns_per_milestone):
                    turn_timeout = budget - duration
                    if turn_timeout <= 0:
                        milestone_failed = f"Timed out after {duration:.1f}s (budget: {budget:.1f}s)"
                        break

                    telemetry = driver.run(
                        task=task,
                        workspace_path=turn_workspace,
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
                    # Condition B: stateless turnkey turns, no conversation carry-over.
                    # See lab/engine/condition_b.py.
                    conversation_id = conversation_id_for(
                        self.name, telemetry.conversation_id or conversation_id
                    )
                    last_response = telemetry.raw_response or ""

                    if budget_hook is not None:
                        budget = max(budget, budget_hook())

                    # Check for approval requests
                    next_prompt = resolve_next_turn_prompt(last_response)
                    if next_prompt is not None:
                        current_prompt = next_prompt
                        continue

                    # Evaluate targeted verification gate & advance state
                    advanced = self._advance_state(
                        client=client,
                        workspace_path=workspace_path,
                        milestone=active,
                        verify_cmd=milestone.verify_cmd,
                        container=container,
                        gate_detail=gate_detail,
                    )
                    if advanced:
                        milestone_failed = None
                        break

                    if not telemetry.success:
                        milestone_failed = (
                            telemetry.error_message or f"Milestone '{active}' failed"
                        )
                        break

                    # Verification gate failed; feed diagnostic feedback if turns remain
                    if milestone_turns < self.max_turns_per_milestone and duration < budget:
                        gate_output = (
                            gate_detail.get("gate_output")
                            or gate_detail.get("engine_error")
                            or "Verification gate failed"
                        )
                        gate_exit_code = gate_detail.get("gate_exit_code", 1)

                        if last_response:
                            client.state_note(
                                repo=workspace_path,
                                message=f"[{active} - Turn {milestone_turns}] {last_response[:500]}",
                            )
                        client.state_note(
                            repo=workspace_path,
                            message=f"[Gate Failed - Turn {milestone_turns}] cmd='{milestone.verify_cmd}' exit={gate_exit_code}: {gate_output[:1000]}",
                        )

                        # Bounded stateless retry: clear conversation_id to avoid quadratic token bloat & anchoring bias
                        conversation_id = None
                        diff_stat = self._get_git_diff_stat(workspace_path)
                        turnkey_prompt = client.state_prompt(
                            repo=workspace_path,
                            task=active,
                            with_graph=True,
                            no_worktree=self.no_worktree,
                        ) or getattr(task, "instruction", "")

                        retry_prompt = (
                            f"{turnkey_prompt}\n\n"
                            f"## 🚨 VERIFICATION GATE FAILED (Attempt {milestone_turns} of {self.max_turns_per_milestone})\n\n"
                            f"The verification command `{milestone.verify_cmd}` failed with exit code {gate_exit_code}.\n\n"
                            f"### Gate Output:\n"
                            f"```\n{gate_output.strip()}\n```\n\n"
                            f"## 📁 Modified Files on Disk (git diff --stat)\n"
                            f"```\n{diff_stat}\n```\n\n"
                            f"Please diagnose this failure against the current workspace state, apply the necessary code or environment changes, and ensure the verification passes."
                        )
                        logger.info(
                            "Milestone '%s' gate failed on turn %d/%d; retrying with bounded diagnostic feedback (stateless turn)",
                            active,
                            milestone_turns,
                            self.max_turns_per_milestone,
                        )
                        current_prompt = retry_prompt
                        continue

                    milestone_failed = f"Verification gate failed for milestone '{active}'"
                    break

                if last_response:
                    distilled = self._distill_finding(last_response)
                    if distilled:
                        client.state_note(repo=workspace_path, message=f"[{active}] {distilled}")

                self._record_milestone(
                    recorder, milestone_index, milestone, milestone_turns, gate_detail, advanced
                )
                if not advanced:
                    error_msg = (
                        milestone_failed or f"Verification gate failed for milestone '{active}'"
                    )
                    break

        except Exception as exc:
            logger.error("Execution encountered exception: %s", exc, exc_info=True)
            error_msg = str(exc)
        finally:
            # Clean worktrees and stop MCP client process
            try:
                client.worktree_clean(repo=workspace_path, force=True)
            except Exception as exc:
                logger.debug("Failed cleaning worktree on finish: %s", exc)
            client.stop()
            self._switch_container_workspace(container, workspace_path, None)

        return result(error_msg is None, error_msg)
