"""Tests for Ablation Runner and Reporter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lab.engine.budget_policy import RunTelemetry
from lab.engine.reporter import generate_comparison_summary


def test_generate_comparison_summary() -> None:
    telemetry_runs = [
        # Arm 1: Vanilla
        RunTelemetry(
            task_id="task-1",
            arm="vanilla",
            passed=False,
            wall_clock_sec=600.0,
            cost_usd=0.50,
            input_tokens=50000,
            output_tokens=2000,
            total_granted_budget_sec=900.0,
        ),
        RunTelemetry(
            task_id="task-2",
            arm="vanilla",
            passed=True,
            wall_clock_sec=400.0,
            cost_usd=0.35,
            input_tokens=40000,
            output_tokens=1500,
            total_granted_budget_sec=900.0,
        ),
        # Arm 2: Superpowers
        RunTelemetry(
            task_id="task-1",
            arm="superpowers",
            passed=True,
            wall_clock_sec=700.0,
            cost_usd=0.80,
            input_tokens=80000,
            output_tokens=3000,
            total_granted_budget_sec=900.0,
        ),
        RunTelemetry(
            task_id="task-2",
            arm="superpowers",
            passed=True,
            wall_clock_sec=500.0,
            cost_usd=0.60,
            input_tokens=60000,
            output_tokens=2500,
            total_granted_budget_sec=900.0,
        ),
        # Arm 3: Superstate (earned lease extension)
        RunTelemetry(
            task_id="task-1",
            arm="superstate",
            passed=True,
            wall_clock_sec=1400.0,
            cost_usd=1.10,
            input_tokens=110000,
            output_tokens=4000,
            milestones_completed=2,
            lease_extensions_earned_sec=1200.0,
            total_granted_budget_sec=2100.0,
        ),
        RunTelemetry(
            task_id="task-2",
            arm="superstate",
            passed=True,
            wall_clock_sec=650.0,
            cost_usd=0.70,
            input_tokens=70000,
            output_tokens=2800,
            milestones_completed=1,
            lease_extensions_earned_sec=1200.0,
            total_granted_budget_sec=2100.0,
        ),
    ]

    summary = generate_comparison_summary(telemetry_runs)
    assert len(summary) == 3

    # Check vanilla metrics
    vanilla = summary["vanilla"]
    assert vanilla["total_tasks"] == 2
    assert vanilla["passes"] == 1
    assert vanilla["pass_rate_pct"] == 50.0
    assert vanilla["total_cost_usd"] == 0.85

    # Check superpowers metrics
    sp = summary["superpowers"]
    assert sp["total_tasks"] == 2
    assert sp["passes"] == 2
    assert sp["pass_rate_pct"] == 100.0
    assert sp["total_cost_usd"] == 1.40

    # Check superstate metrics
    ss = summary["superstate"]
    assert ss["total_tasks"] == 2
    assert ss["passes"] == 2
    assert ss["pass_rate_pct"] == 100.0
    assert ss["total_cost_usd"] == 1.80
    assert ss["total_lease_extensions_sec"] == 2400.0


def test_ablation_runner_execution_and_cleanup() -> None:
    from lab.engine.runner import AblationRunner

    mock_docker_mgr = MagicMock()
    runner = AblationRunner(docker_manager=mock_docker_mgr)

    def mock_executor(policy):
        policy.record_milestone_progress("M1")
        return {"passed": True, "cost_usd": 0.45, "input_tokens": 12000, "output_tokens": 500}

    telemetry = runner.run_task(
        task_id="mock-task-1",
        arm="superstate",
        image="mock:latest",
        base_budget_sec=900.0,
        lease_extension_sec=1200.0,
        executor_fn=mock_executor,
    )

    assert telemetry.passed is True
    assert telemetry.milestones_completed == 1
    assert telemetry.lease_extensions_earned_sec == 1200.0
    assert telemetry.total_granted_budget_sec == 2100.0
    assert telemetry.cost_usd == 0.45

    # Check that disk check and cleanup were called
    mock_docker_mgr.check_disk_space_or_prune.assert_called_once()
    mock_docker_mgr.prune_ephemeral_resources.assert_called_once()


def _fake_sandbox_factory(mock_container):
    """Build a run_sandbox stand-in that writes a passing verifier artifact."""
    from contextlib import contextmanager

    @contextmanager
    def fake_run_sandbox(image, logs_dir, container_name, **kwargs):
        vdir = logs_dir / "verifier"
        vdir.mkdir(parents=True, exist_ok=True)
        (vdir / "reward.json").write_text('{"reward": 1.0, "exit_code": 0}')
        adir = logs_dir / "artifacts"
        adir.mkdir(parents=True, exist_ok=True)
        (adir / "model.patch").write_text("diff --git a/x b/x")
        mock_container.exec_run.return_value = (0, b"All tests passed")
        fake_run_sandbox.kwargs = kwargs
        yield mock_container

    return fake_run_sandbox


def test_ablation_runner_live_path_requires_explicit_driver(tmp_path) -> None:
    # The live path must never silently substitute a mock agent.
    from lab.engine.runner import AblationRunner

    mock_docker_mgr = MagicMock()
    runner = AblationRunner(docker_manager=mock_docker_mgr, workspace_root=tmp_path / "workspaces")

    telemetry = runner.run_task(
        task_id="test/sample-task",
        arm="vanilla",
        image="test:latest",
        base_budget_sec=600.0,
    )

    assert telemetry.passed is False
    assert "No agent driver configured" in str(telemetry.failure_reason)
    mock_docker_mgr.run_sandbox.assert_not_called()


def test_ablation_runner_default_execution_mounts_workspace_into_container(tmp_path) -> None:
    from lab.engine.adapters.base import AgentDriver, DriverTelemetry
    from lab.engine.runner import CONTAINER_MOUNT_ROOT, CONTAINER_WORKSPACE, AblationRunner

    class StubDriver(AgentDriver):
        def run(
            self,
            task,
            workspace_path,
            prompt_override=None,
            conversation_id=None,
            timeout_sec=3600.0,
            container=None,
        ) -> DriverTelemetry:
            (workspace_path / "solution.py").write_text("# solved\n")
            return DriverTelemetry(
                success=True,
                raw_response="Done.",
                duration_seconds=1.0,
                input_tokens=10,
                output_tokens=5,
                cost_usd=0.01,
            )

    mock_docker_mgr = MagicMock()
    mock_container = MagicMock()
    fake_sandbox = _fake_sandbox_factory(mock_container)
    mock_docker_mgr.run_sandbox.side_effect = fake_sandbox

    runner = AblationRunner(
        docker_manager=mock_docker_mgr,
        workspace_root=tmp_path / "workspaces",
        default_driver=StubDriver(),
    )

    telemetry = runner.run_task(
        task_id="test/sample-task",
        arm="vanilla",
        image="test:latest",
        base_budget_sec=600.0,
    )

    assert telemetry.passed is True
    assert telemetry.arm == "vanilla"
    assert telemetry.task_id == "test/sample-task"
    mock_docker_mgr.run_sandbox.assert_called_once()
    mock_docker_mgr.prune_ephemeral_resources.assert_called_once()

    # The agent's workspace and the grader's /app must be the same filesystem.
    kwargs = fake_sandbox.kwargs
    volumes = kwargs["volumes"]
    assert len(volumes) == 1
    host_path, bind_spec = next(iter(volumes.items()))
    assert bind_spec == {"bind": CONTAINER_MOUNT_ROOT, "mode": "rw"}
    assert (Path(host_path) / "solution.py").is_file(), (
        "The mounted host directory must contain the agent's work"
    )
    # Spec-mandated container quotas.
    assert kwargs["nano_cpus"] == int(2.5 * 1e9)
    assert kwargs["mem_limit"] == "4g"


def test_run_cohort_refuses_to_dispatch_when_host_is_exhausted() -> None:
    from lab.engine.runner import AblationRunner, InsufficientResourcesError

    governor = MagicMock()
    governor.calculate_max_concurrency.return_value = 0
    runner = AblationRunner(docker_manager=MagicMock(), governor=governor)

    with pytest.raises(InsufficientResourcesError):
        runner.run_cohort(
            tasks=[{"task_id": "t1"}],
            arms=["vanilla"],
            executor_fn=lambda policy: {"passed": True},
        )


def test_run_cohort_forwards_task_specs_and_driver() -> None:
    from lab.benchmarks.task_loader import TaskSpec
    from lab.engine.runner import AblationRunner

    governor = MagicMock()
    governor.calculate_max_concurrency.return_value = 2
    runner = AblationRunner(docker_manager=MagicMock(), governor=governor)

    spec = TaskSpec(
        id="org/task-1",
        name="task-1",
        instruction="Fix it.",
        docker_image="img:latest",
        agent_timeout_sec=1234.0,
    )
    driver = MagicMock()

    with patch.object(runner, "run_task") as mock_run_task:
        mock_run_task.return_value = MagicMock(passed=True)
        runner.run_cohort(tasks=[spec], arms=["vanilla"], driver=driver)

    kwargs = mock_run_task.call_args.kwargs
    assert kwargs["task_spec"] is spec
    assert kwargs["driver"] is driver
    assert kwargs["task_id"] == "org/task-1"
    assert kwargs["image"] == "img:latest"
    assert kwargs["base_budget_sec"] == 1234.0


def _failed(arm: str, reason: str) -> RunTelemetry:
    return RunTelemetry(
        task_id="t",
        arm=arm,
        passed=False,
        wall_clock_sec=1.0,
        cost_usd=0.1,
        input_tokens=1,
        output_tokens=1,
        failure_reason=reason,
    )


def test_summarize_failures_clusters_like_failures() -> None:
    from lab.engine.reporter import summarize_failures

    runs = [
        _failed("superstate", "Verification gate failed for milestone 'Task 2: Wire adapter'"),
        _failed("superstate", "Verification gate failed for milestone 'Task 9: Add CLI'"),
        _failed("vanilla", "Exhausted maximum turns (50) without completion"),
        RunTelemetry(
            task_id="t",
            arm="vanilla",
            passed=True,
            wall_clock_sec=1.0,
            cost_usd=0.1,
            input_tokens=1,
            output_tokens=1,
        ),
    ]
    clusters = summarize_failures(runs)

    # Two gate failures differing only by milestone name must collapse to one cluster.
    assert clusters["superstate"] == [
        {"signature": "Verification gate failed for milestone '...'", "count": 2}
    ]
    assert clusters["vanilla"][0]["count"] == 1
    # Passing runs contribute nothing.
    assert sum(e["count"] for e in clusters["vanilla"]) == 1


def test_run_cohort_sizes_concurrency_on_declared_task_memory() -> None:
    """A cohort of 8 GB tasks must not be dispatched at the 4 GB default width."""
    from lab.benchmarks.task_loader import TaskSpec
    from lab.engine.runner import AblationRunner

    governor = MagicMock()
    governor.calculate_max_concurrency.return_value = 2
    runner = AblationRunner(docker_manager=MagicMock(), governor=governor)

    specs = [
        TaskSpec(
            id=f"org/t{i}",
            name=f"t{i}",
            instruction="go",
            docker_image="img",
            memory_mb=8192,
        )
        for i in range(3)
    ]

    with patch.object(runner, "run_task") as mock_run_task:
        mock_run_task.return_value = MagicMock(passed=True)
        runner.run_cohort(tasks=specs, arms=["vanilla"], driver=MagicMock())

    kwargs = governor.calculate_max_concurrency.call_args.kwargs
    assert kwargs["ram_gb_per_worker"] == 8.0


def _paired(task: str, arm: str, passed: bool, cost: float, harness: str = "agy") -> RunTelemetry:
    return RunTelemetry(
        task_id=task, arm=arm, passed=passed, wall_clock_sec=1.0, cost_usd=cost,
        input_tokens=0, output_tokens=0, extra={"harness": harness},
    )


def test_lift_is_measured_per_harness_and_task_pair() -> None:
    from lab.engine.reporter import compute_control_plane_lift

    runs = [
        _paired("t1", "vanilla", False, 0.1), _paired("t1", "superstate", True, 0.2),
        _paired("t2", "vanilla", True, 0.1), _paired("t2", "superstate", True, 0.2),
        _paired("t3", "vanilla", True, 0.1), _paired("t3", "superstate", False, 0.2),
    ]
    lift = compute_control_plane_lift(runs)["agy+superstate"]

    assert lift["paired_tasks"] == 3
    assert lift["gained"] == ["t1"]
    assert lift["lost"] == ["t3"]
    assert lift["lift_pct_points"] == 0.0  # 2/3 both ways: no net lift
    assert lift["cost_ratio"] == 2.0


def test_lift_never_compares_across_different_harnesses() -> None:
    # A claude baseline must not be used as the baseline for an agy arm.
    from lab.engine.reporter import compute_control_plane_lift

    runs = [
        _paired("t1", "vanilla", False, 0.1, harness="claude-code"),
        _paired("t1", "superstate", True, 0.2, harness="agy"),
    ]
    assert compute_control_plane_lift(runs) == {}


def test_runs_without_a_baseline_partner_are_excluded() -> None:
    from lab.engine.reporter import compute_control_plane_lift

    runs = [_paired("t1", "superstate", True, 0.2)]  # no vanilla partner
    assert compute_control_plane_lift(runs) == {}


def test_small_sample_warning_is_shown() -> None:
    from lab.engine.reporter import render_lift_report

    runs = [_paired("t1", "vanilla", False, 0.1), _paired("t1", "superstate", True, 0.2)]
    report = render_lift_report(runs)
    assert "one task is worth 100.0pp" in report
