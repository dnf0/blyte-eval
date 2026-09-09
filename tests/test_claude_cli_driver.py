"""Tests for the live Claude Code CLI driver.

Driven against a stub executable so the contract is exercised without spending
money or requiring credentials.
"""

from __future__ import annotations

import json
from pathlib import Path
import stat

import pytest

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.drivers.claude_cli import (
    ClaudeCliDriver,
    ClaudeCliDriverError,
    estimate_cost_usd,
)


def _make_stub(tmp_path: Path, payload: dict | str, exit_code: int = 0) -> Path:
    """Write a fake `claude` that echoes a fixed payload and records its argv."""
    body = payload if isinstance(payload, str) else json.dumps(payload)
    stub = tmp_path / "claude-stub"
    stub.write_text(
        "#!/bin/sh\n"
        f'printf %s "$@" > "{tmp_path}/argv.txt"\n'
        f"cat <<'EOF'\n{body}\nEOF\n"
        f"exit {exit_code}\n",
        encoding="utf-8",
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    return stub


def _task(tmp_path: Path) -> TaskSpec:
    return TaskSpec(
        id="org/task",
        name="task",
        instruction="Fix the bug.",
        docker_image="img",
        task_dir=tmp_path,
    )


def test_driver_parses_result_tokens_cost_and_session(tmp_path: Path) -> None:
    stub = _make_stub(
        tmp_path,
        {
            "type": "result",
            "is_error": False,
            "result": "Fixed the bug and ran the tests.",
            "session_id": "sess-abc",
            "total_cost_usd": 0.42,
            "usage": {"input_tokens": 1200, "output_tokens": 340},
        },
    )
    driver = ClaudeCliDriver(cli_path=str(stub))
    telemetry = driver.run(task=_task(tmp_path), workspace_path=tmp_path)

    assert telemetry.success is True
    assert telemetry.raw_response == "Fixed the bug and ran the tests."
    assert telemetry.input_tokens == 1200
    assert telemetry.output_tokens == 340
    assert telemetry.cost_usd == 0.42
    assert telemetry.conversation_id == "sess-abc"


def test_driver_estimates_cost_when_cli_reports_none(tmp_path: Path) -> None:
    stub = _make_stub(
        tmp_path,
        {"result": "done", "usage": {"input_tokens": 1_000_000, "output_tokens": 1_000_000}},
    )
    driver = ClaudeCliDriver(cli_path=str(stub), model="claude-opus-5")
    telemetry = driver.run(task=_task(tmp_path), workspace_path=tmp_path)

    # Opus 5: $5/MTok in, $25/MTok out.
    assert telemetry.cost_usd == pytest.approx(30.0)


def test_driver_reports_cli_failure_rather_than_claiming_success(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, "boom", exit_code=3)
    driver = ClaudeCliDriver(cli_path=str(stub))
    telemetry = driver.run(task=_task(tmp_path), workspace_path=tmp_path)

    assert telemetry.success is False
    assert "exited 3" in str(telemetry.error_message)


def test_driver_reports_unparseable_output_rather_than_claiming_success(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, "this is not json")
    driver = ClaudeCliDriver(cli_path=str(stub))
    telemetry = driver.run(task=_task(tmp_path), workspace_path=tmp_path)

    assert telemetry.success is False
    assert "Could not parse" in str(telemetry.error_message)


def test_driver_honours_is_error_flag(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, {"is_error": True, "result": "context limit exceeded"})
    driver = ClaudeCliDriver(cli_path=str(stub))
    telemetry = driver.run(task=_task(tmp_path), workspace_path=tmp_path)

    assert telemetry.success is False
    assert "context limit" in str(telemetry.error_message)


def test_driver_resumes_a_session(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, {"result": "ok", "session_id": "sess-1"})
    driver = ClaudeCliDriver(cli_path=str(stub))
    driver.run(task=_task(tmp_path), workspace_path=tmp_path, conversation_id="sess-1")

    argv = (tmp_path / "argv.txt").read_text(encoding="utf-8")
    assert "--resume" in argv and "sess-1" in argv


def test_driver_times_out_without_claiming_success(tmp_path: Path) -> None:
    slow = tmp_path / "slow"
    slow.write_text("#!/bin/sh\nsleep 5\n", encoding="utf-8")
    slow.chmod(slow.stat().st_mode | stat.S_IEXEC)

    driver = ClaudeCliDriver(cli_path=str(slow))
    telemetry = driver.run(task=_task(tmp_path), workspace_path=tmp_path, timeout_sec=1.0)

    assert telemetry.success is False
    assert "exceeded" in str(telemetry.error_message)


def test_driver_rejects_a_cli_path_that_is_not_executable(tmp_path: Path) -> None:
    # Fail at construction, not once a cohort is already burning budget.
    with pytest.raises(ClaudeCliDriverError, match="not an executable file"):
        ClaudeCliDriver(cli_path=str(tmp_path / "does-not-exist"))

    not_executable = tmp_path / "claude-not-exec"
    not_executable.write_text("#!/bin/sh\n", encoding="utf-8")
    with pytest.raises(ClaudeCliDriverError, match="not an executable file"):
        ClaudeCliDriver(cli_path=str(not_executable))


def test_container_exec_instruction_is_opt_in(tmp_path: Path) -> None:
    class FakeContainer:
        id = "cnt-123"

    stub = _make_stub(tmp_path, {"result": "ok"})
    task = _task(tmp_path)

    off = ClaudeCliDriver(cli_path=str(stub))
    assert "docker exec" not in off._augment_prompt("do it", FakeContainer())

    on = ClaudeCliDriver(cli_path=str(stub), exec_in_container=True)
    augmented = on._augment_prompt("do it", FakeContainer())
    assert "docker exec cnt-123" in augmented
    assert task.instruction  # task unused otherwise; keeps the fixture meaningful


def test_pricing_table_covers_the_default_model() -> None:
    assert estimate_cost_usd("claude-opus-5", 1_000_000, 0) == pytest.approx(5.0)
    assert estimate_cost_usd("unknown-model", 1_000_000, 1_000_000) == 0.0
