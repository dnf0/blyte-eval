"""Ablation and efficacy benchmark runner.

Executes evaluation arms (Vanilla, Superpowers, Superstate) against benchmark tasks
with progress-earned budget leases and strict Docker/disk resource protection.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import threading
from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Optional, Sequence
import uuid

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters import (
    AgentAdapter,
    AgentDriver,
    SuperpowersAdapter,
    SuperstateAdapter,
    SuperstateAgentMcpAdapter,
    SuperstateDaemonAdapter,
    SuperstateMcpAdapter,
    SuperstateRelayAdapter,
    VanillaAdapter,
)
from lab.engine.adapters.superstate import ENGINE_PYTHON, ENGINE_RUST
from lab.engine.budget_policy import BudgetPolicy, RunTelemetry
from lab.engine.extractor import compute_test_metrics, extract_and_grade
from lab.engine.governor import ConcurrencyGovernor
from lab.engine.progress_tracker import ProgressTracker
from lab.engine.trace import RunRecorder
from lab.engine.verifier import HeldOutVerifier
from lab.sandbox.answer_key import AnswerKeyGuard
from lab.sandbox.docker_manager import DockerManager

logger = logging.getLogger("superstate_eval.runner")

# Spec: every evaluation container is capped at 2.5 CPUs and 4 GB of memory.
DEFAULT_NANO_CPUS = int(2.5 * 1e9)
DEFAULT_MEM_LIMIT = "4g"
# Host workspace is bind-mounted at CONTAINER_MOUNT_ROOT. CONTAINER_WORKSPACE (/app)
# is dynamically symlinked to the active workspace (or worktree) so that agent commands
# and the blind grader seamlessly operate on the active files without mount impedance.
CONTAINER_WORKSPACE = "/app"
CONTAINER_MOUNT_ROOT = "/workspace_root"


def resolve_network_mode(declared: str | None) -> str | None:
    """Translate a task's declared network policy into a docker network_mode.

    A task that declares "no-network" must not be handed an agent with internet
    access: the upstream fix for the very bug under test is usually one fetch away.
    """
    if declared is None:
        return None
    normalized = declared.strip().lower()
    if normalized in {"no-network", "none", "disabled", "off"}:
        return "none"
    if normalized in {"host", "bridge", "default"}:
        return None if normalized == "default" else normalized
    return declared


class NoDriverConfiguredError(RuntimeError):
    """Raised when a live evaluation is requested without an agent driver."""


class InsufficientResourcesError(RuntimeError):
    """Raised when the host cannot safely run even a single concurrent evaluation."""


class AblationRunner:
    """Executes benchmark tasks across evaluation arms with resource and lease controls."""

    def __init__(
        self,
        docker_manager: DockerManager | None = None,
        governor: ConcurrencyGovernor | None = None,
        workspace_root: Path | None = None,
        min_free_disk_gb: float = 20.0,
        default_driver: Optional[AgentDriver] = None,
        nano_cpus: int = DEFAULT_NANO_CPUS,
        mem_limit: str = DEFAULT_MEM_LIMIT,
        verifier: Optional[HeldOutVerifier] = None,
    ) -> None:
        self.docker_manager = docker_manager or DockerManager()
        self.governor = governor or ConcurrencyGovernor()
        self.workspace_root = workspace_root or Path("/tmp/superstate_eval_workspaces")
        self.min_free_disk_gb = min_free_disk_gb
        self.default_driver = default_driver
        self.nano_cpus = nano_cpus
        self.mem_limit = mem_limit
        self.verifier = verifier or HeldOutVerifier(docker_manager=self.docker_manager)
        self.answer_key_guard = AnswerKeyGuard()
        # Docker maintenance is shared state. Pruning while sibling runs hold
        # containers can tear down resources they are still using, so it is
        # deferred until no run is in flight.
        self._active_runs = 0
        self._active_lock = threading.Lock()

    def _get_adapter(self, arm: str) -> AgentAdapter:
        if arm == "vanilla":
            return VanillaAdapter()
        elif arm == "superpowers":
            return SuperpowersAdapter()
        elif arm in ("superstate", "superstate_python", "superstate-python"):
            return SuperstateAdapter(engine=ENGINE_PYTHON)
        elif arm in ("superstate_rust", "superstate-rust", "rust", "arm_d", "arm-d"):
            return SuperstateAdapter(engine=ENGINE_RUST, zero_turn_planning=True)
        elif arm in ("superstate_rust_planned", "superstate_rust_2phase"):
            return SuperstateAdapter(
                engine=ENGINE_RUST, zero_turn_planning=False, name="superstate_rust_planned"
            )
        # These names are ALIASES of one configuration, not distinct conditions. Benchmarking
        # two of them against each other compares a config with itself. `superstate_solo` is
        # included here: it is the interactive turn-based baseline (Python turn loop driving
        # the superstate CLI directly -- no gateway, no daemon), which is exactly this config.
        elif arm in (
            "superstate_rust_inplace", "superstate-rust-inplace", "rust_inplace",
            "arm_d_inplace", "arm-d-inplace",
            "superstate_rust_fast", "superstate-rust-fast", "rust_fast",
            "superstate_fast", "superstate_rust_direct",
            "superstate_solo", "superstate-solo", "solo",
        ):
            return SuperstateAdapter(engine=ENGINE_RUST, no_worktree=True, zero_turn_planning=True)
        elif arm in ("superstate_mcp", "superstate-mcp", "superstate_rust_mcp", "superstate-rust-mcp", "mcp"):
            return SuperstateMcpAdapter(no_worktree=True, zero_turn_planning=True)
        elif arm in ("superstate_mcp_worktree", "superstate-mcp-worktree", "mcp_worktree"):
            return SuperstateMcpAdapter(no_worktree=False, worktree=True, zero_turn_planning=True)
        elif arm in ("superstate_mcp_planned", "superstate-mcp-planned"):
            # The name MUST differ from superstate_mcp: TaskRunResult.harness_name is what
            # lands in the results JSON, so sharing a name would pool a multi-milestone arm
            # with a single-milestone one and make the comparison invisible.
            return SuperstateMcpAdapter(
                no_worktree=True, zero_turn_planning=False, name="superstate_mcp_planned"
            )
        elif arm in ("superstate_agent_mcp", "superstate-agent-mcp", "agent_mcp", "agent-mcp"):
            return SuperstateAgentMcpAdapter()
        elif arm in ("superstate_agent_mcp_worktree", "superstate-agent-mcp-worktree", "agent_mcp_worktree"):
            return SuperstateAgentMcpAdapter(worktree=True)
        elif arm in ("superstate_agent_mcp_inplace", "superstate-agent-mcp-inplace", "agent_mcp_inplace"):
            return SuperstateAgentMcpAdapter(no_worktree=True)
        # Cross-agent relay: chat-driven handoff between agents, Python-supervised.
        elif arm in ("superstate_relay", "superstate-relay", "relay"):
            return SuperstateRelayAdapter()
        # Detached Autonomous Daemon: hands off task execution entirely to native Rust DaemonRunner
        elif arm in ("superstate_daemon", "superstate-daemon", "daemon"):
            return SuperstateDaemonAdapter()
        elif arm in ("superstate_daemon_review", "superstate-daemon-review", "daemon_review"):
            return SuperstateDaemonAdapter(
                advisory_review=True, auto_rollback=False, name="superstate_daemon_review"
            )
        elif arm in (
            "superstate_daemon_rollback",
            "superstate-daemon-rollback",
            "daemon_rollback",
            "superstate_daemon_full",
            "superstate-daemon-full",
            "daemon_full",
        ):
            arm_name = "superstate_daemon_full" if "full" in arm else "superstate_daemon_rollback"
            return SuperstateDaemonAdapter(
                advisory_review=True, auto_rollback=True, name=arm_name
            )
        elif arm in (
            "superstate_daemon_dag",
            "superstate-daemon-dag",
            "daemon_dag",
        ):
            return SuperstateDaemonAdapter(
                advisory_review=True, auto_rollback=True, tdd_dag=True, name="superstate_daemon_dag"
            )
        raise ValueError(f"Unknown evaluation arm: {arm}")

    def run_task(
        self,
        task_id: str,
        arm: str,
        image: str,
        base_budget_sec: float,
        lease_extension_sec: float = 1200.0,
        executor_fn: Optional[Callable[[BudgetPolicy], Dict[str, Any]]] = None,
        task_spec: Optional[TaskSpec] = None,
        driver: Optional[AgentDriver] = None,
    ) -> RunTelemetry:
        """Execute a single task under the specified arm and budget policy.

        Guarantees:
        1. Pre-flight host disk space check and opportunistic pruning.
        2. Universal progress-earned lease extensions tracked via BudgetPolicy across all arms.
        3. Deterministic teardown of containers and temporary volumes.

        The live path requires an explicit `driver` (or a `default_driver` on the
        runner): there is deliberately no mock fallback, so a misconfigured run
        fails loudly instead of reporting fabricated telemetry.
        """
        # 1. Pre-flight disk space safety check. Only the first run in flight may
        #    prune: the disk check removes stopped containers and unused volumes,
        #    which is unsafe to do underneath a sibling run.
        with self._active_lock:
            first_in_flight = self._active_runs == 0
            self._active_runs += 1
        if first_in_flight:
            self.docker_manager.check_disk_space_or_prune(min_free_gb=self.min_free_disk_gb)

        # 2. Configure budget policy: universal progress extensions enabled for all arms
        budget_policy = BudgetPolicy(
            base_timeout_sec=base_budget_sec,
            lease_extension_sec=lease_extension_sec,
        )

        start_time = time.time()
        passed = False
        cost_usd = 0.0
        input_tokens = 0
        output_tokens = 0
        failure_reason = None
        extra: Dict[str, Any] = {}
        recorder: Optional[RunRecorder] = None

        try:
            logger.info(
                "Starting task '%s' [Arm: %s] (Base budget: %.1fs)", task_id, arm, base_budget_sec
            )
            if executor_fn is not None:
                result = executor_fn(budget_policy)
                passed = bool(result.get("passed", False))
                cost_usd = float(result.get("cost_usd", 0.0))
                input_tokens = int(result.get("input_tokens", 0))
                output_tokens = int(result.get("output_tokens", 0))
                failure_reason = result.get("failure_reason")
            else:
                active_driver = driver or self.default_driver
                if active_driver is None:
                    raise NoDriverConfiguredError(
                        f"No agent driver configured for task '{task_id}' [Arm: {arm}]. "
                        "Pass driver= or default_driver=; the live path has no mock fallback."
                    )

                # Size the slot by what this container will actually reserve, capped
                # at a reasonable worker slice so multiple sandboxes can run concurrently.
                task_ram_gb = (
                    min(task_spec.memory_mb / 1024, 4.0)
                    if task_spec is not None and task_spec.memory_mb
                    else None
                )

                # Full live execution path with container sandbox and grading
                with self.governor.slot(ram_gb_per_worker=task_ram_gb) as acquired:
                    if not acquired:
                        raise RuntimeError(
                            "Failed to acquire concurrency governor slot within timeout"
                        )

                    adapter = self._get_adapter(arm)
                    run_id = f"eval-{task_id.replace('/', '_')}-{arm}-{uuid.uuid4().hex[:8]}"
                    task_run_root = self.workspace_root / run_id
                    logs_dir = task_run_root / "logs"
                    workspace_dir = task_run_root / "workspace"
                    logs_dir.mkdir(parents=True, exist_ok=True)
                    workspace_dir.mkdir(parents=True, exist_ok=True)

                    active_task = task_spec or TaskSpec(
                        id=task_id,
                        name=task_id.split("/")[-1],
                        instruction=f"Solve benchmark task {task_id}",
                        docker_image=image,
                        timeout_sec=base_budget_sec,
                    )

                    # The task's own image is authoritative when a spec is supplied.
                    run_image = active_task.docker_image or image or "alpine:latest"

                    # A bind mount shadows the image's /app, so the task repository
                    # must be copied onto the host before the mount exists.
                    self.docker_manager.seed_workspace_from_image(
                        image=run_image,
                        dest=workspace_dir,
                        source_path=CONTAINER_WORKSPACE,
                    )

                    # Honour the task's declared sandbox contract over harness defaults.
                    nano_cpus = (
                        int(active_task.cpus * 1e9) if active_task.cpus else self.nano_cpus
                    )
                    mem_limit = (
                        f"{active_task.memory_mb}m" if active_task.memory_mb else self.mem_limit
                    )
                    network_mode = resolve_network_mode(active_task.agent_network_mode)

                    with self.docker_manager.run_sandbox(
                        image=run_image,
                        logs_dir=logs_dir,
                        container_name=run_id,
                        # The host workspace is mounted at CONTAINER_MOUNT_ROOT, and CONTAINER_WORKSPACE
                        # (/app) is symlinked to it. This allows active worktrees (.wt/task-N)
                        # to be dynamically symlinked to /app during isolation turns.
                        volumes={
                            str(workspace_dir.resolve()): {
                                "bind": CONTAINER_MOUNT_ROOT,
                                "mode": "rw",
                            }
                        },
                        working_dir=CONTAINER_MOUNT_ROOT,
                        network_mode=network_mode,
                        environment=active_task.env,
                        nano_cpus=nano_cpus,
                        mem_limit=mem_limit,
                    ) as container:
                        # Initialize /app as a dynamic symlink to /workspace_root
                        container.exec_run(
                            [
                                "sh",
                                "-c",
                                f"rm -rf {CONTAINER_WORKSPACE} && ln -s {CONTAINER_MOUNT_ROOT} {CONTAINER_WORKSPACE}",
                            ],
                            workdir="/",
                        )
                        recorder = RunRecorder(
                            logs_dir=logs_dir, task_id=task_id, arm=arm
                        )
                        tracker = ProgressTracker(
                            policy=budget_policy,
                            workspace_path=workspace_dir,
                            arm=arm,
                        )

                        def budget_hook() -> float:
                            """Poll for verifiable progress and report the granted budget."""
                            tracker.poll_for_progress()
                            return budget_policy.current_granted_budget_sec

                        # A host-side agent runs as this user and could read the
                        # task's tests/ directory. Seal it while the agent works.
                        # An in-container agent cannot reach the path at all, so
                        # there is nothing to seal.
                        isolated = bool(
                            getattr(active_driver, "provides_isolated_execution", False)
                        )
                        seal_paths = (
                            []
                            if isolated or active_task.tests_dir is None
                            else [active_task.tests_dir]
                        )

                        with self.answer_key_guard.sealed(seal_paths) as sealed_paths:
                            run_result = adapter.execute(
                                workspace_dir,
                                active_task,
                                active_driver,
                                timeout_sec=budget_policy.current_granted_budget_sec,
                                container=container,
                                budget_hook=budget_hook,
                                recorder=recorder,
                            )

                        grade_res = extract_and_grade(
                            container=container,
                            task=active_task,
                            arm=arm,
                            logs_dir=logs_dir,
                            workspace_path=workspace_dir,
                            recorder=recorder,
                            verifier=self.verifier,
                        )

                        # Compute granular test metrics and pass fraction from verifier stats
                        test_metrics = compute_test_metrics(grade_res.stats, grade_res.passed)

                        passed = grade_res.passed
                        cost_usd = run_result.cost_usd
                        input_tokens = run_result.input_tokens
                        output_tokens = run_result.output_tokens
                        # Cause before symptom. When the agent itself failed -- timed
                        # out, crashed, exhausted its turns -- a low reward is the
                        # consequence, not the diagnosis. Reporting the grading message
                        # first made every agent-side failure look like a bad patch.
                        if run_result.error_message:
                            failure_reason = f"Agent run failed: {run_result.error_message}"
                            if grade_res.failure_reason:
                                failure_reason += f" | grading then reported: {grade_res.failure_reason}"
                        else:
                            failure_reason = grade_res.failure_reason
                        extra = {
                            "run_id": run_id,
                            # The two factors of the design: which execution plane
                            # (harness) and which layer (arm) produced this result.
                            "harness": getattr(active_driver, "harness_name", "unknown"),
                            "model": getattr(active_driver, "harness_model", None),
                            "network_mode": network_mode,
                            "nano_cpus": nano_cpus,
                            "mem_limit": mem_limit,
                            "turns": run_result.turns,
                            "agent_succeeded": run_result.success,
                            "reward": grade_res.reward,
                            "test_stats": grade_res.stats,
                            **test_metrics,
                            "patch_path": str(grade_res.patch_path)
                            if grade_res.patch_path
                            else None,
                            "logs_dir": str(logs_dir),
                            "held_out_verifier": active_task.tests_dir is not None,
                            # Whether the agent's command execution was actually
                            # confined to the sandbox. A False here means the agent
                            # had a host shell and could read the held-out tests, so
                            # the result carries a weaker guarantee than an isolated
                            # run and must not be compared with one unqualified.
                            "isolated_execution": isolated,
                            # Held-out tests made unreadable while the agent worked.
                            "answer_key_sealed": [str(p) for p in sealed_paths],
                            **run_result.provenance,
                        }
        except Exception as e:
            logger.exception("Error during execution of task '%s' [Arm: %s]: %s", task_id, arm, e)
            failure_reason = str(e)
            passed = False
        finally:
            wall_clock_sec = round(time.time() - start_time, 2)
            # 3. Prune only once the last concurrent run has finished. Pruning
            #    after every run reclaimed disk underneath siblings that were
            #    still using it.
            with self._active_lock:
                self._active_runs -= 1
                last_out = self._active_runs == 0
            if last_out:
                self.docker_manager.prune_ephemeral_resources()

        telemetry = RunTelemetry(
            task_id=task_id,
            arm=arm,
            passed=passed,
            wall_clock_sec=wall_clock_sec,
            cost_usd=cost_usd,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            milestones_completed=budget_policy.milestones_completed,
            lease_extensions_earned_sec=budget_policy.lease_extensions_earned_sec,
            total_granted_budget_sec=budget_policy.current_granted_budget_sec,
            failure_reason=failure_reason,
            extra=extra,
        )

        if recorder is not None:
            recorder.write_run_record(
                telemetry,
                image=extra.get("image"),
                sandbox={
                    "network_mode": extra.get("network_mode"),
                    "nano_cpus": extra.get("nano_cpus"),
                    "mem_limit": extra.get("mem_limit"),
                },
            )

        logger.info(
            "Finished task '%s' [Arm: %s]: Passed=%s, WallClock=%.2fs, Cost=$%.2f, "
            "TotalGrantedBudget=%.1fs",
            task_id,
            arm,
            passed,
            wall_clock_sec,
            cost_usd,
            telemetry.total_granted_budget_sec,
        )
        return telemetry

    @staticmethod
    def _normalize_task(entry: TaskSpec | Dict[str, Any]) -> tuple[str, str, float, Optional[TaskSpec]]:
        """Resolve a cohort entry into (task_id, image, base_budget_sec, task_spec)."""
        if isinstance(entry, TaskSpec):
            budget = entry.agent_timeout_sec or entry.timeout_sec
            return entry.id, entry.docker_image, float(budget), entry

        spec = entry.get("task_spec")
        if isinstance(spec, TaskSpec):
            budget = entry.get("base_budget_sec") or spec.agent_timeout_sec or spec.timeout_sec
            return spec.id, spec.docker_image or entry.get("image", ""), float(budget), spec

        return (
            entry["task_id"],
            entry.get("image", "ubuntu:latest"),
            float(entry.get("base_budget_sec", 1800.0)),
            None,
        )

    def run_cohort(
        self,
        tasks: Sequence[TaskSpec | Dict[str, Any]],
        arms: List[str],
        max_workers: int | None = None,
        lease_extension_sec: float = 1200.0,
        executor_fn: Optional[Callable[[BudgetPolicy], Dict[str, Any]]] = None,
        driver: Optional[AgentDriver] = None,
    ) -> List[RunTelemetry]:
        """Execute a matrix of tasks x arms concurrently using the dynamic governor."""
        # Concurrency must be sized on the largest container the cohort will start.
        # Tasks commonly declare 8 GB; sizing on the 4 GB default would overcommit
        # the host two-to-one and put every timing measurement into swap.
        declared_ram_gb = [
            spec.memory_mb / 1024
            for spec in (self._normalize_task(entry)[3] for entry in tasks)
            if spec is not None and spec.memory_mb
        ]
        cohort_ram_gb = max(declared_ram_gb) if declared_ram_gb else None
        concurrency = self.governor.calculate_max_concurrency(
            user_max=max_workers, ram_gb_per_worker=cohort_ram_gb
        )
        if concurrency < 1:
            raise InsufficientResourcesError(
                "Host resources are below the safety margins required to run a single "
                "evaluation (concurrency=0). Free disk/RAM or lower the governor thresholds."
            )

        logger.info(
            "Dispatching cohort: %d tasks across %d arms (%d total runs) with concurrency=%d",
            len(tasks),
            len(arms),
            len(tasks) * len(arms),
            concurrency,
        )

        futures_map = {}
        results: List[RunTelemetry] = []

        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            for entry in tasks:
                task_id, image, base_budget, spec = self._normalize_task(entry)

                for arm in arms:
                    future = pool.submit(
                        self.run_task,
                        task_id=task_id,
                        arm=arm,
                        image=image,
                        base_budget_sec=base_budget,
                        lease_extension_sec=lease_extension_sec,
                        executor_fn=executor_fn,
                        task_spec=spec,
                        driver=driver,
                    )
                    futures_map[future] = (task_id, arm)

            for future in as_completed(futures_map):
                t_id, a_name = futures_map[future]
                try:
                    res = future.result()
                    results.append(res)
                except Exception as err:
                    logger.error(
                        "Task %s under arm %s failed catastrophically: %s", t_id, a_name, err
                    )
                    results.append(
                        RunTelemetry(
                            task_id=t_id,
                            arm=a_name,
                            passed=False,
                            wall_clock_sec=0.0,
                            cost_usd=0.0,
                            input_tokens=0,
                            output_tokens=0,
                            failure_reason=str(err),
                        )
                    )

        return results
