"""Tests for the Antigravity CLI (agy) driver.

Driven against a stub executable so the contract is exercised without spending
money, requiring credentials, or launching real Docker containers.
"""

from __future__ import annotations

import json
from pathlib import Path
import stat

import pytest

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.drivers.agy_cli import (
    AgyCliDriver,
    AgyCliDriverError,
    estimate_cost_usd,
)


def _make_stub(tmp_path: Path, payload: dict | str, exit_code: int = 0) -> Path:
    """Write a fake `agy` that echoes a fixed JSON payload and records its argv."""
    body = payload if isinstance(payload, str) else json.dumps(payload)
    stub = tmp_path / "agy-stub"
    # Write argv separated by null bytes or a delimiter to preserve multi-line arguments
    stub.write_text(
        "#!/bin/sh\n"
        f'printf "%s\\0" "$@" > "{tmp_path}/argv.bin"\n'
        f"cat <<'EOF'\n{body}\nEOF\n"
        f"exit {exit_code}\n",
        encoding="utf-8",
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    return stub


def _read_argv(tmp_path: Path) -> list[str]:
    data = (tmp_path / "argv.bin").read_bytes()
    return [arg.decode("utf-8") for arg in data.split(b"\x00") if arg]


def _task(tmp_path: Path) -> TaskSpec:
    return TaskSpec(
        id="org/task",
        name="task",
        instruction="Fix the bug.",
        docker_image="img",
        task_dir=tmp_path,
    )


class FakeContainer:
    def __init__(self, container_id: str = "cnt-agy-12345") -> None:
        self.id = container_id
        self.name = f"eval-{container_id}"


def test_driver_parses_result_tokens_cost_and_session(tmp_path: Path) -> None:
    stub = _make_stub(
        tmp_path,
        {
            "conversation_id": "conv-1234",
            "status": "SUCCESS",
            "response": "Fixed the bug and ran the tests.",
            "duration_seconds": 4.2,
            "usage": {
                "input_tokens": 10000,
                "output_tokens": 2000,
                "thinking_tokens": 500,
            },
        },
    )
    driver = AgyCliDriver(cli_path=str(stub))
    telemetry = driver.run(task=_task(tmp_path), workspace_path=tmp_path)

    assert telemetry.success is True
    assert telemetry.raw_response == "Fixed the bug and ran the tests."
    assert telemetry.input_tokens == 10000
    assert telemetry.output_tokens == 2000
    assert telemetry.conversation_id == "conv-1234"
    assert telemetry.duration_seconds == pytest.approx(4.2)
    # Gemini 3.8 Flash pricing: $0.75/MTok in ($0.0075), $3.75/MTok out ($0.0075) -> $0.015
    assert telemetry.cost_usd == pytest.approx(0.015)


def test_driver_reports_cli_failure_rather_than_claiming_success(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, "Error occurred", exit_code=1)
    driver = AgyCliDriver(cli_path=str(stub))
    telemetry = driver.run(task=_task(tmp_path), workspace_path=tmp_path)

    assert telemetry.success is False
    assert "exited 1" in str(telemetry.error_message)


def test_driver_reports_unparseable_output_rather_than_claiming_success(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, "not json content")
    driver = AgyCliDriver(cli_path=str(stub))
    telemetry = driver.run(task=_task(tmp_path), workspace_path=tmp_path)

    assert telemetry.success is False
    assert "Could not parse" in str(telemetry.error_message)


def test_driver_honours_error_status(tmp_path: Path) -> None:
    stub = _make_stub(
        tmp_path,
        {
            "status": "ERROR",
            "response": "Rate limit exceeded or backend failure",
        },
    )
    driver = AgyCliDriver(cli_path=str(stub))
    telemetry = driver.run(task=_task(tmp_path), workspace_path=tmp_path)

    assert telemetry.success is False
    assert "Rate limit exceeded" in str(telemetry.error_message)


def test_driver_resumes_a_conversation(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, {"status": "SUCCESS", "response": "Continued", "conversation_id": "conv-existing"})
    driver = AgyCliDriver(cli_path=str(stub))
    driver.run(task=_task(tmp_path), workspace_path=tmp_path, conversation_id="conv-existing")

    argv = _read_argv(tmp_path)
    assert "--conversation" in argv
    assert argv[argv.index("--conversation") + 1] == "conv-existing"


def test_driver_passes_required_cli_flags(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, {"status": "SUCCESS", "response": "ok"})
    driver = AgyCliDriver(cli_path=str(stub), model="gemini-3.8-flash-high")
    driver.run(task=_task(tmp_path), workspace_path=tmp_path)

    argv = _read_argv(tmp_path)
    assert "--model" in argv
    assert argv[argv.index("--model") + 1] == "gemini-3.8-flash-high"
    assert "--output-format" in argv
    assert argv[argv.index("--output-format") + 1] == "json"
    assert "--dangerously-skip-permissions" in argv
    assert "--print" in argv


def test_container_mode_creates_bridge_script_and_steers_prompt(tmp_path: Path) -> None:
    container = FakeContainer("cnt-test-999")
    stub = _make_stub(tmp_path, {"status": "SUCCESS", "response": "done"})
    driver = AgyCliDriver(cli_path=str(stub))
    telemetry = driver.run(task=_task(tmp_path), workspace_path=tmp_path, container=container)

    assert telemetry.success is True

    # Check bridge script
    script = tmp_path / "run-in-container"
    assert script.is_file()
    assert bool(script.stat().st_mode & stat.S_IXUSR)
    content = script.read_text(encoding="utf-8")
    assert "exec docker exec -i -w /app cnt-test-999" in content

    # Check prompt steering
    argv = _read_argv(tmp_path)
    print_idx = argv.index("--print")
    prompt_sent = argv[print_idx + 1]
    assert "./run-in-container" in prompt_sent


def test_container_exec_can_be_disabled(tmp_path: Path) -> None:
    container = FakeContainer("cnt-test-999")
    stub = _make_stub(tmp_path, {"status": "SUCCESS", "response": "done"})
    driver = AgyCliDriver(cli_path=str(stub), container_exec=False)
    driver.run(task=_task(tmp_path), workspace_path=tmp_path, container=container)

    script = tmp_path / "run-in-container"
    assert not script.exists()


def test_driver_times_out_without_claiming_success(tmp_path: Path) -> None:
    slow = tmp_path / "slow"
    slow.write_text("#!/bin/sh\nsleep 5\n", encoding="utf-8")
    slow.chmod(slow.stat().st_mode | stat.S_IEXEC)

    driver = AgyCliDriver(cli_path=str(slow))
    telemetry = driver.run(task=_task(tmp_path), workspace_path=tmp_path, timeout_sec=1.0)

    assert telemetry.success is False
    assert "exceeded" in str(telemetry.error_message)


def test_driver_rejects_invalid_cli_path(tmp_path: Path) -> None:
    with pytest.raises(AgyCliDriverError, match="not an executable file"):
        AgyCliDriver(cli_path=str(tmp_path / "does-not-exist"))

    not_exec = tmp_path / "not-exec"
    not_exec.write_text("#!/bin/sh\n", encoding="utf-8")
    with pytest.raises(AgyCliDriverError, match="not an executable file"):
        AgyCliDriver(cli_path=str(not_exec))


def test_pricing_table_covers_gemini_models() -> None:
    assert estimate_cost_usd("gemini-3.8-flash-high", 1_000_000, 1_000_000) == pytest.approx(4.50)
    assert estimate_cost_usd("gemini-3.8-flash", 1_000_000, 1_000_000) == pytest.approx(4.50)
    assert estimate_cost_usd("unknown-model", 1_000_000, 1_000_000) == 0.0


def test_effort_variants_are_priced_as_their_base_model() -> None:
    """agy exposes one model per effort level; effort changes tokens, not price."""
    from lab.engine.drivers.agy_cli import base_model_name, estimate_cost_usd

    assert base_model_name("gemini-3.8-flash-low") == "gemini-3.8-flash"
    assert base_model_name("gemini-3.8-flash-high") == "gemini-3.8-flash"
    assert base_model_name("gemini-3.8-flash") == "gemini-3.8-flash"

    # All variants cost the same per token as the base entry.
    low = estimate_cost_usd("gemini-3.8-flash-low", 1_000_000, 0)
    high = estimate_cost_usd("gemini-3.8-flash-high", 1_000_000, 0)
    assert low == high == pytest.approx(0.75)


def test_unpriced_model_reports_zero_rather_than_a_guess() -> None:
    # Cost per solve is a headline metric; a fabricated rate would corrupt it.
    from lab.engine.drivers.agy_cli import estimate_cost_usd

    assert estimate_cost_usd("some-unlisted-model", 1_000_000, 1_000_000) == 0.0
