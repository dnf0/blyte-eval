"""Tests for AblationRunner telemetry and metrics integration.

Validates that held-out verifier statistics (F2P, P2P counts and overall pass fractions)
are faithfully extracted, computed, and attached to RunTelemetry extra metadata.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast
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


def test_run_telemetry_records_whether_execution_was_isolated(tmp_path) -> None:
    """A result from a driver with a host shell carries a weaker guarantee.

    It must not sit in a report next to an isolated run without saying so.
    """
    from contextlib import contextmanager
    from unittest.mock import MagicMock

    from lab.benchmarks.task_loader import TaskSpec
    from lab.engine.adapters.base import AgentDriver, DriverTelemetry
    from lab.engine.runner import AblationRunner

    class HostShellDriver(AgentDriver):
        provides_isolated_execution = False

        def run(self, task, workspace_path, prompt_override=None, conversation_id=None,
                timeout_sec=3600.0, container=None) -> DriverTelemetry:
            return DriverTelemetry(success=True, raw_response="done", duration_seconds=1.0)

    mock_docker = MagicMock()
    mock_container = MagicMock()

    @contextmanager
    def fake_sandbox(image, logs_dir, container_name, **kwargs):
        vdir = logs_dir / "verifier"
        vdir.mkdir(parents=True, exist_ok=True)
        (vdir / "reward.json").write_text('{"reward": 1.0}')
        mock_container.exec_run.return_value = (0, b"ok")
        yield mock_container

    mock_docker.run_sandbox.side_effect = fake_sandbox

    runner = AblationRunner(
        docker_manager=mock_docker,
        workspace_root=tmp_path / "ws",
        default_driver=HostShellDriver(),
    )
    telemetry = runner.run_task(
        task_id="org/t",
        arm="vanilla",
        image="img:latest",
        base_budget_sec=600.0,
        task_spec=TaskSpec(id="org/t", name="t", instruction="go", docker_image="img:latest"),
    )

    assert telemetry.extra["isolated_execution"] is False


def test_agent_failure_is_diagnosed_before_the_grading_symptom(tmp_path) -> None:
    """An agent that times out leaves a bad patch; the timeout is the cause.

    Reporting the grading message first made every agent-side failure -- timeout,
    crash, driver error -- indistinguishable from a genuinely wrong solution.
    """
    from contextlib import contextmanager
    from unittest.mock import MagicMock

    from lab.benchmarks.task_loader import TaskSpec
    from lab.engine.adapters.base import AgentDriver, DriverTelemetry
    from lab.engine.runner import AblationRunner

    class TimingOutDriver(AgentDriver):
        def run(self, task, workspace_path, prompt_override=None, conversation_id=None,
                timeout_sec=3600.0, container=None) -> DriverTelemetry:
            return DriverTelemetry(
                success=False, raw_response="", duration_seconds=600.0,
                error_message="agy turn exceeded timeout of 600.0s",
            )

    mock_docker = MagicMock()
    container = MagicMock()

    @contextmanager
    def fake_sandbox(image, logs_dir, container_name, **kwargs):
        vdir = logs_dir / "verifier"
        vdir.mkdir(parents=True, exist_ok=True)
        (vdir / "reward.json").write_text('{"reward": 0.0}')
        container.exec_run.return_value = (1, b"tests failed")
        yield container

    mock_docker.run_sandbox.side_effect = fake_sandbox

    telemetry = AblationRunner(
        docker_manager=mock_docker, workspace_root=tmp_path / "ws",
        default_driver=TimingOutDriver(),
    ).run_task(
        task_id="org/t", arm="superstate", image="img", base_budget_sec=600.0,
        task_spec=TaskSpec(id="org/t", name="t", instruction="go", docker_image="img"),
    )

    reason = str(telemetry.failure_reason)
    assert reason.startswith("Agent run failed:"), reason
    assert "exceeded timeout" in reason
    # The grading detail is kept, but as consequence rather than diagnosis.
    assert "grading then reported" in reason


class MockDriver(AgentDriver):
    """Predictable mock driver recording calls and returning successful telemetry."""

    def __init__(
        self,
        responses: list[DriverTelemetry] | None = None,
        side_effect: Any = None,
    ) -> None:
        self.responses = list(responses) if responses else []
        self.side_effect = side_effect
        self.calls: list[dict[str, Any]] = []

    def run(
        self,
        task: TaskSpec,
        workspace_path: Path,
        prompt_override: str | None = None,
        conversation_id: str | None = None,
        timeout_sec: float = 3600.0,
        container: Any = None,
    ) -> DriverTelemetry:
        call = {
            "task_id": task.id,
            "workspace": workspace_path,
            "prompt": prompt_override,
            "conversation_id": conversation_id,
            "timeout_sec": timeout_sec,
            "container": container,
        }
        self.calls.append(call)
        if self.side_effect:
            self.side_effect(call)
        if self.responses:
            return self.responses.pop(0)
        return DriverTelemetry(
            success=True,
            raw_response="Task complete.",
            duration_seconds=1.0,
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.01,
        )


@pytest.mark.parametrize(
    "arm_alias",
    [
        "superstate_mcp",
        "superstate-mcp",
        "superstate_rust_mcp",
        "superstate-rust-mcp",
        "mcp",
    ],
)
def test_runner_resolves_superstate_mcp_default_arms(arm_alias: str) -> None:
    from lab.engine.adapters.superstate_mcp import SuperstateMcpAdapter

    runner = AblationRunner(workspace_root=Path("/tmp"))
    adapter = runner._get_adapter(arm_alias)
    assert isinstance(adapter, SuperstateMcpAdapter)
    assert adapter.no_worktree is True
    assert adapter.worktree is False
    assert adapter.zero_turn_planning is True


@pytest.mark.parametrize(
    "arm_alias",
    [
        "superstate_mcp_worktree",
        "superstate-mcp-worktree",
        "mcp_worktree",
    ],
)
def test_runner_resolves_superstate_mcp_worktree_arms(arm_alias: str) -> None:
    from lab.engine.adapters.superstate_mcp import SuperstateMcpAdapter

    runner = AblationRunner(workspace_root=Path("/tmp"))
    adapter = runner._get_adapter(arm_alias)
    assert isinstance(adapter, SuperstateMcpAdapter)
    assert adapter.no_worktree is False
    assert adapter.worktree is True
    assert adapter.zero_turn_planning is True


@pytest.mark.parametrize(
    "arm_alias",
    [
        "superstate_mcp_planned",
        "superstate-mcp-planned",
    ],
)
def test_runner_resolves_superstate_mcp_planned_arms(arm_alias: str) -> None:
    from lab.engine.adapters.superstate_mcp import SuperstateMcpAdapter

    runner = AblationRunner(workspace_root=Path("/tmp"))
    adapter = runner._get_adapter(arm_alias)
    assert isinstance(adapter, SuperstateMcpAdapter)
    assert adapter.no_worktree is True
    assert adapter.worktree is False
    assert adapter.zero_turn_planning is False


@pytest.mark.parametrize(
    "arm_alias",
    [
        "superstate_agent_mcp",
        "superstate-agent-mcp",
        "agent_mcp",
        "agent-mcp",
    ],
)
def test_runner_resolves_superstate_agent_mcp_arms(arm_alias: str) -> None:
    from lab.engine.adapters.superstate_agent_mcp import SuperstateAgentMcpAdapter

    runner = AblationRunner(workspace_root=Path("/tmp"))
    adapter = runner._get_adapter(arm_alias)
    assert isinstance(adapter, SuperstateAgentMcpAdapter)


def _seed_git_repo(image: str, dest: Path, source_path: str) -> None:
    """Helper to initialize git repo in workspace seed for simulated runner tests."""
    import subprocess

    dest.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=str(dest), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test Agent"],
        cwd=str(dest),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "agent@test.local"],
        cwd=str(dest),
        check=True,
        capture_output=True,
    )
    (dest / "README.md").write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(dest), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "--no-gpg-sign", "-m", "Initial commit"],
        cwd=str(dest),
        check=True,
        capture_output=True,
    )


def test_runner_simulated_task_execution_superstate_mcp(tmp_path: Path) -> None:
    runner = _setup_runner(tmp_path)
    mock_docker = cast(Any, runner.docker_manager)
    mock_docker.seed_workspace_from_image.side_effect = _seed_git_repo
    mock_container = mock_docker.run_sandbox.return_value.__enter__.return_value
    mock_container.exec_run.return_value = (0, b"")

    mock_driver = MockDriver()
    mock_grade = EvaluationResult(
        task_id="test/mcp-task",
        arm="superstate_mcp",
        passed=True,
        reward=1.0,
        exit_code=0,
        patch_path=Path("/tmp/patch"),
        state_json_path=None,
        stats={"f2p_total": 1, "f2p_passed": 1, "p2p_total": 0, "p2p_passed": 0},
    )

    task_spec = TaskSpec(
        id="test/mcp-task",
        name="mcp-task",
        instruction="Implement feature via MCP",
        docker_image="dummy:latest",
        verification_cmd="true",
    )

    with patch("lab.engine.runner.extract_and_grade", return_value=mock_grade):
        telemetry = runner.run_task(
            task_id="test/mcp-task",
            arm="superstate_mcp",
            image="dummy:latest",
            base_budget_sec=600.0,
            task_spec=task_spec,
            driver=mock_driver,
        )

    assert telemetry.passed is True
    assert telemetry.arm == "superstate_mcp"
    assert telemetry.extra["agent_succeeded"] is True
    assert telemetry.extra["engine"] == "superstate_rust_mcp"
    assert telemetry.extra["transport"] == "mcp_stdio"
    assert len(mock_driver.calls) >= 1


def test_runner_simulated_task_execution_superstate_agent_mcp(tmp_path: Path) -> None:
    runner = _setup_runner(tmp_path)
    mock_docker = cast(Any, runner.docker_manager)
    mock_docker.seed_workspace_from_image.side_effect = _seed_git_repo
    mock_container = mock_docker.run_sandbox.return_value.__enter__.return_value
    mock_container.exec_run.return_value = (0, b"")

    mock_driver = MockDriver()
    mock_grade = EvaluationResult(
        task_id="test/agent-mcp-task",
        arm="superstate_agent_mcp",
        passed=True,
        reward=1.0,
        exit_code=0,
        patch_path=Path("/tmp/patch"),
        state_json_path=None,
        stats={"f2p_total": 1, "f2p_passed": 1, "p2p_total": 0, "p2p_passed": 0},
    )

    task_spec = TaskSpec(
        id="test/agent-mcp-task",
        name="agent-mcp-task",
        instruction="Solve task autonomously via MCP",
        docker_image="dummy:latest",
        verification_cmd="true",
    )

    with patch("lab.engine.runner.extract_and_grade", return_value=mock_grade):
        telemetry = runner.run_task(
            task_id="test/agent-mcp-task",
            arm="superstate_agent_mcp",
            image="dummy:latest",
            base_budget_sec=600.0,
            task_spec=task_spec,
            driver=mock_driver,
        )

    assert telemetry.passed is True
    assert telemetry.arm == "superstate_agent_mcp"
    assert telemetry.extra["agent_succeeded"] is True
    assert telemetry.extra["engine"] == "superstate_agent_mcp"
    assert telemetry.extra["transport"] == "mcp_agent_tooling"
    assert telemetry.extra["autonomous"] is True
    assert len(mock_driver.calls) >= 1
