"""Pilot showdown runner executing end-to-end task runs across Vanilla and Superpowers."""

from __future__ import annotations

from contextlib import contextmanager
import logging
from pathlib import Path
import time
from typing import Any, Generator, Optional
import uuid

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.base import AgentAdapter, AgentDriver, DriverTelemetry
from lab.engine.adapters.superpowers import SuperpowersAdapter
from lab.engine.adapters.vanilla import VanillaAdapter
from lab.engine.extractor import extract_and_grade
from lab.sandbox.docker_manager import DockerManager

logger = logging.getLogger("superstate_eval.pilot")


class PilotMockDriver(AgentDriver):
    """Predictable mock driver simulating agent behavior for pilot verification."""

    def __init__(self, arm: str) -> None:
        self.arm = arm
        self.turn = 0

    def run(
        self,
        task: TaskSpec,
        workspace_path: Path,
        prompt_override: Optional[str] = None,
        conversation_id: Optional[str] = None,
        timeout_sec: float = 3600.0,
        container: Any = None,
    ) -> DriverTelemetry:
        self.turn += 1
        # Create simulated patch file in the workspace
        mod_file = workspace_path / "solution.py"
        mod_file.write_text(
            f"# Solution for {task.id} by {self.arm} (turn {self.turn})\n", encoding="utf-8"
        )

        if self.arm == "superpowers" and self.turn == 1:
            # Superpowers asks for approval on Turn 1
            return DriverTelemetry(
                success=True,
                raw_response="Should I proceed with Option 1?",
                duration_seconds=2.5,
                input_tokens=150,
                output_tokens=30,
                cost_usd=0.001,
                conversation_id="conv-pilot-sp",
            )

        return DriverTelemetry(
            success=True,
            raw_response=f"Completed {task.name} under {self.arm}.",
            duration_seconds=3.0,
            input_tokens=250,
            output_tokens=60,
            cost_usd=0.002,
            conversation_id=conversation_id or f"conv-pilot-{self.arm}",
        )


class MockContainer:
    """Mock container for testing evaluation extractors without live Docker."""

    def __init__(self, logs_dir: Optional[Path] = None, arm: str = "vanilla") -> None:
        self.logs_dir = logs_dir
        self.arm = arm

    def exec_run(self, cmd: str, workdir: Optional[str] = None, **kwargs: Any) -> tuple[int, bytes]:
        if self.logs_dir is not None:
            # Simulate container-side verifier generating reward
            vdir = self.logs_dir / "verifier"
            vdir.mkdir(parents=True, exist_ok=True)
            (vdir / "reward.json").write_text('{"reward": 1.0, "exit_code": 0}', encoding="utf-8")
            adir = self.logs_dir / "artifacts"
            adir.mkdir(parents=True, exist_ok=True)
            (adir / "model.patch").write_text(f"# Patch by {self.arm}\n", encoding="utf-8")
        return (0, b"Verification passed\n")


class PilotShowdownRunner:
    """Executes a single benchmark task across evaluation arms with isolated containers and blind verification."""

    def __init__(
        self,
        docker_manager: Optional[DockerManager] = None,
        logs_root: Optional[Path] = None,
    ) -> None:
        self.docker_manager = docker_manager or DockerManager()
        self.logs_root = logs_root or Path("/tmp/superstate_pilot_logs")
        self.logs_root.mkdir(parents=True, exist_ok=True)

    def _get_adapter(self, arm: str) -> AgentAdapter:
        if arm == "vanilla":
            return VanillaAdapter()
        elif arm == "superpowers":
            return SuperpowersAdapter()
        raise ValueError(f"Unknown evaluation arm: {arm}")

    @contextmanager
    def _acquire_container(
        self,
        task: TaskSpec,
        arm: str,
        run_id: str,
        logs_dir: Path,
        mock_mode: bool,
    ) -> Generator[Any, None, None]:
        if mock_mode:
            yield MockContainer(logs_dir=logs_dir, arm=arm)
        else:
            with self.docker_manager.run_sandbox(
                image=task.docker_image or "alpine:latest",
                logs_dir=logs_dir,
                container_name=run_id,
                mem_limit="4g",
            ) as container:
                yield container

    def run_pilot(
        self,
        task: TaskSpec,
        arms: Optional[list[str]] = None,
        mock_mode: bool = True,
        driver: Optional[AgentDriver] = None,
    ) -> dict[str, Any]:
        """Execute task across arms and return structured benchmark outcomes.

        With `mock_mode=True` (the default) the sandbox is a `MockContainer` whose
        verifier always reports success. Such a summary exercises the pipeline; it
        is not a measurement, and every record is tagged `mock_mode: True`.
        """
        if mock_mode:
            logger.warning(
                "run_pilot called with mock_mode=True: verification outcomes are simulated "
                "and must not be reported as evaluation results."
            )
        selected_arms = arms or ["vanilla", "superpowers"]
        summary: dict[str, Any] = {
            "task_id": task.id,
            "image": task.docker_image,
            "base_commit": task.base_commit,
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "mock_mode": mock_mode,
            "results": [],
        }

        for arm in selected_arms:
            run_id = f"pilot-{task.name}-{arm}-{uuid.uuid4().hex[:8]}"
            logs_dir = self.logs_root / run_id
            logs_dir.mkdir(parents=True, exist_ok=True)

            logger.info("Executing pilot run %s [Arm: %s]", run_id, arm)
            adapter = self._get_adapter(arm)
            active_driver = driver or PilotMockDriver(arm=arm)

            with self._acquire_container(task, arm, run_id, logs_dir, mock_mode) as container:
                workspace = logs_dir / "workspace"
                workspace.mkdir(parents=True, exist_ok=True)
                run_result = adapter.execute(
                    workspace, task, active_driver, container=container
                )

                # Blind extraction and grading from the container
                grade_res = extract_and_grade(
                    container=container,
                    task=task,
                    arm=arm,
                    logs_dir=logs_dir,
                    workspace_path=workspace,
                )

                arm_summary = {
                    "arm": arm,
                    "run_id": run_id,
                    "mock_mode": mock_mode,
                    "success": run_result.success,
                    "passed": grade_res.passed,
                    "reward": grade_res.reward,
                    "exit_code": grade_res.exit_code,
                    "turns": run_result.turns,
                    "duration_sec": run_result.duration_seconds,
                    "duration_seconds": run_result.duration_seconds,
                    "cost_usd": run_result.cost_usd,
                    "input_tokens": run_result.input_tokens,
                    "output_tokens": run_result.output_tokens,
                    "patch_path": str(grade_res.patch_path) if grade_res.patch_path else None,
                    "state_json_path": str(grade_res.state_json_path)
                    if grade_res.state_json_path
                    else None,
                    "failure_reason": grade_res.failure_reason,
                    "error_message": run_result.error_message,
                    "provenance": run_result.provenance,
                }
                summary["results"].append(arm_summary)

        return summary
