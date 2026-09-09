"""Ablation and efficacy benchmark runner.

Executes evaluation arms (Vanilla, Superpowers, Superstate) against benchmark tasks
with progress-earned budget leases and strict Docker/disk resource protection.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Optional

from lab.engine.budget_policy import BudgetPolicy, RunTelemetry
from lab.engine.governor import ConcurrencyGovernor
from lab.sandbox.docker_manager import DockerManager

logger = logging.getLogger("superstate_eval.runner")


class AblationRunner:
    """Executes benchmark tasks across evaluation arms with resource and lease controls."""

    def __init__(
        self,
        docker_manager: DockerManager | None = None,
        governor: ConcurrencyGovernor | None = None,
        workspace_root: Path | None = None,
        min_free_disk_gb: float = 20.0,
    ) -> None:
        self.docker_manager = docker_manager or DockerManager()
        self.governor = governor or ConcurrencyGovernor()
        self.workspace_root = workspace_root or Path("/tmp/superstate_eval_workspaces")
        self.min_free_disk_gb = min_free_disk_gb

    def run_task(
        self,
        task_id: str,
        arm: str,
        image: str,
        base_budget_sec: float,
        lease_extension_sec: float = 1200.0,
        executor_fn: Optional[Callable[[BudgetPolicy], Dict[str, Any]]] = None,
    ) -> RunTelemetry:
        """Execute a single task under the specified arm and budget policy.

        Guarantees:
        1. Pre-flight host disk space check and opportunistic pruning.
        2. Universal progress-earned lease extensions tracked via BudgetPolicy across all arms.
        3. Deterministic teardown of containers and temporary volumes.
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

        try:
            logger.info(f"Starting task '{task_id}' [Arm: {arm}] (Base budget: {base_budget_sec}s)")
            if executor_fn is not None:
                result = executor_fn(budget_policy)
                passed = bool(result.get("passed", False))
                cost_usd = float(result.get("cost_usd", 0.0))
                input_tokens = int(result.get("input_tokens", 0))
                output_tokens = int(result.get("output_tokens", 0))
                failure_reason = result.get("failure_reason")
        except Exception as e:
            logger.exception(f"Error during execution of task '{task_id}' [Arm: {arm}]: {e}")
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
        )

        logger.info(
            f"Finished task '{task_id}' [Arm: {arm}]: Passed={passed}, "
            f"WallClock={wall_clock_sec}s, Cost=${cost_usd:.2f}, "
            f"TotalGrantedBudget={telemetry.total_granted_budget_sec}s"
        )
        return telemetry

    def run_cohort(
        self,
        tasks: List[Dict[str, Any]],
        arms: List[str],
        max_workers: int | None = None,
        lease_extension_sec: float = 1200.0,
        executor_fn: Optional[Callable[[BudgetPolicy], Dict[str, Any]]] = None,
    ) -> List[RunTelemetry]:
        """Execute a matrix of tasks x arms concurrently using the dynamic governor."""
        concurrency = self.governor.calculate_max_concurrency(user_max=max_workers)
        logger.info(
            f"Dispatching cohort: {len(tasks)} tasks across {len(arms)} arms "
            f"({len(tasks) * len(arms)} total runs) with concurrency={concurrency}"
        )

        futures_map = {}
        results: List[RunTelemetry] = []

        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            for task_spec in tasks:
                task_id = task_spec["task_id"]
                image = task_spec.get("image", "ubuntu:latest")
                base_budget = task_spec.get("base_budget_sec", 1800.0)

                for arm in arms:
                    future = pool.submit(
                        self.run_task,
                        task_id=task_id,
                        arm=arm,
                        image=image,
                        base_budget_sec=base_budget,
                        lease_extension_sec=lease_extension_sec,
                        executor_fn=executor_fn,
                    )
                    futures_map[future] = (task_id, arm)

            for future in as_completed(futures_map):
                t_id, a_name = futures_map[future]
                try:
                    res = future.result()
                    results.append(res)
                except Exception as err:
                    logger.error(f"Task {t_id} under arm {a_name} failed catastrophically: {err}")
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
