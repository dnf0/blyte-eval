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
import shlex
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
    "1. **HARD STOP UPON PASSING (MANDATORY):** The moment the verification command passes with exit code 0, YOUR WORK ON THIS MILESTONE IS COMPLETE. You MUST stop immediately and return your summary. Do NOT second-guess the verification command. Do NOT run extra tests or alternative scripts. Do NOT inspect external directories. Output your summary and conclude your turn.\n"
    "2. **MINIMAL DIRECT FIX:** Write ONLY the minimal direct code required to pass the verification command. Do NOT build speculative CLI flags, general-purpose frameworks, or unnecessary abstraction layers. Do NOT author synthetic test suite files if the verification command can verify the deliverable directly.\n"
    "3. **SCOPE BOUNDARY:** Modify ONLY files directly related to this task. Do not touch unrelated files.\n"
    "4. **TARGETED VERIFICATION ONLY:** Run only the targeted test command. Do not execute full global test suites.\n"
    "5. **ZERO GLOBAL EXPLORATION:** Do not run recursive grep/find across the whole codebase or dump whole directories.\n"
    "6. **ZERO-READ AST EXECUTION:** Use targeted symbol lookup or line-bounded reads. Never cat entire files into context.\n"
    "7. **AUTOMATIC SNAPSHOTS:** The orchestrator automatically snapshots and commits your changes upon milestone completion. Do not attempt to merge or delete the worktree.\n"
    "8. **NO EXTERNAL LINTER PROBING:** Do not run external linters or formatters. Focus solely on making tests pass.\n"
    "9. **DO NOT READ SKILL OR RULES FILES:** Do not inspect GEMINI.md, AGENTS.md, or .cursorrules.\n"
    "10. **CONTAINMENT INVARIANT:** Confine ALL file inspections, code searches, and commands strictly to the active worktree directory and the provided container environment. Never inspect parent directories, host processes, or external repositories outside this workspace."
)

