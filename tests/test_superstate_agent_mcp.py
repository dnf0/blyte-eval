"""Tests for SuperstateAgentMcpAdapter.

Tests the agent-level autonomous MCP adapter that exposes Superstate MCP tools
directly to the agent runtime under an autonomous contract. Verifies workspace setup,
prompt seeding, driver MCP configuration, milestone completion detection via state
inspection, gate fallback, and process/worktree cleanup.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Any, Callable

import pytest

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.base import AgentDriver, DriverTelemetry, TaskRunResult
from lab.engine.adapters.superstate_agent_mcp import SuperstateAgentMcpAdapter
from lab.engine.mcp.client import SuperstateMcpClient


class MockDriver(AgentDriver):
    """Mock agent driver supporting pre-canned responses and recording invocations."""

    def __init__(
        self,
        responses: list[DriverTelemetry] | None = None,
        side_effect: Callable[[dict[str, Any]], None] | None = None,
        superstate_mcp: bool = False,
        superstate_bin: str | None = None,
    ) -> None:
        self.responses = list(responses) if responses else []
        self.side_effect = side_effect
        self.superstate_mcp = superstate_mcp
        self.superstate_bin = superstate_bin
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
            raw_response="Completed the requested changes autonomously using MCP tools.",
            duration_seconds=2.0,
            input_tokens=150,
            output_tokens=75,
            cost_usd=0.002,
            conversation_id="conv-auto-1",
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
    task_id: str = "test/mcp-agent-task",
    instruction: str = "Implement autonomous feature using MCP",
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
    """Verify default configuration and provenance fields."""
    adapter = SuperstateAgentMcpAdapter()
    assert adapter.name == "superstate_agent_mcp"
    assert adapter.superstate_bin is None

    prov = adapter.get_provenance()
    assert prov["engine"] == "superstate_agent_mcp"
    assert prov["transport"] == "mcp_agent_tooling"
    assert prov["autonomous"] is True
    assert "mcp_tools_discovered" in prov


def test_workspace_setup_and_guidance_stripping(tmp_path: Path) -> None:
    """Verify setup_workspace strips legacy files and excludes harness artifacts."""
    _init_git_repo(tmp_path)

    (tmp_path / "AGENTS.md").write_text("legacy agents", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("legacy claude", encoding="utf-8")
    skills_dir = tmp_path / ".agents" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "dummy.md").write_text("dummy skill", encoding="utf-8")

    adapter = SuperstateAgentMcpAdapter()
    adapter.setup_workspace(tmp_path)

    assert not (tmp_path / "AGENTS.md").exists()
    assert not (tmp_path / "CLAUDE.md").exists()
    assert not skills_dir.exists()

    exclude = tmp_path / ".git" / "info" / "exclude"
    assert exclude.is_file()
    exclude_text = exclude.read_text(encoding="utf-8")
    assert ".agent-state/" in exclude_text
    assert "plan.md" in exclude_text


def test_driver_receives_autonomous_prompt_contract_and_enables_mcp(tmp_path: Path) -> None:
    """Verify driver prompt is seeded with autonomous contract and driver.superstate_mcp is set."""
    _init_git_repo(tmp_path)
    task = _make_dummy_task(tmp_path, instruction="Solve math equation in calculator.py")

    driver = MockDriver(superstate_mcp=False)
    adapter = SuperstateAgentMcpAdapter()

    # Pre-mark state as completed in side-effect so run succeeds immediately
    def driver_action(call: dict[str, Any]) -> None:
        state_file = tmp_path / ".agent-state" / "state.json"
        state_data = json.loads(state_file.read_text(encoding="utf-8"))
        state_data["status"] = "completed"
        state_data["active_task"] = None
        state_data["completed_tasks"] = [{"id": "task-1", "title": "Solve math equation"}]
        state_file.write_text(json.dumps(state_data), encoding="utf-8")

    driver.side_effect = driver_action

    result = adapter.execute(tmp_path, task, driver)

    assert result.success is True
    # Driver must have had superstate_mcp enabled by adapter
    assert driver.superstate_mcp is True
    assert len(driver.calls) == 1

    prompt = str(driver.calls[0]["prompt"])
    assert "Solve math equation in calculator.py" in prompt
    assert "AUTONOMOUS SUPERSTATE MCP EXECUTION CONTRACT" in prompt
    assert "state_prompt" in prompt
    assert "state_exec" in prompt
    assert "state_next" in prompt
    assert "state_note" in prompt


def test_single_milestone_completion_via_state_next(tmp_path: Path) -> None:
    """Driver simulates agent calling state_next using a live MCP client against repo."""
    _init_git_repo(tmp_path)

    output_file = tmp_path / "result.txt"
    task = _make_dummy_task(
        tmp_path,
        instruction="Generate result.txt",
        verification_cmd=f"test -f {output_file.name}",
    )

    def agent_mcp_simulation(call: dict[str, Any]) -> None:
        # Agent writes the required file
        output_file.write_text("42\n", encoding="utf-8")
        # Agent commits its change and advances state via SuperstateMcpClient
        subprocess.run(["git", "add", "result.txt"], cwd=tmp_path, check=True)
        subprocess.run(
            ["git", "-c", "user.name=Agent", "-c", "user.email=agent@eval.local", "commit", "-m", "feat: create result.txt"],
            cwd=tmp_path,
            check=True,
        )
        with SuperstateMcpClient(cwd=tmp_path) as client:
            adv = client.state_next(repo=tmp_path, verify_git_clean=True)
            assert adv is True

    driver = MockDriver(side_effect=agent_mcp_simulation)
    adapter = SuperstateAgentMcpAdapter()

    result = adapter.execute(tmp_path, task, driver)

    assert isinstance(result, TaskRunResult)
    assert result.success is True
    assert result.harness_name == "superstate_agent_mcp"
    assert result.turns == 1
    assert result.provenance["engine"] == "superstate_agent_mcp"
    assert result.provenance["transport"] == "mcp_agent_tooling"
    assert result.provenance["autonomous"] is True
    assert result.provenance["mcp_tools_discovered"] >= 20
    assert output_file.is_file()


def test_fallback_to_verification_gate_when_state_not_advanced(tmp_path: Path) -> None:
    """When agent forgets state_next but verification gate passes, adapter marks success."""
    _init_git_repo(tmp_path)

    output_file = tmp_path / "valid.txt"
    task = _make_dummy_task(
        tmp_path,
        instruction="Create valid.txt",
        verification_cmd=f"test -f {output_file.name}",
    )

    def driver_action(call: dict[str, Any]) -> None:
        # Agent creates file but never calls state_next
        output_file.write_text("valid content\n", encoding="utf-8")

    driver = MockDriver(side_effect=driver_action)
    adapter = SuperstateAgentMcpAdapter()

    result = adapter.execute(tmp_path, task, driver)

    assert result.success is True
    assert output_file.is_file()


def test_incomplete_task_reporting_when_gate_fails(tmp_path: Path) -> None:
    """When agent leaves task incomplete and verification gate fails, adapter marks failure."""
    _init_git_repo(tmp_path)

    task = _make_dummy_task(
        tmp_path,
        instruction="Create missing.txt",
        verification_cmd="test -f missing.txt",
    )

    driver = MockDriver()
    adapter = SuperstateAgentMcpAdapter()

    result = adapter.execute(tmp_path, task, driver)

    assert result.success is False
    assert result.error_message is not None
    assert "Verification gate failed" in result.error_message or "incomplete" in result.error_message.lower()


def test_worktree_cleanup_on_completion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify client.worktree_clean is called upon finish."""
    _init_git_repo(tmp_path)

    task = _make_dummy_task(tmp_path, instruction="Test cleanup", verification_cmd="true")
    driver = MockDriver()
    adapter = SuperstateAgentMcpAdapter()

    clean_called = False
    original_worktree_clean = SuperstateMcpClient.worktree_clean

    def mock_clean(self: SuperstateMcpClient, repo: Path | str, force: bool = False) -> dict[str, Any]:
        nonlocal clean_called
        clean_called = True
        return original_worktree_clean(self, repo, force=force)

    monkeypatch.setattr(SuperstateMcpClient, "worktree_clean", mock_clean)

    # Set state as completed in side-effect
    def driver_action(call: dict[str, Any]) -> None:
        state_file = tmp_path / ".agent-state" / "state.json"
        state_data = json.loads(state_file.read_text(encoding="utf-8"))
        state_data["status"] = "completed"
        state_file.write_text(json.dumps(state_data), encoding="utf-8")

    driver.side_effect = driver_action

    result = adapter.execute(tmp_path, task, driver)
    assert result.success is True
    assert clean_called is True
