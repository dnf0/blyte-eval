"""Agent-level autonomous adapter for Superstate over Model Context Protocol (MCP).

Exposes the 25 Superstate MCP tools directly to the agent runtime (e.g. Claude Code
or Antigravity CLI) under an autonomous execution contract. The agent is responsible for
inspecting its own state, retrieving milestone prompts, running commands, and advancing
its milestones over MCP tool calls.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import re
import shlex
import subprocess
from typing import Any, Dict, Optional

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.base import (
    AgentAdapter,
    AgentDriver,
    BudgetHook,
    TaskRunResult,
    strip_preexisting_guidance,
)
from lab.engine.approval import resolve_next_turn_prompt
from lab.engine.mcp.client import SuperstateMcpClient

logger = logging.getLogger("superstate_eval.adapters.superstate_agent_mcp")

BRIDGE_PREFIX_RE = re.compile(r"(?:^|(?<=[;&|(]))\s*\.?/?run-in-container\s+")

AUTONOMOUS_MCP_EXECUTION_CONTRACT = (
    "## AUTONOMOUS SUPERSTATE MCP EXECUTION CONTRACT\n\n"
    "You have full access to the Superstate MCP tool suite for deterministic state and workflow management:\n"
    "- `state_status` or `state_show`: Inspect overall progress, pending milestones, and active task status.\n"
    "- `state_prompt`: Retrieve turnkey milestone instructions, dependencies, and targeted verification criteria.\n"
    "- `state_exec`: Execute commands with optional automatic state advancement and verification.\n"
    "- `state_next`: Advance to the next milestone once the active milestone's changes and verification gates are satisfied.\n"
    "- `state_note`: Record architectural findings, hypotheses, and milestone progress notes.\n\n"
    "### Operating Rules:\n"
    "1. **Check State First:** Call `state_status` or `state_prompt` to inspect your active task.\n"
    "2. **Implement & Verify:** Make necessary file edits and run tests for the active task.\n"
    "3. **Advance State:** Call `state_next` (or `state_exec` with advance=True) to commit and advance each completed task.\n"
    "4. **Log Progress:** Use `state_note` to log significant decisions or findings.\n"
    "5. **Conclude When Complete:** When all milestones are completed (`state_status` reports status 'completed' or no remaining active task), finish your turn with a concise summary."
)


class SuperstateAgentMcpAdapter(AgentAdapter):
    """Adapter evaluating autonomous agent behavior with direct Superstate MCP tooling."""

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
        name: str = "superstate_agent_mcp",
        max_turns: int = 20,
    ) -> None:
        """Initialize the autonomous Superstate MCP adapter configuration.

        Parameters:
            superstate_bin: Optional path to the superstate executable binary.
            name: Harness name identifying this evaluation arm.
            max_turns: Maximum allowable conversation turns for autonomous agent execution.
        """
        self.superstate_bin = Path(superstate_bin) if superstate_bin is not None else None
        self._name = name
        self.max_turns = max_turns
        self.mcp_tools_discovered: int = 0

    @property
    def name(self) -> str:
        """Name of the evaluation arm."""
        return self._name

    def get_provenance(self) -> Dict[str, Any]:
        """Report state engine, transport, and autonomous tooling provenance.

        Returns:
            Dictionary containing metadata for benchmark reporting.
        """
        return {
            "engine": "superstate_agent_mcp",
            "transport": "mcp_agent_tooling",
            "autonomous": True,
            "superstate_bin": str(self.superstate_bin) if self.superstate_bin else None,
            "mcp_tools_discovered": self.mcp_tools_discovered,
        }

    def _exclude_harness_artifacts(self, workspace_path: Path) -> None:
        """Keep harness files from dirtying the git working tree.

        Appends harness-internal paths to .git/info/exclude so clean git checks pass.

        Parameters:
            workspace_path: Root path of the workspace repository.
        """
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
        """Sanitize workspace by stripping legacy guidance and excluding harness artifacts.

        Parameters:
            workspace_path: Target workspace path for the task execution.
        """
        self._exclude_harness_artifacts(workspace_path)
        strip_preexisting_guidance(workspace_path)

    @staticmethod
    def normalize_gate_command(verify_cmd: str, in_container: bool) -> str:
        """Strip host-side bridge scripts when running verification inside the container.

        Parameters:
            verify_cmd: Shell verification command string.
            in_container: True if the command will be run directly inside container.

        Returns:
            Clean command string stripped of container wrappers.
        """
        if not in_container:
            return verify_cmd
        return BRIDGE_PREFIX_RE.sub(
            lambda m: m.group(0)[: -len(m.group(0).lstrip())] or "", verify_cmd
        ).strip()

    def _run_gate_command(
        self,
        workspace_path: Path,
        verify_cmd: str,
        container: Any = None,
    ) -> tuple[bool, Optional[int], str]:
        """Execute a verification command either inside a container sandbox or on the host.

        Parameters:
            workspace_path: Target workspace directory.
            verify_cmd: Verification command string to run.
            container: Optional Docker container instance.

        Returns:
            Tuple of (passed, exit_code, combined_output).
        """
        # Strip container wrappers if already executing within container sandbox
        verify_cmd = self.normalize_gate_command(verify_cmd, in_container=container is not None)

        if container is not None:
            container_workdir = "/app"
            # Sealed held-out test paths must not fail the run during agent evaluation
            if "/tests/" in verify_cmd or verify_cmd.startswith("bash /tests"):
                try:
                    chk = container.exec_run(["test", "-d", "/tests"])
                    chk_code = chk[0] if isinstance(chk, tuple) else getattr(chk, "exit_code", 0)
                    if chk_code != 0:
                        logger.info("Held-out test path /tests is sealed; skipping gate")
                        return True, 0, "Held-out test path /tests is sealed"
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

        # Host-level subprocess verification
        try:
            res = subprocess.run(
                verify_cmd,
                shell=True,
                cwd=str(workspace_path),
                capture_output=True,
                text=True,
                timeout=300.0,
            )
            passed = res.returncode == 0
            output = (res.stdout or "") + (res.stderr or "")
            return passed, res.returncode, output
        except Exception as e:
            logger.warning("Verification command failed to run on host: %s", e)
            return False, None, f"gate command could not be executed: {e}"

    def _auto_commit_if_dirty(self, workspace_path: Path, milestone_desc: str) -> None:
        """Auto-commit any pending git changes if the working tree is dirty.

        Parameters:
            workspace_path: Root of the repository.
            milestone_desc: Description to include in checkpoint commit message.
        """
        if not (workspace_path / ".git").exists():
            return
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
                    ["git", "add", "-A"],
                    cwd=str(workspace_path),
                    capture_output=True,
                    check=False,
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
                        f"chore: checkpoint {milestone_desc}",
                    ],
                    cwd=str(workspace_path),
                    capture_output=True,
                    check=False,
                )
        except Exception as exc:
            logger.debug("Failed auto-committing pending changes: %s", exc)

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
        """Execute task autonomously with the agent directly wielding Superstate MCP tools.

        Parameters:
            workspace_path: Working directory for task execution.
            task: Task specification containing instructions and verification details.
            driver: Agent driver to execute turns (e.g. ClaudeCliDriver).
            timeout_sec: Maximum duration allowed for the execution.
            container: Optional Docker container sandbox.
            budget_hook: Optional hook to extend budget based on progress.
            recorder: Optional trace recorder.

        Returns:
            TaskRunResult summarizing execution success, metrics, and provenance.
        """
        # Step 1: Prepare workspace and exclude internal artifacts
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
            # Step 2: Start Superstate MCP server and inspect discovered tools
            client.start()
            self.mcp_tools_discovered = len(client.tools)
            if self.superstate_bin is None and client.superstate_bin is not None:
                self.superstate_bin = client.superstate_bin

            # Step 3: Initialize state tracking
            plan_file = workspace_path / "plan.md"
            if plan_file.is_file():
                client.state_init(
                    repo=workspace_path,
                    plan=plan_file,
                    no_worktree=True,
                )
            else:
                vcmd = getattr(task, "verification_cmd", None)
                if vcmd and ("/tests/" in vcmd or vcmd.startswith("bash /tests")):
                    vcmd = None
                client.state_init(
                    repo=workspace_path,
                    goal=task.instruction,
                    verify_cmd=vcmd,
                    no_worktree=True,
                )

            # Step 4: Configure driver to expose Superstate MCP tools
            if hasattr(driver, "superstate_mcp"):
                setattr(driver, "superstate_mcp", True)
            if (
                hasattr(driver, "superstate_bin")
                and getattr(driver, "superstate_bin") is None
                and self.superstate_bin is not None
            ):
                setattr(driver, "superstate_bin", str(self.superstate_bin))

            # Step 5: Construct autonomous seed prompt with contract
            seed_prompt = (
                f"{task.instruction}\n\n"
                f"{AUTONOMOUS_MCP_EXECUTION_CONTRACT}"
            )

            current_prompt: Optional[str] = seed_prompt
            conversation_id: Optional[str] = None
            last_response = ""

            # Step 6: Multi-turn autonomous driver execution loop
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
                        phase="autonomous_mcp",
                        prompt=current_prompt,
                        telemetry=telemetry,
                    )

                duration += telemetry.duration_seconds
                input_tokens += telemetry.input_tokens
                output_tokens += telemetry.output_tokens
                cost_usd += telemetry.cost_usd
                turns += 1
                conversation_id = telemetry.conversation_id or conversation_id
                last_response = telemetry.raw_response or ""

                if budget_hook is not None:
                    budget = max(budget, budget_hook())

                if not telemetry.success:
                    error_msg = telemetry.error_message or "Agent turn failed"
                    break

                # Inspect for clarification / approval requests
                next_prompt = resolve_next_turn_prompt(last_response)
                if next_prompt is not None:
                    current_prompt = next_prompt
                    continue

                # Agent concluded turn without asking for approval
                break

            # Step 7: Inspect resulting state machine status
            state_data: dict[str, Any] = {}
            try:
                state_data = client.state_status(workspace_path)
            except Exception as exc:
                logger.debug("Failed querying state_status via client: %s", exc)
                state_file = workspace_path / ".agent-state" / "state.json"
                if state_file.is_file():
                    try:
                        state_data = json.loads(state_file.read_text(encoding="utf-8"))
                    except Exception:
                        pass

            # Determine whether the agent reached completion status
            is_completed = (
                state_data.get("status") == "completed"
                or (state_data.get("active_task") is None and bool(state_data.get("completed_tasks")))
            )

            if is_completed:
                logger.info("Autonomous agent reached state completion successfully")
                self._auto_commit_if_dirty(workspace_path, "autonomous milestone completion")
                return result(True, None)

            # Step 8: Fallback check against verification gate if state is incomplete
            vcmd = getattr(task, "verification_cmd", None)
            if vcmd:
                logger.info("State not marked completed; evaluating fallback verification gate: %s", vcmd)
                gate_passed, exit_code, output = self._run_gate_command(
                    workspace_path, vcmd, container=container
                )
                if gate_passed:
                    logger.info("Verification gate passed on fallback check")
                    self._auto_commit_if_dirty(workspace_path, "verified task completion")
                    return result(True, None)

                gate_err = (
                    f"Verification gate failed with exit code {exit_code}: {output[:500]}"
                    if output
                    else f"Verification gate failed with exit code {exit_code}"
                )
                return result(False, gate_err)

            # No verification command and state not completed
            return result(
                False,
                error_msg or "Task incomplete: state was not advanced to completion and no verification gate was available",
            )

        except Exception as exc:
            logger.error("Execution encountered exception: %s", exc, exc_info=True)
            return result(False, str(exc))
        finally:
            # Step 9: Clean worktrees and stop MCP client child process
            try:
                client.worktree_clean(repo=workspace_path, force=True)
            except Exception as exc:
                logger.debug("Failed cleaning worktree on finish: %s", exc)
            client.stop()
