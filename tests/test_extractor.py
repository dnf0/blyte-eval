"""Tests for Blind Extraction and Verification Pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from lab.engine.extractor import compute_test_metrics, extract_and_grade


class MockTask:
    def __init__(
        self,
        task_id: str,
        verification_cmd: str,
        base_commit: str = "HEAD~1",
        tests_dir: Path | None = None,
    ) -> None:
        self.task_id = task_id
        self.verification_cmd = verification_cmd
        self.base_commit = base_commit
        self.tests_dir = tests_dir


def _sealed_grader(tmp_path: Path) -> Path:
    """A stand-in held-out tests/ directory, so a test exercises the graded path."""
    d = tmp_path / "sealed_tests"
    d.mkdir(exist_ok=True)
    (d / "test_held_out.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")
    return d


def test_extract_and_grade_passing_reward_json(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    verifier_dir = logs_dir / "verifier"
    verifier_dir.mkdir(parents=True)
    reward_file = verifier_dir / "reward.json"
    reward_file.write_text(json.dumps({"reward": 1.0}), encoding="utf-8")

    artifacts_dir = logs_dir / "artifacts"
    artifacts_dir.mkdir(parents=True)
    patch_file = artifacts_dir / "model.patch"
    patch_file.write_text("diff --git a/foo b/foo", encoding="utf-8")

    mock_container = MagicMock()
    # exec_run returns (exit_code, output_bytes)
    mock_container.exec_run.return_value = (0, b"All tests passed")

    task = MockTask(task_id="task-1", verification_cmd="pytest tests/", tests_dir=_sealed_grader(tmp_path))
    result = extract_and_grade(
        container=mock_container,
        task=task,
        arm="blyte",
        logs_dir=logs_dir,
    )

    assert result.passed is True
    assert result.reward == 1.0
    assert result.exit_code == 0
    assert result.patch_path == patch_file
    assert result.failure_reason is None


def test_extract_and_grade_failing_reward_json(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    verifier_dir = logs_dir / "verifier"
    verifier_dir.mkdir(parents=True)
    reward_file = verifier_dir / "reward.json"
    reward_file.write_text(json.dumps({"reward": 0.0}), encoding="utf-8")

    mock_container = MagicMock()
    mock_container.exec_run.return_value = (1, b"AssertionError: failed")

    task = MockTask(task_id="task-1", verification_cmd="pytest tests/", tests_dir=_sealed_grader(tmp_path))
    result = extract_and_grade(
        container=mock_container,
        task=task,
        arm="vanilla",
        logs_dir=logs_dir,
    )

    assert result.passed is False
    assert result.reward == 0.0
    assert result.exit_code == 1
    assert "Verification failed" in str(result.failure_reason)


def test_extract_and_grade_missing_reward_json_fails(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True)
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True)

    mock_container = MagicMock()
    mock_container.exec_run.return_value = (0, b"OK")

    task = MockTask(task_id="task-1", verification_cmd="pytest tests/", tests_dir=tests_dir)
    result = extract_and_grade(
        container=mock_container,
        task=task,
        arm="superpowers",
        logs_dir=logs_dir,
    )

    # Missing reward.json must fail per evaluation specification when tests_dir exists
    assert result.passed is False
    assert result.reward is None
    assert result.exit_code == 0
    assert "Missing or invalid verifier/reward.json" in str(result.failure_reason)


def test_extract_and_grade_refuses_to_self_grade_without_a_sealed_verifier(
    tmp_path: Path,
) -> None:
    """A task with no held-out tests must be recorded unmeasurable, never scored.

    `verification_cmd` for these tasks is `pytest tests/`, and with no sealed suite to
    inject that runs whatever the AGENT put in tests/ -- the agent grading itself.

    Measured 2026-09-16 across 55 paired runs: the 7 terminal-bench tasks with no sealed
    grader went vanilla 0/7, superstate_mcp 7/7, because superstate's handoff prompt asks
    the worker to produce and run a verification command and the baseline gets no such
    instruction. That supplied 7 of the 18 discordant pairs behind the headline lift.
    """
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True)

    mock_container = MagicMock()
    # The agent's own tests pass, which under the old behaviour scored 1.0.
    mock_container.exec_run.return_value = (0, b"3 passed")

    task = MockTask(task_id="task-1", verification_cmd="pytest tests/", tests_dir=None)
    result = extract_and_grade(
        container=mock_container,
        task=task,
        arm="superstate_mcp",
        logs_dir=logs_dir,
    )

    assert result.passed is False, "an ungradeable task must never be recorded as a pass"
    assert result.reward is None, "there is no reward to report without a grader"
    assert "UNMEASURABLE" in str(result.failure_reason)
    assert result.stats == {"unmeasurable": True}
    # exec_run is still used for blind patch extraction; what must never happen is the
    # verification command being run against the agent's own workspace.
    ran = [str(call) for call in mock_container.exec_run.call_args_list]
    assert not any("pytest tests/" in c for c in ran), \
        f"the agent's own tests must not be executed as a grader: {ran}"


class _HeldOutTask:
    """A task that ships its own verifier image."""

    def __init__(self, tests_dir: Path) -> None:
        self.id = "org/held-out"
        self.base_commit = "abc123"
        self.verification_cmd = "pytest"
        self.collect_commands: list[str] = []
        self.tests_dir = tests_dir


def test_held_out_verifier_grade_wins_over_agent_container(tmp_path: Path) -> None:
    """The agent's own container must not be able to declare its work correct."""
    from unittest.mock import MagicMock

    from lab.engine.verifier import VerifierOutcome

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()

    # The agent's container would happily report success.
    agent_container = MagicMock()
    agent_container.exec_run.return_value = (0, b"all good, honest")

    # The held-out verifier disagrees.
    verifier = MagicMock()
    verifier.run.return_value = VerifierOutcome(
        reward=0.0,
        exit_code=1,
        output="f2p tests still failing",
        reward_source="reward.json",
    )

    result = extract_and_grade(
        container=agent_container,
        task=_HeldOutTask(tests_dir=tmp_path / "tests"),
        arm="blyte",
        logs_dir=logs_dir,
        verifier=verifier,
    )

    assert result.passed is False
    assert result.reward == 0.0
    verifier.run.assert_called_once()
    # The verification command must NOT have been run in the agent's container.
    ran = [c.args[0] for c in agent_container.exec_run.call_args_list]
    assert not any("pytest" == cmd for cmd in ran), (
        "grading must not execute in the agent's own container when a held-out verifier exists"
    )


