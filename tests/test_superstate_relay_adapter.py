from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.superstate_relay import SuperstateRelayAdapter
from lab.engine.adapters.base import DriverTelemetry


def test_relay_adapter_initialization():
    adapter = SuperstateRelayAdapter()
    assert adapter.name == "superstate_relay"
    assert adapter.max_retries == 2


def test_relay_adapter_run_task_mocked(tmp_path: Path):
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
