"""Superstate daemon evaluation adapter for autonomous detached headless execution."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
import shlex
import subprocess
import time
from typing import Any, Dict, Optional

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.base import (
    AgentAdapter,
    BudgetHook,
    TaskRunResult,
    strip_preexisting_guidance,
)
from lab.engine.adapters.superstate import ENGINE_RUST, find_superstate_binary
from lab.engine.mcp.client import SuperstateMcpClient

logger = logging.getLogger("superstate_eval.adapters.superstate_daemon")

# A gate the driver proposes must actually discriminate. These always pass, so
# accepting one reproduces exactly the no-op-gate failure this derivation exists to fix.
NOOP_GATE_RE = re.compile(r"^\s*(true|:|exit\s+0)\s*;?\s*$", re.IGNORECASE)

GATE_PROMPT = """Read the task below and output ONE shell command that verifies whether it is complete.

Rules:
- Output ONLY the command. No prose, no markdown fences, no explanation.
- It must exit 0 when the task is done and non-zero when it is not done.
- It must FAIL right now, before any work has been performed.
- Use only what the task itself describes (its own snippets, its own test suite).
- Do NOT reference /tests/ -- that path holds a sealed grader you must not read or run.

TASK:
{instruction}
"""

BRIDGE_PREFIX_RE = re.compile(r"(?:^|(?<=[;&|(]))\s*\.?/?run-in-container\s+")


def is_pid_alive(pid: int) -> bool:
    """Check if process with given PID is alive."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