def test_held_out_verifier_pass_is_accepted(tmp_path: Path) -> None:
    from unittest.mock import MagicMock

    from lab.engine.verifier import VerifierOutcome

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()

    verifier = MagicMock()
    verifier.run.return_value = VerifierOutcome(
        reward=1.0, exit_code=0, output="all f2p pass", reward_source="reward.json"
    )

    result = extract_and_grade(
        container=MagicMock(),
        task=_HeldOutTask(tests_dir=tmp_path / "tests"),
        arm="vanilla",
        logs_dir=logs_dir,
        verifier=verifier,
    )
    assert result.passed is True
    assert result.reward == 1.0


def test_harness_artifacts_are_excluded_from_the_patch(tmp_path: Path) -> None:
    from unittest.mock import MagicMock

    container = MagicMock()
    container.exec_run.return_value = (0, b"ok")
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()

    extract_and_grade(
        container=container,
        task=MockTask(task_id="t", verification_cmd="pytest"),
        arm="superpowers",
        logs_dir=logs_dir,
    )

    exclude_cmd = container.exec_run.call_args_list[0].args[0]
    for artifact in ("AGENTS.md", ".agents/", "plan.md", ".agent-state/"):
        assert artifact in exclude_cmd
    assert "/app/.git/info/exclude" in exclude_cmd


def test_compute_test_metrics_full_counts() -> None:
    stats = {
        "reward": 1.0,
        "f2p_total": 137,
        "f2p_passed": 137,
        "p2p_total": 3134,
        "p2p_passed": 3134,
    }
    metrics = compute_test_metrics(stats, passed=True)
    assert metrics["test_pass_fraction"] == 1.0
    assert metrics["f2p_fraction"] == 1.0
    assert metrics["p2p_fraction"] == 1.0
    assert metrics["tests_passed"] == 3271
    assert metrics["tests_total"] == 3271


def test_compute_test_metrics_zero_totals() -> None:
    stats = {"f2p_total": 0, "f2p_passed": 0, "p2p_total": 0, "p2p_passed": 0}
    # When passed=True, fraction is 1.0, but per-suite fractions are None since totals are 0
    metrics_pass = compute_test_metrics(stats, passed=True)
    assert metrics_pass["test_pass_fraction"] == 1.0
    assert metrics_pass["f2p_fraction"] is None
    assert metrics_pass["p2p_fraction"] is None
    assert metrics_pass["tests_passed"] == 0
    assert metrics_pass["tests_total"] == 0

    # When passed=False, fraction is 0.0
    metrics_fail = compute_test_metrics(stats, passed=False)
    assert metrics_fail["test_pass_fraction"] == 0.0
    assert metrics_fail["f2p_fraction"] is None
    assert metrics_fail["p2p_fraction"] is None
    assert metrics_fail["tests_passed"] == 0
    assert metrics_fail["tests_total"] == 0


def test_compute_test_metrics_partial_failures() -> None:
    stats = {
        "f2p_total": 20,
        "f2p_passed": 10,
        "p2p_total": 80,
        "p2p_passed": 80,
    }
    metrics = compute_test_metrics(stats, passed=False)
    assert abs(metrics["test_pass_fraction"] - 0.9) < 1e-6
    assert abs(metrics["f2p_fraction"] - 0.5) < 1e-6
    assert metrics["p2p_fraction"] == 1.0
    assert metrics["tests_passed"] == 90
    assert metrics["tests_total"] == 100


