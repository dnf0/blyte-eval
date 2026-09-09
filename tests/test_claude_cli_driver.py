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
    # Records argv one-per-line and the piped prompt, then emits the payload.
    # It also mimics the real CLI's refusal to run with no prompt on stdin.
    stub.write_text(
        "#!/bin/sh\n"
        f'for a in "$@"; do echo "$a"; done > "{tmp_path}/argv.txt"\n'
        f'cat > "{tmp_path}/stdin.txt"\n'
        f'if [ ! -s "{tmp_path}/stdin.txt" ]; then\n'
        '  echo "Error: Input must be provided either through stdin or as a prompt argument" >&2\n'
        "  exit 1\n"
        "fi\n"
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

    argv = (tmp_path / "argv.txt").read_text(encoding="utf-8").splitlines()
    assert "--resume" in argv and "sess-1" in argv


def test_prompt_is_piped_not_positional(tmp_path: Path) -> None:
    """Regression: several CLI flags are variadic (--add-dir, --disallowedTools,
    --mcp-config), so a trailing positional prompt is swallowed as another value
    and the CLI exits 1 with "Input must be provided"."""
    stub = _make_stub(tmp_path, {"result": "ok"})
    driver = ClaudeCliDriver(cli_path=str(stub))
    telemetry = driver.run(
        task=_task(tmp_path), workspace_path=tmp_path, prompt_override="fix the bug"
    )

    assert telemetry.success is True, telemetry.error_message
    assert (tmp_path / "stdin.txt").read_text(encoding="utf-8") == "fix the bug"

    argv = (tmp_path / "argv.txt").read_text(encoding="utf-8").splitlines()
    assert "fix the bug" not in argv, "prompt must not be a positional argument"
    # Nothing positional may trail a variadic flag.
    assert argv[-2] == "--add-dir" and argv[-1] == str(tmp_path)


def test_container_mode_removes_host_bash_and_wires_mcp(tmp_path: Path) -> None:
    """A host shell can reach the Docker daemon and read the held-out tests."""

    class FakeContainer:
        id = "cnt-abc123"

    stub = _make_stub(tmp_path, {"result": "ok"})
    driver = ClaudeCliDriver(cli_path=str(stub))
    driver.run(task=_task(tmp_path), workspace_path=tmp_path, container=FakeContainer())

    argv = (tmp_path / "argv.txt").read_text(encoding="utf-8").splitlines()
    assert "--disallowedTools" in argv
    assert "Bash" in argv
    assert "--strict-mcp-config" in argv, "operator MCP servers must not leak into a run"

    config = json.loads(argv[argv.index("--mcp-config") + 1])
    server = config["mcpServers"]["task"]
    assert server["args"] == ["-m", "lab.engine.drivers.container_exec_mcp"]
    assert server["env"]["SUPERSTATE_EVAL_CONTAINER"] == "cnt-abc123"


def test_no_container_leaves_bash_alone(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, {"result": "ok"})
    driver = ClaudeCliDriver(cli_path=str(stub))
    driver.run(task=_task(tmp_path), workspace_path=tmp_path)

    argv = (tmp_path / "argv.txt").read_text(encoding="utf-8").splitlines()
    assert "--disallowedTools" not in argv
    assert "--mcp-config" not in argv


def test_container_exec_can_be_disabled(tmp_path: Path) -> None:
    class FakeContainer:
        id = "cnt-abc123"

    stub = _make_stub(tmp_path, {"result": "ok"})
    driver = ClaudeCliDriver(cli_path=str(stub), container_exec=False)
    driver.run(task=_task(tmp_path), workspace_path=tmp_path, container=FakeContainer())

    argv = (tmp_path / "argv.txt").read_text(encoding="utf-8").splitlines()
    assert "--disallowedTools" not in argv


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


def test_pricing_table_covers_the_default_model() -> None:
    assert estimate_cost_usd("claude-opus-5", 1_000_000, 0) == pytest.approx(5.0)
    assert estimate_cost_usd("unknown-model", 1_000_000, 1_000_000) == 0.0
