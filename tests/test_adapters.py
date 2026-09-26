"""Tests for Evaluation Arm Adapters: Vanilla and Superpowers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pytest

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.base import AgentDriver, DriverTelemetry, TaskRunResult
from lab.engine.adapters.superpowers import SuperpowersAdapter
from lab.engine.adapters.vanilla import VanillaAdapter


class MockDriver(AgentDriver):
    """Predictable mock driver simulating agent behavior."""

    def __init__(
        self,
        responses: list[DriverTelemetry] | None = None,
        side_effect: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.responses = list(responses) if responses is not None else []
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
            raw_response="Task complete.",
            duration_seconds=5.0,
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.001,
            conversation_id="conv-1",
        )


def _make_dummy_task(tmp_path: Path) -> TaskSpec:
    return TaskSpec(
        id="sample/test-task",
        name="test-task",
        instruction="Fix the bug in main.py.",
        docker_image="dummy:latest",
        task_dir=tmp_path,
    )


def test_vanilla_adapter_cleans_workspace_and_executes(tmp_path: Path) -> None:
    # Setup dirty workspace with legacy rules and skills
    (tmp_path / "AGENTS.md").write_text("legacy rules", encoding="utf-8")
    skills_dir = tmp_path / ".agents" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "dummy.md").write_text("dummy", encoding="utf-8")

    driver = MockDriver(
        [
            DriverTelemetry(
                success=True,
                raw_response="Fixed the bug in main.py.",
                duration_seconds=12.0,
                input_tokens=500,
                output_tokens=100,
                cost_usd=0.005,
                conversation_id="conv-vanilla",
            )
        ]
    )
    adapter = VanillaAdapter()
    result = adapter.execute(tmp_path, _make_dummy_task(tmp_path), driver)

    assert isinstance(result, TaskRunResult)
    assert result.harness_name == "vanilla"
    assert result.success is True
    assert result.duration_seconds == 12.0
    assert not (tmp_path / "AGENTS.md").exists(), "Vanilla must remove AGENTS.md"
    assert not skills_dir.exists(), "Vanilla must remove .agents/skills"
    assert len(driver.calls) == 1
    assert driver.calls[0]["prompt"] == "Fix the bug in main.py."


def test_superpowers_adapter_installs_guidance_and_handles_approval(tmp_path: Path) -> None:
    # Driver asks for approval on Turn 1, then completes on Turn 2
    driver = MockDriver(
        [
            DriverTelemetry(
                success=True,
                raw_response="Should I proceed with Option 1?",
                duration_seconds=10.0,
                input_tokens=200,
                output_tokens=50,
                cost_usd=0.002,
                conversation_id="conv-sp",
            ),
            DriverTelemetry(
                success=True,
                raw_response="Implementation finished.",
                duration_seconds=15.0,
                input_tokens=300,
                output_tokens=80,
                cost_usd=0.003,
                conversation_id="conv-sp",
            ),
        ]
    )
    adapter = SuperpowersAdapter()
    result = adapter.execute(tmp_path, _make_dummy_task(tmp_path), driver)

    assert result.harness_name == "superpowers"
    assert result.success is True
    assert result.turns == 2
    assert result.duration_seconds == 25.0
    assert (tmp_path / "AGENTS.md").exists(), "Superpowers must install AGENTS.md"
    assert "Proceed with the recommended option" in str(driver.calls[1]["prompt"])


def test_budget_hook_extends_budget_mid_run(tmp_path: Path) -> None:
    # A run that earns progress must actually get the extra runway, not merely
    # have it recorded after the fact.
    from lab.engine.budget_policy import BudgetPolicy

    policy = BudgetPolicy(base_timeout_sec=10.0, lease_extension_sec=100.0)

    def budget_hook() -> float:
        policy.record_milestone_progress("commit")
        return policy.current_granted_budget_sec

    # Each turn burns 8s; without extensions the second turn would exceed the 10s budget.
    driver = MockDriver(
        [
            DriverTelemetry(success=True, raw_response="Should I proceed?", duration_seconds=8.0),
            DriverTelemetry(success=True, raw_response="Should I proceed?", duration_seconds=8.0),
            DriverTelemetry(success=True, raw_response="All done.", duration_seconds=8.0),
        ]
    )
    result = VanillaAdapter().execute(
        tmp_path, _make_dummy_task(tmp_path), driver, timeout_sec=10.0, budget_hook=budget_hook
    )

    assert result.success is True
    assert result.turns == 3
    assert policy.extensions_granted_count == 3


def test_adapter_passes_container_handle_to_driver(tmp_path: Path) -> None:
    sentinel = object()
    driver = MockDriver([DriverTelemetry(success=True, raw_response="Done.", duration_seconds=1.0)])
    VanillaAdapter().execute(
        tmp_path, _make_dummy_task(tmp_path), driver, container=sentinel
    )
    assert driver.calls[0]["container"] is sentinel


def test_turn_loop_breaker_reports_failure(tmp_path: Path) -> None:
    # The turn cap is a loop-breaker, not a budget. Set it explicitly rather than
    # depending on the production value, which must stay high enough not to bind.
    driver = MockDriver(
        [
            DriverTelemetry(
                success=True,
                raw_response="Should I proceed with Option 1?",
                duration_seconds=1.0,
            )
            for _ in range(12)
        ]
    )
    adapter = VanillaAdapter()
    adapter.max_turns = 4
    result = adapter.execute(tmp_path, _make_dummy_task(tmp_path), driver)

    assert result.success is False
    assert result.turns == 4
    assert "Exhausted maximum turns (4)" in str(result.error_message)


def test_production_turn_caps_do_not_bind_on_ordinary_runs() -> None:
    # Guard against a future edit quietly turning the loop-breakers back into
    # budgets that decide evaluation outcomes.
    assert VanillaAdapter().max_turns >= 50
    assert SuperpowersAdapter().max_turns >= 50


def test_recorder_captures_prompts_and_responses(tmp_path: Path) -> None:
    """The trace must explain a failure, not merely report one."""
    import json

    from lab.engine.trace import RunRecorder

    logs = tmp_path / "logs"
    recorder = RunRecorder(logs_dir=logs, task_id="t", arm="vanilla")

    driver = MockDriver(
        [DriverTelemetry(success=True, raw_response="Did the thing.", duration_seconds=1.0)]
    )
    result = VanillaAdapter().execute(
        tmp_path, _make_dummy_task(tmp_path), driver, recorder=recorder
    )

    assert result.success is True

    turns = [json.loads(ln) for ln in (logs / "transcript.jsonl").read_text().splitlines()]
    assert turns[0]["phase"] == "implementation"
    assert turns[0]["response"] == "Did the thing."

    run_record_path = recorder.write_run_record(result)
    assert run_record_path is not None
    record = json.loads(run_record_path.read_text())
    assert record["task_id"] == "t"
    assert record["arm"] == "vanilla"


def test_is_transient_stream_interruption_detection() -> None:
    """Verify is_transient_stream_interruption correctly classifies transport vs logical errors."""
    from lab.engine.adapters.base import is_transient_stream_interruption

    assert is_transient_stream_interruption("The stream was interrupted. Please continue the task you were working on.")
    assert is_transient_stream_interruption("connection reset by peer")
    assert is_transient_stream_interruption("gRPC deadline exceeded during token streaming")
    assert is_transient_stream_interruption("HTTP 503 Service Unavailable from upstream API")
    assert is_transient_stream_interruption("Transport error: socket closed unexpectedly")
    assert not is_transient_stream_interruption("Fatal syntax error in main.py: line 42")
    assert not is_transient_stream_interruption("AssertionError at test_runner.py:503: test failed")
    assert not is_transient_stream_interruption("Process exited with code 503")
    assert not is_transient_stream_interruption("Timed out after 3600.0s")
    assert not is_transient_stream_interruption(None)
    assert not is_transient_stream_interruption("")


def test_turn_based_adapter_recovers_from_transient_stream_interruption(tmp_path: Path) -> None:
    """Verify TurnBasedAdapter resumes conversation when a transient API stream drop occurs."""
    task = _make_dummy_task(tmp_path)
    adapter = VanillaAdapter(max_turns=5)

    driver = MockDriver(
        [
            DriverTelemetry(
                success=False,
                raw_response="",
                error_message="The stream was interrupted. Please continue the task you were working on.",
                duration_seconds=30.0,
                input_tokens=500,
                output_tokens=100,
                cost_usd=0.01,
                conversation_id="conv-transient-1",
            ),
            DriverTelemetry(
                success=True,
                raw_response="Task complete.",
                duration_seconds=20.0,
                input_tokens=300,
                output_tokens=50,
                cost_usd=0.005,
                conversation_id="conv-transient-1",
            ),
        ]
    )

    result = adapter.execute(tmp_path, task, driver, timeout_sec=300.0)

    assert result.success is True
    assert result.turns == 2
    assert result.duration_seconds == 50.0
    assert result.input_tokens == 800
    assert result.output_tokens == 150
    assert result.cost_usd == pytest.approx(0.015)
    assert len(driver.calls) == 2
    # Second turn must resume the interrupted conversation
    assert driver.calls[0]["conversation_id"] is None
    assert driver.calls[1]["conversation_id"] == "conv-transient-1"
    assert "stream was interrupted" in str(driver.calls[1]["prompt"]).lower()


def test_turn_based_adapter_recovers_without_conversation_id(tmp_path: Path) -> None:
    """Verify TurnBasedAdapter retries with initial prompt when conversation_id is None."""
    task = _make_dummy_task(tmp_path)
    adapter = VanillaAdapter(max_turns=5)

    driver = MockDriver(
        [
            DriverTelemetry(
                success=False,
                raw_response="",
                error_message="Connection reset by peer",
                duration_seconds=10.0,
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                conversation_id=None,
            ),
            DriverTelemetry(
                success=True,
                raw_response="Fixed the bug in main.py.",
                duration_seconds=15.0,
                input_tokens=300,
                output_tokens=50,
                cost_usd=0.005,
                conversation_id="conv-recovered-2",
            ),
        ]
    )

    result = adapter.execute(tmp_path, task, driver, timeout_sec=300.0)

    assert result.success is True
    assert result.turns == 2
    assert len(driver.calls) == 2
    # When conversation_id was None, it must re-send the task instruction, NOT a resume string
    assert driver.calls[1]["conversation_id"] is None
    assert driver.calls[1]["prompt"] == "Fix the bug in main.py."


def test_turn_based_adapter_aborts_when_stream_retries_exhausted(tmp_path: Path) -> None:
    """Verify TurnBasedAdapter halts after exhausting max_stream_retries."""
    task = _make_dummy_task(tmp_path)
    adapter = VanillaAdapter(max_turns=10, max_stream_retries=2)

    driver = MockDriver(
        [
            DriverTelemetry(
                success=False,
                raw_response="",
                error_message="stream was interrupted",
                duration_seconds=10.0,
                conversation_id="conv-drop",
            ),
            DriverTelemetry(
                success=False,
                raw_response="",
                error_message="stream was interrupted",
                duration_seconds=10.0,
                conversation_id="conv-drop",
            ),
            DriverTelemetry(
                success=False,
                raw_response="",
                error_message="stream was interrupted",
                duration_seconds=10.0,
                conversation_id="conv-drop",
            ),
        ]
    )

    result = adapter.execute(tmp_path, task, driver, timeout_sec=300.0)

    assert result.success is False
    assert result.turns == 3  # 1 initial + 2 retries
    assert "stream was interrupted" in str(result.error_message)


def test_turn_based_adapter_does_not_retry_non_transient_failure(tmp_path: Path) -> None:
    """Verify TurnBasedAdapter does not retry non-transient model/logic failures."""
    task = _make_dummy_task(tmp_path)
    adapter = VanillaAdapter(max_turns=5)

    driver = MockDriver(
        [
            DriverTelemetry(
                success=False,
                raw_response="",
                error_message="Fatal error: compilation failed with exit code 2",
                duration_seconds=15.0,
                input_tokens=200,
                output_tokens=50,
                cost_usd=0.002,
                conversation_id="conv-fail-1",
            ),
        ]
    )

    result = adapter.execute(tmp_path, task, driver, timeout_sec=300.0)

    assert result.success is False
    assert result.turns == 1
    assert "compilation failed" in str(result.error_message)
    assert len(driver.calls) == 1
