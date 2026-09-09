"""Tests for AblationRunner telemetry and metrics integration.

Validates that held-out verifier statistics (F2P, P2P counts and overall pass fractions)
are faithfully extracted, computed, and attached to RunTelemetry extra metadata.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.base import AgentDriver, DriverTelemetry
from lab.engine.extractor import EvaluationResult
from lab.engine.runner import AblationRunner


class StubDriver(AgentDriver):
    """Stub driver providing dummy execution telemetry for runner tests."""

    def run(
        self,
        task: TaskSpec,
        workspace_path: Path,
        prompt_override: str | None = None,
        conversation_id: str | None = None,
        timeout_sec: float = 3600.0,
        container: Any = None,
    ) -> DriverTelemetry:
        """Simulate agent execution by writing a stub solution file.

        Parameters:
            task: Task specification under evaluation.
            workspace_path: Working directory for task execution.
            prompt_override: Optional system prompt override.
            conversation_id: Optional conversation ID for multi-turn sessions.
            timeout_sec: Execution time limit in seconds.
            container: Optional Docker container sandbox.

        Returns:
            DriverTelemetry recording successful agent turn execution.
        """
        # Populate workspace with dummy solution file to simulate agent output
        (workspace_path / "solution.py").write_text("# solution\n")
        return DriverTelemetry(
            success=True,
            raw_response="Task complete.",
            duration_seconds=1.0,
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.02,
        )


def _setup_runner(tmp_path: Path) -> AblationRunner:
    """Instantiate an AblationRunner configured with mocked docker and governor.

    Parameters:
        tmp_path: Pytest temporary directory for workspace roots.

    Returns:
        Configured AblationRunner instance with StubDriver.
    """
    mock_docker_mgr = MagicMock()
    mock_container = MagicMock()
    mock_docker_mgr.run_sandbox.return_value.__enter__.return_value = mock_container
    mock_docker_mgr.run_sandbox.return_value.__exit__.return_value = None

    governor = MagicMock()
    governor.slot.return_value.__enter__.return_value = True
    governor.slot.return_value.__exit__.return_value = None

    return AblationRunner(
        docker_manager=mock_docker_mgr,
        governor=governor,
        workspace_root=tmp_path / "workspaces",
        default_driver=StubDriver(),
    )


def test_pass_fraction_metrics_populated_from_verifier_stats(tmp_path: Path) -> None:
    """Verify that granular verifier statistics populate test metrics in telemetry extra.

    Parameters:
        tmp_path: Pytest temporary directory fixture.
    """
    runner = _setup_runner(tmp_path)
    stats: dict[str, Any] = {
        "f2p_total": 4,
        "f2p_passed": 3,
        "p2p_total": 6,
        "p2p_passed": 6,
    }
    mock_grade_result = EvaluationResult(
        task_id="test/sample-task",
        arm="vanilla",
        passed=True,
        reward=0.9,
        exit_code=0,
        patch_path=Path("/tmp/patch"),
        state_json_path=None,
        stats=stats,
    )

    # Patch extract_and_grade to return our controlled EvaluationResult with stats
    with patch("lab.engine.runner.extract_and_grade", return_value=mock_grade_result):
        telemetry = runner.run_task(
            task_id="test/sample-task",
            arm="vanilla",
            image="test:latest",
            base_budget_sec=600.0,
        )

    # Validate that runner telemetry records exact test metrics from compute_test_metrics
    assert telemetry.extra["test_stats"] == stats
    assert telemetry.extra["test_pass_fraction"] == pytest.approx(0.9)
    assert telemetry.extra["f2p_fraction"] == pytest.approx(0.75)
    assert telemetry.extra["p2p_fraction"] == pytest.approx(1.0)
    assert telemetry.extra["tests_passed"] == 9
    assert telemetry.extra["tests_total"] == 10


def test_pass_fraction_fallback_when_stats_are_none_passed(tmp_path: Path) -> None:
    """Verify fallback to 1.0 pass fraction when verifier stats are None and task passed.

    Parameters:
        tmp_path: Pytest temporary directory fixture.
    """
    runner = _setup_runner(tmp_path)
    mock_grade_result = EvaluationResult(
        task_id="test/sample-task",
        arm="vanilla",
        passed=True,
        reward=1.0,
        exit_code=0,
        patch_path=Path("/tmp/patch"),
        state_json_path=None,
        stats=None,
    )

    # Patch extract_and_grade to simulate verifier without granular test metrics
    with patch("lab.engine.runner.extract_and_grade", return_value=mock_grade_result):
        telemetry = runner.run_task(
            task_id="test/sample-task",
            arm="vanilla",
            image="test:latest",
            base_budget_sec=600.0,
        )

    # Validate default pass fraction of 1.0 when evaluation strictly passed
    assert telemetry.extra["test_stats"] is None
    assert telemetry.extra["test_pass_fraction"] == 1.0
    assert telemetry.extra["f2p_fraction"] is None
    assert telemetry.extra["p2p_fraction"] is None
    assert telemetry.extra["tests_passed"] is None
    assert telemetry.extra["tests_total"] is None


def test_pass_fraction_fallback_when_stats_are_none_failed(tmp_path: Path) -> None:
    """Verify fallback to 0.0 pass fraction when verifier stats are None and task failed.

    Parameters:
        tmp_path: Pytest temporary directory fixture.
    """
    runner = _setup_runner(tmp_path)
    mock_grade_result = EvaluationResult(
        task_id="test/sample-task",
        arm="vanilla",
        passed=False,
        reward=0.0,
        exit_code=1,
        patch_path=None,
        state_json_path=None,
        failure_reason="Verifier test assertion failed",
        stats=None,
    )

    # Patch extract_and_grade to simulate failed run without granular stats
    with patch("lab.engine.runner.extract_and_grade", return_value=mock_grade_result):
        telemetry = runner.run_task(
            task_id="test/sample-task",
            arm="vanilla",
            image="test:latest",
            base_budget_sec=600.0,
        )

    # Validate default pass fraction of 0.0 when evaluation failed
    assert telemetry.extra["test_stats"] is None
    assert telemetry.extra["test_pass_fraction"] == 0.0
    assert telemetry.extra["f2p_fraction"] is None
    assert telemetry.extra["p2p_fraction"] is None
    assert telemetry.extra["tests_passed"] is None
    assert telemetry.extra["tests_total"] is None