def test_compute_test_metrics_none_stats() -> None:
    metrics_pass = compute_test_metrics(None, passed=True)
    assert metrics_pass["test_pass_fraction"] == 1.0
    assert metrics_pass["f2p_fraction"] is None
    assert metrics_pass["p2p_fraction"] is None
    assert metrics_pass["tests_passed"] is None
    assert metrics_pass["tests_total"] is None

    metrics_fail = compute_test_metrics(None, passed=False)
    assert metrics_fail["test_pass_fraction"] == 0.0
    assert metrics_fail["f2p_fraction"] is None
    assert metrics_fail["p2p_fraction"] is None
    assert metrics_fail["tests_passed"] is None
    assert metrics_fail["tests_total"] is None


def test_extract_and_grade_propagates_stats_from_reward_json(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    verifier_dir = logs_dir / "verifier"
    verifier_dir.mkdir(parents=True)
    reward_file = verifier_dir / "reward.json"
    stats_data = {
        "reward": 1.0,
        "f2p_total": 5,
        "f2p_passed": 5,
        "p2p_total": 10,
        "p2p_passed": 10,
    }
    reward_file.write_text(json.dumps(stats_data), encoding="utf-8")

    mock_container = MagicMock()
    mock_container.exec_run.return_value = (0, b"Passed")

    task = MockTask(task_id="task-stats-1", verification_cmd="pytest", tests_dir=_sealed_grader(tmp_path))
    result = extract_and_grade(
        container=mock_container,
        task=task,
        arm="vanilla",
        logs_dir=logs_dir,
    )

    assert result.stats == stats_data


def test_extract_and_grade_propagates_stats_from_held_out_verifier(tmp_path: Path) -> None:
    from lab.engine.verifier import VerifierOutcome

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()

    stats_data = {
        "reward": 0.5,
        "f2p_total": 4,
        "f2p_passed": 2,
        "p2p_total": 10,
        "p2p_passed": 10,
    }
    verifier = MagicMock()
    verifier.run.return_value = VerifierOutcome(
        reward=0.5,
        exit_code=1,
        output="2 f2p tests failed",
        reward_source="reward.json",
        stats=stats_data,
    )

    task = _HeldOutTask(tests_dir=tmp_path / "tests")
    result = extract_and_grade(
        container=MagicMock(),
        task=task,
        arm="blyte",
        logs_dir=logs_dir,
        verifier=verifier,
    )

    assert result.stats == stats_data


def test_compute_test_metrics_generic_total_passed() -> None:
    stats = {"tests_total": 50, "tests_passed": 45}
    metrics = compute_test_metrics(stats, passed=False)
    assert metrics["test_pass_fraction"] == 0.9
    assert metrics["tests_total"] == 50
    assert metrics["tests_passed"] == 45
    assert metrics["f2p_fraction"] is None
    assert metrics["p2p_fraction"] is None




def test_bridge_script_is_excluded_from_the_graded_patch(tmp_path: Path) -> None:
    """The agy driver writes ./run-in-container into the workspace.

    It is bind-mounted to /app, so `git add -A` would commit it into model.patch.
    The task verifiers record an out-of-scope signal for files outside the
    expected fix scope, so harness scaffolding must never reach the patch.
    """
    from unittest.mock import MagicMock

    container = MagicMock()
    container.exec_run.return_value = (0, b"ok")
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()

    extract_and_grade(
        container=container,
        task=MockTask(task_id="t", verification_cmd="pytest"),
        arm="vanilla",
        logs_dir=logs_dir,
    )

    exclude_cmd = container.exec_run.call_args_list[0].args[0]
    assert "run-in-container" in exclude_cmd


def test_extract_and_grade_in_container_tests_injection(tmp_path: Path) -> None:
    """When a task has a tests directory without a Dockerfile, tests are injected into container."""
    from unittest.mock import MagicMock

    logs_dir = tmp_path / "logs"
    verifier_dir = logs_dir / "verifier"
    verifier_dir.mkdir(parents=True)
    (verifier_dir / "reward.txt").write_text("1.0\n", encoding="utf-8")
    ctrf_data = {"results": {"summary": {"tests": 11, "passed": 11, "failed": 0}}}
    (verifier_dir / "ctrf.json").write_text(json.dumps(ctrf_data), encoding="utf-8")

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test.sh").write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")

    container = MagicMock()
    container.exec_run.return_value = (0, b"All tests passed")

    class InContainerTask:
        id = "tb/db-wal-recovery"
        task_id = "tb/db-wal-recovery"
        base_commit = None
        collect_commands = []
        verification_cmd = "bash /tests/test.sh"
        has_verifier_dockerfile = False
        verifier_env = {"FOO": "BAR"}

        def __init__(self, td: Path) -> None:
            self.tests_dir = td

    result = extract_and_grade(
        container=container,
        task=InContainerTask(tests_dir),
        arm="blyte",
        logs_dir=logs_dir,
    )

    assert result.passed is True
    assert result.reward == 1.0
    assert result.stats is not None
    assert result.stats.get("tests_total") == 11
    assert result.stats.get("tests_passed") == 11
    container.put_archive.assert_called_once()
