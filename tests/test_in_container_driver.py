"""Tests for the isolated in-container agent driver."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.drivers.in_container import (
    InContainerClaudeDriver,
    InContainerDriverError,
)


def _task() -> TaskSpec:
    return TaskSpec(id="org/t", name="t", instruction="fix it", docker_image="img")


def _container(exit_code: int = 0, stdout: bytes = b"{}", stderr: bytes = b"") -> MagicMock:
    c = MagicMock()
    c.exec_run.return_value = (exit_code, (stdout, stderr))
    return c


def test_driver_refuses_to_run_without_a_container() -> None:
    # The whole point of this driver is that the agent never touches the host.
    with pytest.raises(InContainerDriverError):
        InContainerClaudeDriver().run(task=_task(), workspace_path=Path("/ws"))


def test_driver_declares_itself_isolated() -> None:
    assert InContainerClaudeDriver().provides_isolated_execution is True


def test_prompt_is_passed_as_base64_so_content_cannot_alter_the_command() -> None:
    driver = InContainerClaudeDriver()
    nasty = "fix it'; rm -rf /; echo '"
    command = driver._shell_command(nasty, 900)

    encoded = base64.b64encode(nasty.encode()).decode()
    assert encoded in command
    assert "rm -rf" not in command


def test_turn_is_bounded_from_inside_the_container() -> None:
    # docker exec has no timeout of its own; without this a hung agent blocks forever.
    command = InContainerClaudeDriver()._shell_command("go", 900)
    assert "timeout 900s" in command


def test_timeout_exit_code_is_reported_as_a_timeout_not_a_crash() -> None:
    driver = InContainerClaudeDriver()
    telemetry = driver.run(
        task=_task(), workspace_path=Path("/ws"), container=_container(exit_code=124),
        timeout_sec=300,
    )
    assert telemetry.success is False
    assert "exceeded 300s" in str(telemetry.error_message)


def test_agent_runs_as_a_non_root_user() -> None:
    # The CLI refuses to bypass permission prompts as root, and an unattended
    # agent should not be root regardless.
    container = _container(stdout=json.dumps({"result": "ok"}).encode())
    InContainerClaudeDriver().run(
        task=_task(), workspace_path=Path("/ws"), container=container
    )
    assert container.exec_run.call_args.kwargs["user"] == "agent"


def test_successful_turn_reports_tokens_and_session() -> None:
    payload = {
        "result": "done",
        "session_id": "s-1",
        "total_cost_usd": 0.25,
        "usage": {"input_tokens": 100, "output_tokens": 20},
    }
    container = _container(stdout=json.dumps(payload).encode())
    telemetry = InContainerClaudeDriver().run(
        task=_task(), workspace_path=Path("/ws"), container=container
    )

    assert telemetry.success is True
    assert telemetry.input_tokens == 100
    assert telemetry.cost_usd == 0.25
    assert telemetry.conversation_id == "s-1"


def test_cost_is_estimated_only_from_a_known_rate() -> None:
    payload = {"result": "ok", "usage": {"input_tokens": 1_000_000, "output_tokens": 0}}
    container = _container(stdout=json.dumps(payload).encode())

    known = InContainerClaudeDriver(model="claude-opus-5").run(
        task=_task(), workspace_path=Path("/ws"), container=container
    )
    assert known.cost_usd == pytest.approx(5.0)

    unknown = InContainerClaudeDriver(model="some-unlisted-model").run(
        task=_task(), workspace_path=Path("/ws"), container=container
    )
    assert unknown.cost_usd == 0.0, "an unknown model must not get a guessed price"


def test_unparseable_output_is_a_failure_not_a_silent_success() -> None:
    container = _container(stdout=b"not json at all")
    telemetry = InContainerClaudeDriver().run(
        task=_task(), workspace_path=Path("/ws"), container=container
    )
    assert telemetry.success is False
    assert "Could not parse" in str(telemetry.error_message)


def test_resume_is_threaded_without_mutating_shared_state() -> None:
    # The runner drives arms on a thread pool; per-call state must stay per-call.
    driver = InContainerClaudeDriver(extra_args=["--verbose"])
    with_resume = driver._shell_command("go", 60, "sess-9")
    without = driver._shell_command("go", 60, None)

    assert "--resume sess-9" in with_resume
    assert "--resume" not in without
    assert driver.extra_args == ["--verbose"]
