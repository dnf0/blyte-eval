from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.superstate_relay import SuperstateRelayAdapter
from lab.engine.adapters.base import DriverTelemetry


def test_relay_adapter_initialization() -> None:
    adapter = SuperstateRelayAdapter()
    assert adapter.name == "superstate_relay"
    assert adapter.max_retries == 2


def test_relay_adapter_run_task_mocked(tmp_path: Path) -> None:
    adapter = SuperstateRelayAdapter()
    task = TaskSpec(
        id="test-task",
        name="Test Task",
        instruction="Fix the bug",
        docker_image="test:latest",
        task_dir=tmp_path / "repo",
    )

    mock_claude = MagicMock()
    mock_claude.run.return_value = DriverTelemetry(
        success=True, raw_response="Done stage 1", duration_seconds=10.0, input_tokens=500, output_tokens=100, cost_usd=0.01
    )
    mock_agy = MagicMock()
    mock_agy.run.return_value = DriverTelemetry(
        success=True, raw_response="Done stage 2", duration_seconds=15.0, input_tokens=800, output_tokens=150, cost_usd=0.005
    )

    # Pre-create handoff.md so stage 1 verification passes
    state_dir = tmp_path / ".agent-state"
    state_dir.mkdir(parents=True, exist_ok=True)
    handoff_file = state_dir / "handoff.md"
    handoff_file.write_text("# Handoff\n- Active Task: task-1\n", encoding="utf-8")

    with patch.object(adapter, "_run_gate_command", return_value=(True, 0, "pass")):
        result = adapter.run_task(
            task=task,
            workspace_path=tmp_path,
            driver=mock_agy,
            budget_sec=120.0,
            claude_driver=mock_claude,
        )

    assert result.success is True
    assert result.task_id == "test-task"
    assert result.harness_name == "superstate_relay"
    assert result.input_tokens == 1300
    assert result.output_tokens == 250
    assert result.cost_usd == pytest.approx(0.015)


def test_relay_adapter_execute_mocked(tmp_path: Path) -> None:
    adapter = SuperstateRelayAdapter()
    task = TaskSpec(
        id="test-task",
        name="Test Task",
        instruction="Fix the bug",
        docker_image="test:latest",
        task_dir=tmp_path / "repo",
    )
    mock_agy = MagicMock()
    with patch.object(adapter, "run_task") as mock_run_task, \
         patch("lab.engine.drivers.claude_cli.ClaudeCliDriver"):
        adapter.execute(tmp_path, task, mock_agy)
        mock_run_task.assert_called_once()


def test_relay_adapter_nested_subdirectory_handoff_discovery(tmp_path: Path) -> None:
    adapter = SuperstateRelayAdapter()
    task = TaskSpec(
        id="nested-task",
        name="Nested Task",
        instruction="Fix bug in nested repo",
        docker_image="test:latest",
    )
    # Handoff created in nested subdirectory
    nested_dir = tmp_path / "app" / "repo" / ".agent-state"
    nested_dir.mkdir(parents=True, exist_ok=True)
    handoff_file = nested_dir / "handoff.md"
    handoff_file.write_text("# Active Handoff\n- Working Directory: app/repo\n", encoding="utf-8")

    mock_claude = MagicMock()
    mock_claude.run.return_value = DriverTelemetry(
        success=True,
        raw_response="Claude finished reproduction",
        duration_seconds=10.0,
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.01,
    )

    mock_agy = MagicMock()
    mock_agy.run.return_value = DriverTelemetry(
        success=True,
        raw_response="Agy implemented fix",
        duration_seconds=15.0,
        input_tokens=200,
        output_tokens=80,
        cost_usd=0.005,
    )

    with patch.object(adapter, "_run_gate_command", return_value=(True, 0, "pass")):
        result = adapter.run_task(
            task=task,
            workspace_path=tmp_path,
            driver=mock_agy,
            budget_sec=60.0,
            claude_driver=mock_claude,
        )

    assert result.success is True
    # Ensure mirrored to root
    root_handoff = tmp_path / ".agent-state" / "handoff.md"
    assert root_handoff.exists()
    assert "Active Handoff" in root_handoff.read_text(encoding="utf-8")


