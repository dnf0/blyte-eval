"""Ablation and efficacy benchmark runner.

Executes evaluation arms (Vanilla, Superpowers, Superstate) against benchmark tasks
with progress-earned budget leases and strict Docker/disk resource protection.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Optional, Sequence
import uuid

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.base import AgentAdapter, AgentDriver
from lab.engine.adapters.superpowers import SuperpowersAdapter
from lab.engine.adapters.superstate import SuperstateAdapter
from lab.engine.adapters.vanilla import VanillaAdapter
from lab.engine.budget_policy import BudgetPolicy, RunTelemetry
from lab.engine.extractor import extract_and_grade
from lab.engine.governor import ConcurrencyGovernor
from lab.engine.progress_tracker import ProgressTracker
from lab.engine.trace import RunRecorder
from lab.sandbox.docker_manager import DockerManager

logger = logging.getLogger("superstate_eval.runner")

# Spec: every evaluation container is capped at 2.5 CPUs and 4 GB of memory.
DEFAULT_NANO_CPUS = int(2.5 * 1e9)
DEFAULT_MEM_LIMIT = "4g"
# Host workspace is bind-mounted here so the agent and the blind grader operate
# on the same files.
CONTAINER_WORKSPACE = "/app"


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
    ) -> None:
        self.docker_manager = docker_manager or DockerManager()
        self.governor = governor or ConcurrencyGovernor()
        self.workspace_root = workspace_root or Path("/tmp/superstate_eval_workspaces")
        self.min_free_disk_gb = min_free_disk_gb
        self.default_driver = default_driver
        self.nano_cpus = nano_cpus
        self.mem_limit = mem_limit

    def _get_adapter(self, arm: str) -> AgentAdapter:
        if arm == "vanilla":
            return VanillaAdapter()
        elif arm == "superpowers":
            return SuperpowersAdapter()
        elif arm == "superstate":
            return SuperstateAdapter()
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
        # 1. Pre-flight disk space safety check
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

                # Full live execution path with container sandbox and grading
                with self.governor.slot() as acquired:
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
                        # The agent's workspace and the blind grader's /app must be
                        # the same filesystem, or the grader scores an empty repo.
                        volumes={
                            str(workspace_dir.resolve()): {
                                "bind": CONTAINER_WORKSPACE,
                                "mode": "rw",
                            }
                        },
                        working_dir=CONTAINER_WORKSPACE,
                        network_mode=network_mode,
                        environment=active_task.env,
                        nano_cpus=nano_cpus,
                        mem_limit=mem_limit,
                    ) as container:
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
                        )

                        passed = grade_res.passed
                        cost_usd = run_result.cost_usd
                        input_tokens = run_result.input_tokens
                        output_tokens = run_result.output_tokens
                        failure_reason = grade_res.failure_reason or run_result.error_message
                        extra = {
                            "run_id": run_id,
                            "network_mode": network_mode,
                            "nano_cpus": nano_cpus,
                            "mem_limit": mem_limit,
                            "turns": run_result.turns,
                            "agent_succeeded": run_result.success,
                            "reward": grade_res.reward,
                            "patch_path": str(grade_res.patch_path)
                            if grade_res.patch_path
                            else None,
                            "logs_dir": str(logs_dir),
                            **run_result.provenance,
                        }
        except Exception as e:
            logger.exception("Error during execution of task '%s' [Arm: %s]: %s", task_id, arm, e)
            failure_reason = str(e)
            passed = False
        finally:
            wall_clock_sec = round(time.time() - start_time, 2)
            # 3. Post-task ephemeral Docker resource pruning
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
        concurrency = self.governor.calculate_max_concurrency(user_max=max_workers)
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