class SuperstateDaemonAdapter(AgentAdapter):
    """Adapter executing tasks autonomously via the detached Superstate DaemonRunner."""

    HARNESS_UNTRACKED = (
        ".agent-state/",
        "plan.md",
        "plan.normalized.md",
        "run-in-container",
    )

    def __init__(
        self,
        superstate_bin: Optional[Path | str] = None,
        driver_preset: str = "agy",
        poll_interval_sec: float = 1.0,
        name: str = "superstate_daemon",
        max_retries: int = 3,
        timeout: float = 300.0,
        no_worktree: bool = True,
        worktree: bool = False,
    ) -> None:
        """Initialize SuperstateDaemonAdapter with driver preset and polling configuration."""
        # `state daemon` exists ONLY in the Rust engine -- agent-rules (the Python
        # engine, and the default for find_superstate_binary()) has no such verb. Resolve
        # ENGINE_RUST explicitly and fail closed: this arm previously worked only because
        # ~/.local/bin/superstate was a symlink to the Rust build, so the bare call
        # silently returned Rust while claiming Python.
        self.superstate_bin = (
            Path(superstate_bin) if superstate_bin is not None else find_superstate_binary(ENGINE_RUST)
        )
        self.driver_preset = driver_preset
        self.poll_interval_sec = poll_interval_sec
        self._name = name
        self.max_retries = max_retries
        self.timeout = timeout
        self.no_worktree = no_worktree
        self.worktree = worktree
        self.daemon_pid: Optional[int] = None
        self.step_count: int = 0

    @property
    def name(self) -> str:
        """Name of the evaluation arm."""
        return self._name

    def get_provenance(self) -> Dict[str, Any]:
        """Report execution provenance metadata."""
        return {
            "engine": "superstate_rust_daemon",
            "transport": "detached_daemon",
            "driver_preset": self.driver_preset,
            "superstate_bin": str(self.superstate_bin) if self.superstate_bin else None,
            "daemon_pid": self.daemon_pid,
            "no_worktree": self.no_worktree,
            "worktree": self.worktree,
        }

    def _exclude_harness_artifacts(self, workspace_path: Path) -> None:
        """Exclude harness artifacts from git tracking."""
        exclude = workspace_path / ".git" / "info" / "exclude"
        if not exclude.parent.parent.is_dir():
            return
        try:
            exclude.parent.mkdir(parents=True, exist_ok=True)
            existing = exclude.read_text(encoding="utf-8") if exclude.is_file() else ""
            missing = [a for a in self.HARNESS_UNTRACKED if a not in existing]
            if missing:
                with exclude.open("a", encoding="utf-8") as fh:
                    for entry in missing:
                        fh.write(f"{entry}\n")
        except OSError as err:
            logger.debug("Failed configuring git exclude: %s", err)

    def _init_daemon_state(self, workspace_path: Path, task: TaskSpec, verify_cmd: str) -> bool:
        """Initialize state machine tracking via MCP superstate_handoff or CLI fallback."""
        state_dir = workspace_path / ".agent-state"
        state_dir.mkdir(parents=True, exist_ok=True)
        state_file = state_dir / "state.json"

        # Attempt to use MCP client superstate_handoff with detach=False to provision state
        try:
            client = SuperstateMcpClient(superstate_bin=self.superstate_bin, cwd=workspace_path)
            with client:
                if "superstate_handoff" in client.tools:
                    res = client.superstate_handoff(
                        goal=task.instruction,
                        verify_cmd=verify_cmd,
                        driver=self.driver_preset,
                        no_worktree=self.no_worktree or not self.worktree,
                        worktree=self.worktree and not self.no_worktree,
                        detach=False,
                        state=state_file,
                    )
                    return res.get("status") in ("ready", "success", "ok")
        except Exception as e:
            logger.debug("MCP superstate_handoff initialization failed, falling back to CLI: %s", e)

        # Fallback to CLI superstate state handoff or state init
        if self.superstate_bin:
            cmd = [
                str(self.superstate_bin),
                "state",
                "handoff",
                "--goal",
                task.instruction,
                "--verify-cmd",
                verify_cmd,
                "--driver",
                self.driver_preset,
                "--state",
                str(state_file),
            ]
            if self.no_worktree or not self.worktree:
                cmd.append("--no-worktree")
            elif self.worktree:
                cmd.append("--worktree")
            try:
                res = subprocess.run(cmd, cwd=str(workspace_path), capture_output=True, text=True, timeout=30.0)
                if res.returncode == 0:
                    return True
            except Exception as e:
                logger.debug("CLI handoff failed: %s", e)

        # Minimal fallback direct JSON initialization
        direct_state = {
            "version": "1.0",
            "goal": task.instruction,
            "status": "in_progress",
            "step": 0,
            "active_task": "task-1",
            "active_milestone": "task-1",
            "tasks": [
                {
                    "id": "task-1",
                    "title": task.instruction[:80],
                    "verify_cmd": verify_cmd,
                    "status": "in_progress",
                }
            ],
            "completed_tasks": [],
            "failed_tasks": [],
        }
        state_file.write_text(json.dumps(direct_state, indent=2), encoding="utf-8")
        return True

    def _spawn_daemon(self, workspace_path: Path) -> bool:
        """Spawn the autonomous background daemon process."""
        state_file = workspace_path / ".agent-state" / "state.json"
        if not self.superstate_bin:
            logger.warning("No superstate binary resolved to spawn daemon")
            return False

        cmd = [
            str(self.superstate_bin),
            "state",
            "daemon",
            "--state",
            str(state_file),
            "--driver",
            self.driver_preset,
            "--detach",
            "--max-retries",
            str(self.max_retries),
            "--timeout",
            str(int(self.timeout)),
        ]
        try:
            res = subprocess.run(cmd, cwd=str(workspace_path), capture_output=True, text=True, timeout=30.0)
            return res.returncode == 0
        except Exception as e:
            logger.error("Failed to spawn superstate daemon: %s", e)
            return False

    @staticmethod
    def _is_sealed_gate(verify_cmd: Optional[str]) -> bool:
        """Whether a verification command points at the sealed held-out grader."""
        if not verify_cmd:
            return True
        return "/tests/" in verify_cmd or verify_cmd.strip().startswith("bash /tests")

    @staticmethod
    def _extract_gate(raw_response: str) -> Optional[str]:
        """Pull a single shell command out of a driver response."""
        if not raw_response:
            return None
        text = raw_response.strip()
        fence = re.search(r"```(?:[a-zA-Z]*\n)?(.+?)```", text, re.DOTALL)
        if fence:
            text = fence.group(1).strip()
        for line in (ln.strip() for ln in text.splitlines()):
            if line and not line.startswith("#"):
                return line
        return None

    def _derive_gate(
        self,
        workspace_path: Path,
        task: TaskSpec,
        driver: Any,
        container: Any,
        timeout_sec: float,
    ) -> tuple[str, Optional[Any]]:
        """Resolve a verification command that actually discriminates.

        These benchmark tasks ship only a sealed held-out grader, which the agent must
        never gate on -- that is the answer key. The harness therefore handed the daemon
        `true`, which always passes, so the daemon declared completion after a single
        driver turn and stopped. Its whole mechanism (gate, diagnose, retry) was inert.

        The task instructions do describe how to check the work ("this snippet should
        run", "these tests should still pass"), so the gate is recoverable: ask the
        driver to author one, then fail closed -- a proposed gate is rejected unless it
        currently FAILS, because a gate that already passes cannot discriminate.

        Returns the gate and the telemetry of the authoring turn (for cost accounting).
        """
        declared = getattr(task, "verification_cmd", None)
        if not self._is_sealed_gate(declared):
            logger.info("Gate: using task-declared verifier %r", declared)
            return str(declared), None

        if driver is None:
            logger.warning("Gate: no driver available to author one; falling back to no-op")
            return "true", None

        try:
            telemetry = driver.run(
                task,
                workspace_path,
                prompt_override=GATE_PROMPT.format(instruction=task.instruction),
                timeout_sec=min(300.0, timeout_sec),
                container=container,
            )
        except Exception as exc:
            logger.warning("Gate: driver failed to author a gate (%s); falling back to no-op", exc)
            return "true", None

        candidate = self._extract_gate(getattr(telemetry, "raw_response", "") or "")
        if not candidate:
            logger.warning("Gate: driver returned no parseable command; falling back to no-op")
            return "true", telemetry
        if NOOP_GATE_RE.match(candidate) or self._is_sealed_gate(candidate):
            logger.warning("Gate: rejected %r (no-op or reads the sealed grader)", candidate)
            return "true", telemetry

        passes_now, _, _ = self._run_gate_command(workspace_path, candidate, container=container)
        if passes_now:
            logger.warning("Gate: rejected %r -- already passes before any work", candidate)
            return "true", telemetry

        logger.info("Gate: driver authored %r (fails before work, as required)", candidate)
        return candidate, telemetry

    def _write_driver_wrapper(
        self, workspace_path: Path, driver: Any, container: Any = None
    ) -> Optional[Path]:
        """Write a shell wrapper the Rust daemon invokes instead of a bare preset.

        Three things are otherwise lost, all because the Rust daemon spawns the driver
        itself and so bypasses the Python driver's own prompt and flag handling.

        1. The daemon expands the `agy` preset with only `-p` and permission flags, so
           the harness's `--model` never reaches it and this arm silently ran a
           different model than every other arm.
        2. The daemon records no driver usage, so the arm reported $0.00 / 0 tokens.
        3. The daemon's turnkey prompt carries no environment contract, so the worker
           was never told that dependencies, compilers and test runners live in the
           container, nor that `./run-in-container` exists. It therefore worked on the
           host while its own verification gate ran inside the container -- the two
           halves of the handoff operating on different environments, which is the
           single largest cause of this arm's failures.

        Non-preset driver commands are passed through unmodified, so this wrapper is
        the seam for all three.
        """
        cli_path = getattr(driver, "cli_path", None)
        model = getattr(driver, "model", None)
        if not cli_path or not model:
            return None

        turns_dir = workspace_path / ".agent-state" / "driver-turns"
        turns_dir.mkdir(parents=True, exist_ok=True)

        # The environment contract the Python driver appends to every prompt it sends.
        # The daemon renders its own prompt and never sees it, so append it here.
        contract_line = ""
        if container is not None:
            from lab.engine.drivers.agy_cli import CONTAINER_GUIDANCE_TEMPLATE

            contract = workspace_path / ".agent-state" / "environment-contract.md"
            contract.write_text(CONTAINER_GUIDANCE_TEMPLATE, encoding="utf-8")
            contract_line = f'PROMPT="$PROMPT\n$(cat {shlex.quote(str(contract))})"\n'

        wrapper = workspace_path / ".agent-state" / "driver-wrapper.sh"
        script = (
            "#!/bin/sh\n"
            "# Generated by SuperstateDaemonAdapter -- do not edit.\n"
            "# The daemon pipes the turnkey prompt on stdin and passes non-preset driver\n"
            "# commands through unmodified, so this is where the harness pins the model,\n"
            "# captures the usage the daemon never records, and appends the environment\n"
            "# contract the daemon's own prompt omits.\n"
            "PROMPT=$(cat)\n"
            f"{contract_line}"
            f'OUT="{turns_dir}/turn-$$-$(date +%s).json"\n'
            f"{shlex.quote(str(cli_path))} \\\n"
            f"  --model {shlex.quote(str(model))} \\\n"
            "  --output-format json \\\n"
            "  --dangerously-skip-permissions \\\n"
            f"  --add-dir {shlex.quote(str(workspace_path))} \\\n"
            '  --print "$PROMPT" > "$OUT" 2>/dev/null\n'
            "status=$?\n"
            'cat "$OUT"\n'
            "exit $status\n"
        )
        wrapper.write_text(script, encoding="utf-8")
        wrapper.chmod(0o755)
        return wrapper

    def _collect_driver_telemetry(self, workspace_path: Path) -> tuple[int, int]:
        """Sum token usage across the driver turns the wrapper captured."""
        turns_dir = workspace_path / ".agent-state" / "driver-turns"
        total_in = total_out = 0
        if not turns_dir.is_dir():
            return 0, 0
        for turn_file in sorted(turns_dir.glob("turn-*.json")):
            try:
                usage = json.loads(turn_file.read_text(encoding="utf-8")).get("usage", {})
            except Exception:
                continue
            total_in += int(usage.get("input_tokens", 0) or 0)
            total_out += int(usage.get("output_tokens", 0) or 0)
        return total_in, total_out

    @staticmethod
    def normalize_gate_command(verify_cmd: str, in_container: bool) -> str:
        """Strip bridge prefixes when running inside sandbox container."""
        if not in_container:
            return verify_cmd
        return BRIDGE_PREFIX_RE.sub(lambda m: m.group(0)[: -len(m.group(0).lstrip())] or "", verify_cmd).strip()

    def _run_gate_command(
        self,
        workspace_path: Path,
        verify_cmd: str,
        container: Any = None,
    ) -> tuple[bool, Optional[int], str]:
        """Execute verification command within target environment."""
        verify_cmd = self.normalize_gate_command(verify_cmd, in_container=container is not None)
        target_dir = workspace_path

        if container is not None:
            container_workdir = "/app"
            if "/tests/" in verify_cmd or verify_cmd.startswith("bash /tests"):
                try:
                    chk = container.exec_run(["test", "-d", "/tests"])
                    chk_code = chk[0] if isinstance(chk, tuple) else getattr(chk, "exit_code", 0)
                    if chk_code != 0:
                        return True, 0, "Held-out test path /tests sealed during agent phase"
                except Exception:
                    pass

            shell_cmd = ["/bin/sh", "-c", verify_cmd]
            try:
                exec_res = container.exec_run(shell_cmd, workdir=container_workdir)
            except TypeError:
                fallback_cmd = ["/bin/sh", "-c", f"cd {shlex.quote(str(container_workdir))} && {verify_cmd}"]
                exec_res = container.exec_run(fallback_cmd)
            except Exception as e:
                return False, None, f"gate command failed in container: {e}"

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
            return res.returncode == 0, res.returncode, (res.stdout + res.stderr)
        except subprocess.TimeoutExpired:
            return False, None, "gate command timed out"
        except Exception as e:
            return False, None, str(e)

    def execute(
        self,
        workspace_path: Path,
        task: TaskSpec,
        driver: Any = None,
        timeout_sec: Optional[float] = None,
        container: Any = None,
        budget_hook: Optional[BudgetHook] = None,
        recorder: Any = None,
    ) -> TaskRunResult:
        """Execute task autonomously via the Superstate DaemonRunner."""
        strip_preexisting_guidance(workspace_path)
        self._exclude_harness_artifacts(workspace_path)

        budget = timeout_sec or task.agent_timeout_sec or 3600.0
        start_time = time.monotonic()

        effective_vcmd, gate_telemetry = self._derive_gate(
            workspace_path, task, driver, container, budget
        )

        # The gate may resolve without a driver turn (a task-declared verifier), in which
        # case nothing has provisioned `./run-in-container` yet. The wrapper's contract
        # points the worker at that script, so it must actually exist.
        if container is not None and hasattr(driver, "_setup_container_bridge"):
            try:
                driver._setup_container_bridge(workspace_path, container)
            except Exception as exc:
                logger.warning("Could not provision container bridge: %s", exc)

        # Pin the model, capture usage, and supply the environment contract the daemon's
        # own prompt omits (see _write_driver_wrapper).
        wrapper = self._write_driver_wrapper(workspace_path, driver, container)
        if wrapper is not None:
            self.driver_preset = str(wrapper)

        # Step 1: Initialize state
        if not self._init_daemon_state(workspace_path, task, effective_vcmd):
            return TaskRunResult(
                task_id=task.task_id,
                harness_name=self.name,
                success=False,
                duration_seconds=time.monotonic() - start_time,
                error_message="Failed to initialize daemon state",
                provenance=self.get_provenance(),
            )

        # Step 2: Spawn background daemon
        if not self._spawn_daemon(workspace_path):
            return TaskRunResult(
                task_id=task.task_id,
                harness_name=self.name,
                success=False,
                duration_seconds=time.monotonic() - start_time,
                error_message="Failed to spawn superstate daemon",
                provenance=self.get_provenance(),
            )

        # Step 3: Monitor daemon PID and state progress
        state_file = workspace_path / ".agent-state" / "state.json"
        daemons_dir = workspace_path / ".agent-state" / "daemons"
        pid_file = daemons_dir / "default.pid"

        pid: Optional[int] = None
        for _ in range(50):
            if pid_file.is_file():
                try:
                    pid = int(pid_file.read_text(encoding="utf-8").strip())
                    self.daemon_pid = pid
                    break
                except Exception:
                    pass
            time.sleep(0.05)

        is_completed = False
        error_msg: Optional[str] = None

        while True:
            elapsed = time.monotonic() - start_time
            if budget_hook:
                budget = budget_hook()
            if elapsed >= budget:
                error_msg = f"Daemon timed out after {elapsed:.1f}s (budget: {budget:.1f}s)"
                break

            # Check state file
            if state_file.is_file():
                try:
                    state_data = json.loads(state_file.read_text(encoding="utf-8"))
                    self.step_count = state_data.get("step", 0)
                    status = state_data.get("status")
                    if status == "completed":
                        is_completed = True
                        break
                    elif status in ("failed", "cancelled"):
                        error_msg = f"Daemon terminated with status '{status}'"
                        break
                except Exception:
                    pass

            # Check if PID is still alive
            if pid is not None and not is_pid_alive(pid):
                # Process died; check state one last time
                if state_file.is_file():
                    try:
                        state_data = json.loads(state_file.read_text(encoding="utf-8"))
                        if state_data.get("status") == "completed":
                            is_completed = True
                            break
                    except Exception:
                        pass
                break

            time.sleep(self.poll_interval_sec)

        # Step 4: Verification gate validation
        duration = time.monotonic() - start_time
        passed, exit_code, output = self._run_gate_command(workspace_path, effective_vcmd, container=container)
        final_success = is_completed and passed

        if not final_success and not error_msg:
            error_msg = f"Verification failed (exit code {exit_code}): {output[:300]}"

        # The Rust daemon spawns the driver itself, so the harness never sees those calls.
        # Sum what the wrapper captured, plus the gate-authoring turn the adapter ran.
        input_tokens, output_tokens = self._collect_driver_telemetry(workspace_path)
        if gate_telemetry is not None:
            input_tokens += int(getattr(gate_telemetry, "input_tokens", 0) or 0)
            output_tokens += int(getattr(gate_telemetry, "output_tokens", 0) or 0)
        # Imported locally: drivers -> adapters -> superstate_daemon is already a cycle,
        # so a module-level import here breaks `python -m lab.engine.drivers.*`.
        from lab.engine.drivers.agy_cli import estimate_cost_usd

        model = getattr(driver, "model", None)
        cost_usd = estimate_cost_usd(model, input_tokens, output_tokens) if model else 0.0

        return TaskRunResult(
            task_id=task.task_id,
            harness_name=self.name,
            success=final_success,
            duration_seconds=duration,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            turns=max(1, self.step_count),
            error_message=error_msg if not final_success else None,
            provenance=self.get_provenance(),
        )

    def run_task(
        self,
        task: TaskSpec,
        workspace_path: Path,
        driver: Any = None,
        budget_sec: float = 3600.0,
        budget_hook: Optional[BudgetHook] = None,
        recorder: Any = None,
        **kwargs: Any,
    ) -> TaskRunResult:
        """Alias method to execute for cross-agent benchmark harness runner."""
        return self.execute(
            workspace_path=workspace_path,
            task=task,
            driver=driver,
            timeout_sec=budget_sec,
            budget_hook=budget_hook,
            recorder=recorder,
        )