TARGETED_EXECUTION_CONTRACT_INPLACE = (
    "## TARGETED EXECUTION CONTRACT (STRICT ENFORCEMENT)\n"
    "1. **HARD STOP UPON PASSING (MANDATORY):** The moment the verification command passes with exit code 0, YOUR WORK ON THIS MILESTONE IS COMPLETE. You MUST stop immediately and return your summary. Do NOT second-guess the verification command. Do NOT run extra tests or alternative scripts. Do NOT inspect external directories. Output your summary and conclude your turn.\n"
    "2. **MINIMAL DIRECT FIX:** Write ONLY the minimal direct code required to pass the verification command. Do NOT build speculative CLI flags, general-purpose frameworks, or unnecessary abstraction layers. Do NOT author synthetic test suite files if the verification command can verify the deliverable directly.\n"
    "3. **SCOPE BOUNDARY:** Modify ONLY files directly related to this task. Do not touch unrelated files.\n"
    "4. **TARGETED VERIFICATION ONLY:** Run only the targeted test command. Do not execute full global test suites.\n"
    "5. **ZERO GLOBAL EXPLORATION:** Do not run recursive grep/find across the whole codebase or dump whole directories.\n"
    "6. **ZERO-READ AST EXECUTION:** Use targeted symbol lookup or line-bounded reads. Never cat entire files into context.\n"
    "7. **NO UNNECESSARY COMMITS:** Do not create manual git commits unless the task explicitly requires modifying git history. Focus solely on making tests pass.\n"
    "8. **NO EXTERNAL LINTER PROBING:** Do not run external linters or formatters. Focus solely on making tests pass.\n"
    "9. **DO NOT READ SKILL OR RULES FILES:** Do not inspect GEMINI.md, AGENTS.md, or .cursorrules.\n"
    "10. **CONTAINMENT INVARIANT:** Confine ALL file inspections, code searches, and commands strictly to the project container environment and workspace directory. Never inspect parent directories, host processes, or external repositories outside this workspace."
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

    # Prefer the most recently built artefact. A stale release build silently
    # shadows a freshly compiled debug one, and the run then measures old code
    # while reporting the engine it thinks it used.
    existing = [c for c in ENGINE_PATHS.get(engine, ()) if c.is_file()]
    if not existing:
        return None
    return max(existing, key=lambda c: c.stat().st_mtime)


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
        max_turns_per_milestone: int = 3,
        no_worktree: bool = False,
        zero_turn_planning: bool = False,
    ) -> None:
        if superstate_bin is not None and engine == DEFAULT_ENGINE:
            bin_path = Path(superstate_bin)
            if "superstate/target" in str(bin_path) or bin_path in ENGINE_PATHS.get(ENGINE_RUST, ()):
                engine = ENGINE_RUST
        if zero_turn_planning and engine == DEFAULT_ENGINE:
            rust_bin = find_superstate_binary(ENGINE_RUST)
            if rust_bin:
                engine = ENGINE_RUST
        self.engine = engine
        self.superstate_bin = superstate_bin or find_superstate_binary(engine)
        self.max_turns_per_milestone = max_turns_per_milestone
        self.no_worktree = no_worktree
        self.zero_turn_planning = zero_turn_planning
        self.engine_used: Optional[str] = None
        self.plan_source: Optional[str] = None
        self.milestones_planned: int = 0
        self.decomposed: bool = False
        if self.superstate_bin is None:
            logger.warning(
                "SuperstateAdapter: superstate binary not found. Arm C will fall back to the "
                "in-process Python state machine, which is NOT the system under test."
            )

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
        except Exception as e:
            logger.debug("Failed reading active_worktree from %s: %s", state_file, e)
            return None

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
            "no_worktree": self.no_worktree,
            "zero_turn_planning": self.zero_turn_planning,
            # Whether this run was actually a control-plane run.
            "plan_source": self.plan_source,
            "milestones_planned": self.milestones_planned,
            "decomposed": self.decomposed,
        }

    def _record_engine(self, engine: str) -> None:
        """Record the engine used, downgrading to the fallback if it is ever hit."""
        if engine == ENGINE_PYTHON_FALLBACK or self.engine_used is None:
            self.engine_used = engine

    #: Harness bookkeeping that must not count as uncommitted agent work.
    HARNESS_UNTRACKED = (".agent-state/", "plan.md", "plan.normalized.md", "run-in-container")

    @staticmethod
    def _distill_finding(response: str) -> str:
        """Extract a clean, concise finding from the turn's response to keep prompts bounded."""
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

    def _exclude_harness_artifacts(self, workspace_path: Path) -> None:
        """Keep harness files from dirtying the tree the git-clean gate inspects.

        The engine writes `.agent-state/` into the workspace, so an untracked
        state directory makes the working tree dirty and `--verify-git-clean`
        fails on its own bookkeeping -- the gate can never pass. Excluding these
        locally leaves the gate measuring what it is for: whether the agent
        committed its work.
        """
        exclude = workspace_path / ".git" / "info" / "exclude"
        if not exclude.parent.parent.is_dir():
            return  # not a git repository; nothing to exclude
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
        """Sanitize workspace so Arm C sees the same blank slate as the control arm."""
        self._exclude_harness_artifacts(workspace_path)
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
        if self.no_worktree and self.engine == ENGINE_RUST:
            args.append("--no-worktree")
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
                cmd = [
                    str(self.superstate_bin), "state", "init",
                    "--plan", str(plan_path),
                    out_flag, str(state_path),
                ]
                if self.no_worktree and self.engine == ENGINE_RUST:
                    cmd.append("--no-worktree")
                res = subprocess.run(
                    cmd,
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
        wt = self.active_worktree(workspace_path)
        target_dir = wt if (wt and wt.is_dir()) else workspace_path

        if container is not None:
            container_workdir = "/app"
            shell_cmd = ["/bin/sh", "-c", verify_cmd]
            try:
                exec_res = container.exec_run(shell_cmd, workdir=container_workdir)
            except TypeError:
                fallback_cmd = ["/bin/sh", "-c", f"cd {shlex.quote(str(container_workdir))} && {verify_cmd}"]
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
                                "Host verification gate passed via worktree path substitution (%s -> %s)",
                                verify_cmd,
                                alt_cmd,
                            )
                            return True, 0, (alt_res.stdout or "") + (alt_res.stderr or "")
                    except Exception as exc:
                        logger.debug("Host worktree path alternate gate check failed: %s", exc)
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
            res = container.exec_run(["sh", "-c", f"ln -sfn {shlex.quote(target)} /app"], workdir="/")
            code = res[0] if isinstance(res, tuple) else getattr(res, "exit_code", 0)
            if code != 0:
                out = res[1] if isinstance(res, tuple) else getattr(res, "output", b"")
                logger.warning("ln -sfn to %s failed with exit code %s: %s", target, code, out)
        except Exception as exc:
            logger.warning("Failed to switch container workspace symlink: %s", exc)

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
            wt = self.active_worktree(workspace_path)
            target_dir = wt if (wt and wt.is_dir()) else workspace_path

            # When the gate passes, auto-commit any uncommitted changes so git HEAD
            # advances and --verify-git-clean passes deterministically.
            if gate_cmd != "exit 1" and (workspace_path / ".git").exists():
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

            cmd = [str(self.superstate_bin), "state", "next"]
            if (workspace_path / ".git").exists():
                cmd.append("--verify-git-clean")
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
                    self._switch_container_workspace(container, workspace_path, None)
                    return True
                logger.warning("superstate state next gate failed: %s", res.stderr)
                if gate_detail is not None:
                    gate_detail["engine_error"] = res.stderr
                return False
            except Exception as e:
                logger.warning("Failed to invoke superstate state next: %s", e)
                if gate_detail is not None:
                    gate_detail["engine_error"] = str(e)
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

        vcmd = getattr(task, "verification_cmd", None)
        if not plan_text and self.zero_turn_planning and vcmd:
            state_path = workspace_path / ".agent-state" / "state.json"
            state_path.parent.mkdir(parents=True, exist_ok=True)
            init_ok = False

            # Direct state initialization via the superstate binary
            if self.superstate_bin:
                cmd = [
                    str(self.superstate_bin),
                    "state",
                    "init",
                    "--goal",
                    task.instruction,
                    "--verify-cmd",
                    vcmd,
                    "--state",
                    str(state_path),
                ]
                if self.no_worktree:
                    cmd.append("--no-worktree")

                try:
                    res = subprocess.run(
                        cmd,
                        cwd=str(workspace_path),
                        capture_output=True,
                        text=True,
                        timeout=30.0,
                    )
                    if res.returncode == 0:
                        self._record_engine(ENGINE_BINARY)
                        init_ok = True
                    else:
                        logger.warning("Direct state init failed: %s", res.stderr)
                except Exception as err:
                    logger.warning("Direct state init failed with exception: %s", err)

            # Fallback state creation if binary is missing or failed
            if not init_ok:
                self._record_engine(ENGINE_PYTHON_FALLBACK)
                state_data = {
                    "status": "in_progress",
                    "step": 1,
                    "active_task": {
                        "id": "task-1",
                        "title": task.instruction,
                        "depends_on": [],
                        "files_modify": [],
                        "interfaces_produces": [],
                        "verification_cmd": vcmd,
                    },
                    "pending_tasks": [],
                    "completed_tasks": [],
                    "modified_files": [],
                    "errors": [],
                    "plan_path": None,
                    "notes": [],
                    "active_worktree": None,
                    "active_branch": None,
                    "no_worktree": self.no_worktree,
                }
                state_path.write_text(json.dumps(state_data, indent=2), encoding="utf-8")

            self.plan_source = "direct_state_handoff"
            self.decomposed = True
            self.milestones_planned = 1
            logger.info(
                "Direct state handoff active: initialized state directly with gate '%s' without plan.md",
                vcmd,
            )

        if not plan_text and self.plan_source != "direct_state_handoff":
            # Phase 1: Planning turn if no plan exists
            planning_prompt = (
                "<state-evaluation>\n"
                "State: 2. Spec Exists, Needs Plan\n"
                "Required Skill: writing-plans\n"
                "Status: Specification and requirements are complete. Generate plan.md directly.\n"
                "</state-evaluation>\n\n"
                f"{task.instruction}\n\n"
                "## 🔬 PRE-ASSESSMENT & ADAPTIVE DECOMPOSITION PROTOCOL\n"
                "Before writing `plan.md`, dynamically evaluate the architectural surface area and requirement invariants:\n"
                "1. **Adaptive Granularity:**\n"
                "   - For atomic, single-objective tasks (bug fixes, data recovery, scripts, configuration), create at most 1 to 2 milestones.\n"
                "   - Do NOT artificially over-decompose a focused task into 4+ milestones.\n"
                "   - Only multi-module features touching distinct subsystems should have 3+ milestones.\n"
                "2. **Direct Invariant Verification:**\n"
                "   - Each milestone specifies a targeted verification command using the repository's native test runner (e.g. `go test ./parser/...`, `pytest tests/test_foo.py`) or a direct plain command verifying the goal invariant (e.g. `python3 -c \"...\"` or verifying the output file exists and is valid).\n"
                "   - Do NOT demand that the worker write synthetic test suites from scratch if an inline command or existing runner can verify the fix.\n\n"
                "## 📝 PLAN FORMAT REQUIREMENTS\n"
                "Write `plan.md` using `write_to_file`. Format each task as:\n"
                "### Task <number>: <Title>\n"
                "- **Depends on:** <Prerequisite Tasks or none>\n"
                "**Files:**\n"
                "- Modify: `<target_file_path>`\n"
                "- Verification Command: `<plain command running directly in project environment>`\n"
                "**Goal:** <One-sentence description of the capability delivered>\n\n"
                "Write each verification command as a PLAIN command that runs in the "
                "project environment, e.g. `go test ./parser/...`. Do not prefix it with "
                "any wrapper or helper script -- the command is executed directly in the "
                "project environment, where such a wrapper does not exist.\n\n"
                "## ⛔ CRITICAL DIRECTIVE (MANDATORY)\n"
                "- This is a planning-only turn. Do NOT execute shell commands, do NOT run git, and do NOT explore files.\n"
                "- Based on the specification above, synthesize the plan and call `write_to_file` to write `plan.md` immediately in the workspace.\n"
                "- Output ONLY `plan.md` via `write_to_file`. Do NOT output conversational preambles or lengthy analysis text."
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

        if self.plan_source == "direct_state_handoff":
            milestones = [Milestone(title=f"task-1: {task.instruction}", verify_cmd=vcmd)]
            verify_by_title = {
                f"task-1: {task.instruction}": vcmd,
                task.instruction: vcmd,
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

            verify_by_title = {m.title: m.verify_cmd for m in milestones}
        executed: set[str] = set()

        try:
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
                if "TARGETED EXECUTION CONTRACT" not in current_prompt:
                    contract = TARGETED_EXECUTION_CONTRACT_INPLACE if (self.no_worktree or self.engine == ENGINE_PYTHON) else TARGETED_EXECUTION_CONTRACT
                    current_prompt = f"{current_prompt}\n\n{contract}"
    
                wt = self.active_worktree(workspace_path)
                turn_workspace = wt if (wt and wt.is_dir() and not self.no_worktree) else workspace_path
                self._switch_container_workspace(container, workspace_path, wt)
    
                conversation_id: Optional[str] = None
                milestone_failed: Optional[str] = None
                milestone_turns = 0
                last_response = ""
                advanced = False
                milestone = Milestone(
                    title=active,
                    verify_cmd=verify_by_title.get(active)
                    or (getattr(task, "verification_cmd", None) if self.plan_source == "direct_state_handoff" else None),
                )
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
    
                    # Verification gate failed. If turns remain, feed diagnostic feedback back to the agent.
                    if milestone_turns < self.max_turns_per_milestone and duration < budget:
                        gate_output = (
                            gate_detail.get("gate_output")
                            or gate_detail.get("engine_error")
                            or "Verification gate failed"
                        )
                        gate_exit_code = gate_detail.get("gate_exit_code", 1)
    
                        if last_response:
                            self.record_note(
                                workspace_path, f"[{active} - Turn {milestone_turns}] {last_response[:500]}"
                            )
                        self.record_note(
                            workspace_path,
                            f"[Gate Failed - Turn {milestone_turns}] cmd='{milestone.verify_cmd}' exit={gate_exit_code}: {gate_output[:1000]}",
                        )
    
                        retry_prompt = (
                            f"## VERIFICATION GATE FAILED (Attempt {milestone_turns} of {self.max_turns_per_milestone})\n\n"
                            f"The verification command `{milestone.verify_cmd}` failed with exit code {gate_exit_code}.\n\n"
                            f"### Gate Output:\n"
                            f"```\n{gate_output.strip()}\n```\n\n"
                            f"Please diagnose this failure, apply the necessary code or environment changes, and ensure the verification passes."
                        )
                        logger.info(
                            "Milestone '%s' gate failed on turn %d/%d; retrying with diagnostic feedback",
                            active,
                            milestone_turns,
                            self.max_turns_per_milestone,
                        )
                        current_prompt = retry_prompt
                        continue
    
                    # Agent concluded without asking for user approval, but verification gate failed
                    milestone_failed = f"Verification gate failed for milestone '{active}'"
                    break
    
                # Carry what this turn learned into the ledger, so later milestones
                # inherit it rather than starting blind.
                if last_response:
                    distilled = self._distill_finding(last_response)
                    if distilled:
                        self.record_note(workspace_path, f"[{active}] {distilled}")
    
                self._record_milestone(
                    recorder, milestone_index, milestone, milestone_turns, gate_detail, advanced
                )
                if not advanced:
                    error_msg = milestone_failed or f"Verification gate failed for milestone '{active}'"
                    break
    
        finally:
            # Ensure container /app points back to /workspace_root for held-out grading
            self._switch_container_workspace(container, workspace_path, None)

        return result(error_msg is None, error_msg)
