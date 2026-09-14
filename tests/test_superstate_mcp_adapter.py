"""Tests for SuperstateMcpAdapter.

Tests the harness-level MCP adapter for state orchestration over stdio JSON-RPC,
including zero-turn and plan-based initialization, milestone loop execution,
gate failure and recovery handling, provenance assertions, and worktree cleanup.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any, Callable
from unittest.mock import MagicMock

import pytest

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.base import AgentDriver, DriverTelemetry, TaskRunResult
from lab.engine.adapters.superstate_mcp import SuperstateMcpAdapter
from lab.engine.mcp.client import SuperstateMcpClient


class MockDriver(AgentDriver):
    """Predictable mock driver supporting pre-canned responses and side-effects."""

    def __init__(
        self,
        responses: list[DriverTelemetry] | None = None,
        side_effect: Callable[[dict[str, Any]], None] | None = None,
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
        container: object = None,
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
            raw_response="Task milestone completed.",
            duration_seconds=2.0,
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.001,
            conversation_id="conv-1",
        )


def _init_git_repo(path: Path) -> None:
    """Initialize a git repository with an initial commit."""
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test Agent"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    readme = path / "README.md"
    readme.write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "--no-gpg-sign", "-m", "Initial commit"],
        cwd=path,
        check=True,
        capture_output=True,
    )


def _make_dummy_task(
    tmp_path: Path,
    task_id: str = "test/mcp-task",
    instruction: str = "Implement test feature",
    verification_cmd: str = "true",
) -> TaskSpec:
    return TaskSpec(
        id=task_id,
        name=task_id.split("/")[-1],
        instruction=instruction,
        docker_image="dummy:latest",
        task_dir=tmp_path,
        verification_cmd=verification_cmd,
    )


def test_adapter_initialization_defaults_and_provenance() -> None:
    """Verify default parameters and provenance initial structure."""
    adapter = SuperstateMcpAdapter()
    assert adapter.name == "superstate_mcp"
    assert adapter.no_worktree is True
    assert adapter.worktree is False
    assert adapter.zero_turn_planning is True
    assert adapter.superstate_bin is None

    prov = adapter.get_provenance()
    assert prov["engine"] == "superstate_rust_mcp"
    assert prov["transport"] == "mcp_stdio"
    assert "mcp_tools_discovered" in prov
    assert prov["no_worktree"] is True
    assert prov["worktree"] is False
    assert prov["zero_turn_planning"] is True


def test_workspace_setup_and_guidance_stripping(tmp_path: Path) -> None:
    """Verify setup_workspace strips legacy files and excludes harness artifacts."""
    _init_git_repo(tmp_path)

    # Pre-existing guidance files that must be removed
    (tmp_path / "AGENTS.md").write_text("legacy agents", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("legacy claude", encoding="utf-8")
    skills_dir = tmp_path / ".agents" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "dummy.md").write_text("dummy skill", encoding="utf-8")

    adapter = SuperstateMcpAdapter()
    adapter.setup_workspace(tmp_path)

    assert not (tmp_path / "AGENTS.md").exists()
    assert not (tmp_path / "CLAUDE.md").exists()
    assert not skills_dir.exists()

    exclude = tmp_path / ".git" / "info" / "exclude"
    assert exclude.is_file()
    exclude_text = exclude.read_text(encoding="utf-8")
    assert ".agent-state/" in exclude_text
    assert "plan.md" in exclude_text


def test_single_milestone_zero_turn_execution(tmp_path: Path) -> None:
    """Execute a single-milestone task with zero-turn planning using real superstate."""
    _init_git_repo(tmp_path)

    target_file = tmp_path / "output.txt"
    task = _make_dummy_task(
        tmp_path,
        instruction="Generate output.txt with hello",
        verification_cmd=f"test -f {target_file.name}",
    )

    def driver_action(call: dict[str, Any]) -> None:
        target_file.write_text("hello world\n", encoding="utf-8")

    driver = MockDriver(side_effect=driver_action)
    adapter = SuperstateMcpAdapter()

    result = adapter.execute(tmp_path, task, driver)

    assert isinstance(result, TaskRunResult)
    assert result.success is True
    assert result.turns == 1
    assert result.harness_name == "superstate_mcp"
    assert result.error_message is None
    assert result.provenance["engine"] == "superstate_rust_mcp"
    assert result.provenance["transport"] == "mcp_stdio"
    assert result.provenance["mcp_tools_discovered"] >= 4
    assert result.provenance["plan_source"] == "direct_state_handoff"

    # Verify auto-commit of uncommitted changes
    log = subprocess.run(
        ["git", "log", "-n", "1", "--oneline"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "chore: checkpoint completed milestone" in log.stdout


def test_multi_milestone_plan_based_execution(tmp_path: Path) -> None:
    """Execute a multi-milestone task with plan.md using real superstate."""
    _init_git_repo(tmp_path)

    file_a = tmp_path / "file_a.txt"
    file_b = tmp_path / "file_b.txt"

    plan_content = (
        "### Task 1: Create File A\n"
        f"- Verification Command: test -f {file_a.name}\n\n"
        "### Task 2: Create File B\n"
        f"- Verification Command: test -f {file_b.name}\n"
    )
    (tmp_path / "plan.md").write_text(plan_content, encoding="utf-8")

    task = _make_dummy_task(tmp_path, instruction="Create files A and B")

    turn_count = 0

    def driver_action(call: dict[str, Any]) -> None:
        nonlocal turn_count
        turn_count += 1
        if turn_count == 1:
            file_a.write_text("A\n", encoding="utf-8")
        elif turn_count == 2:
            file_b.write_text("B\n", encoding="utf-8")

    driver = MockDriver(side_effect=driver_action)
    adapter = SuperstateMcpAdapter(zero_turn_planning=False)

    result = adapter.execute(tmp_path, task, driver)

    assert result.success is True
    assert result.turns == 2
    assert file_a.is_file()
    assert file_b.is_file()
    assert result.provenance["plan_source"] == "plan.md"
    assert result.provenance["milestones_planned"] == 2
    assert result.provenance["decomposed"] is True


def test_multi_milestone_planning_turn_generates_plan(tmp_path: Path) -> None:
    """When plan.md is missing and zero_turn_planning=False, driver generates plan."""
    _init_git_repo(tmp_path)

    file_a = tmp_path / "mod_a.txt"

    planning_response = (
        "### Task 1: Build Module A\n"
        f"- Verification Command: test -f {file_a.name}\n"
    )

    responses = [
        DriverTelemetry(
            success=True,
            raw_response=planning_response,
            duration_seconds=3.0,
            input_tokens=200,
            output_tokens=100,
        ),
        DriverTelemetry(
            success=True,
            raw_response="Module A completed.",
            duration_seconds=4.0,
            input_tokens=150,
            output_tokens=50,
        ),
    ]

    call_index = 0

    def driver_action(call: dict[str, Any]) -> None:
        nonlocal call_index
        call_index += 1
        if call_index == 1:
            # Planning turn writes plan.md
            (tmp_path / "plan.md").write_text(planning_response, encoding="utf-8")
        elif call_index == 2:
            # Milestone turn creates the file
            file_a.write_text("Module A code\n", encoding="utf-8")

    driver = MockDriver(responses=responses, side_effect=driver_action)
    adapter = SuperstateMcpAdapter(zero_turn_planning=False)
    task = _make_dummy_task(tmp_path, instruction="Build Module A")

    result = adapter.execute(tmp_path, task, driver)

    assert result.success is True
    assert result.turns == 2  # 1 planning turn + 1 milestone turn
    assert result.provenance["plan_source"] == "plan.md"
    assert file_a.is_file()


def test_gate_command_failure_handling_and_retry(tmp_path: Path) -> None:
    """Test gate command failure, diagnostic prompt feed, and recovery on retry."""
    _init_git_repo(tmp_path)

    target_file = tmp_path / "repaired.txt"
    task = _make_dummy_task(
        tmp_path,
        instruction="Create repaired.txt",
        verification_cmd=f"test -f {target_file.name}",
    )

    turn_count = 0

    def driver_action(call: dict[str, Any]) -> None:
        nonlocal turn_count
        turn_count += 1
        if turn_count == 1:
            # Turn 1: fails to create the file
            pass
        elif turn_count == 2:
            # Turn 2: checks that retry prompt contains error details, stateless turn (conv=None), and git diff stat
            prompt = str(call.get("prompt", ""))
            assert "VERIFICATION GATE FAILED" in prompt
            assert f"test -f {target_file.name}" in prompt
            assert "Modified Files on Disk" in prompt
            assert call.get("conversation_id") is None  # Bounded stateless retry
            target_file.write_text("repaired content\n", encoding="utf-8")

    driver = MockDriver(side_effect=driver_action)
    adapter = SuperstateMcpAdapter(max_turns_per_milestone=3)

    result = adapter.execute(tmp_path, task, driver)

    assert result.success is True
    assert result.turns == 2
    assert target_file.is_file()


def test_gate_command_failure_exhausts_turns(tmp_path: Path) -> None:
    """Test gate command persistently failing exhausts turns and reports failure."""
    _init_git_repo(tmp_path)

    task = _make_dummy_task(
        tmp_path,
        instruction="Create impossible.txt",
        verification_cmd="test -f impossible.txt",
    )

    driver = MockDriver()
    adapter = SuperstateMcpAdapter(max_turns_per_milestone=2)

    result = adapter.execute(tmp_path, task, driver)

    assert result.success is False
    assert result.turns == 2
    assert "Verification gate failed" in str(result.error_message)


def test_container_gate_execution(tmp_path: Path) -> None:
    """Verify that when a container is provided, gate command executes inside it."""
    _init_git_repo(tmp_path)

    task = _make_dummy_task(
        tmp_path,
        instruction="Run container command",
        verification_cmd="pytest -q",
    )

    mock_container = MagicMock()
    # exec_run returns (exit_code, output_bytes)
    mock_container.exec_run.return_value = (0, b"1 passed in 0.01s")

    driver = MockDriver()
    adapter = SuperstateMcpAdapter()

    result = adapter.execute(tmp_path, task, driver, container=mock_container)

    assert result.success is True
    # Container exec_run must have been called for gate evaluation
    exec_run_calls = [
        call for call in mock_container.exec_run.call_args_list
        if "pytest -q" in str(call)
    ]
    assert len(exec_run_calls) > 0


def test_worktree_cleanup_on_completion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify client.worktree_clean is called upon finish."""
    _init_git_repo(tmp_path)

    task = _make_dummy_task(tmp_path, instruction="Test cleanup", verification_cmd="true")
    driver = MockDriver()
    adapter = SuperstateMcpAdapter()

    clean_called = False
    original_worktree_clean = SuperstateMcpClient.worktree_clean

    def mock_clean(self: SuperstateMcpClient, repo: Path | str, force: bool = False) -> dict[str, Any]:
        nonlocal clean_called
        clean_called = True
        return original_worktree_clean(self, repo, force=force)

    monkeypatch.setattr(SuperstateMcpClient, "worktree_clean", mock_clean)

    result = adapter.execute(tmp_path, task, driver)
    assert result.success is True
    assert clean_called is True
