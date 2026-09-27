"""Tests for the claude+blyte offload harness."""

from __future__ import annotations

import json
from pathlib import Path
import stat
from typing import Any

import pytest

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.vanilla import VanillaAdapter
from lab.engine.drivers.claude_cli import (
    CONTAINER_EXEC_SYSTEM_PROMPT,
    OFFLOAD_SYSTEM_PROMPT,
    ClaudeCliDriver,
)
from lab.engine.harnesses import (
    HarnessSpecError,
    build_harness,
    parse_harness_spec,
)


class FakeContainer:
    id = "cnt-test-123"


def _make_stub(tmp_path: Path, payload: dict[str, Any] | str, exit_code: int = 0) -> Path:
    """Write a fake claude CLI that records argv, stdin, and prints payload."""
    body = payload if isinstance(payload, str) else json.dumps(payload)
    stub = tmp_path / "claude-stub"
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
        name="test-task",
        instruction="Fix the bug.",
        docker_image="img",
        task_dir=tmp_path,
    )


# --- Spec parsing tests ---


def test_parse_harness_spec_valid() -> None:
    assert parse_harness_spec("claude+blyte[gemini-3.8-flash-high]") == (
        "claude+blyte",
        ["gemini-3.8-flash-high"],
    )
    assert parse_harness_spec("claude+blyte[claude-haiku-4-5]") == (
        "claude+blyte",
        ["claude-haiku-4-5"],
    )


@pytest.mark.parametrize(
    "spec",
    [
        "claude+blyte",
        "claude+blyte[]",
    ],
)
def test_parse_harness_spec_missing_option(spec: str) -> None:
    with pytest.raises(HarnessSpecError, match="exactly one implementer model option"):
        parse_harness_spec(spec)


@pytest.mark.parametrize(
    "spec",
    [
        "claude+blyte[gemini-3.8-flash-high,other-model]",
        "claude+blyte[a,b,c]",
    ],
)
def test_parse_harness_spec_multiple_options(spec: str) -> None:
    with pytest.raises(HarnessSpecError, match="exactly one implementer model option"):
        parse_harness_spec(spec)


# --- Build harness tests ---


def test_build_harness_claude_blyte(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The driver resolves the `claude` CLI when built; CI has none, so point it at a stub.
    stub = _make_stub(tmp_path, {"result": "ok"})
    monkeypatch.setattr("lab.engine.drivers.claude_cli.shutil.which", lambda name: str(stub))
    driver = build_harness(
        "claude+blyte[gemini-3.8-flash-high]",
        "claude-sonnet-5",
        report_dir=tmp_path,
    )
    assert isinstance(driver, ClaudeCliDriver)
    assert driver.model == "claude-sonnet-5"
    assert driver.implementer_model == "gemini-3.8-flash-high"
    assert driver.harness_name == "claude+blyte"
    assert driver.report_dir == tmp_path


def test_build_harness_claude_blyte_refuses_gemini_orchestrator() -> None:
    with pytest.raises(HarnessSpecError, match="Claude model"):
        build_harness(
            "claude+blyte[gemini-3.8-flash-high]",
            "gemini-3.8-flash-high",
        )


# --- Driver argv and env tests for both arms ---


def test_plain_claude_arm_argv_and_env(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, {"result": "ok", "total_cost_usd": 0.25})
    driver = ClaudeCliDriver(cli_path=str(stub), model="claude-sonnet-5")
    assert driver.harness_name == "claude-code"

    driver.run(task=_task(tmp_path), workspace_path=tmp_path, container=FakeContainer())

    argv = (tmp_path / "argv.txt").read_text(encoding="utf-8").splitlines()
    assert "--append-system-prompt" in argv
    idx = argv.index("--append-system-prompt")
    assert argv[idx + 1] == CONTAINER_EXEC_SYSTEM_PROMPT
    assert OFFLOAD_SYSTEM_PROMPT not in argv

    mcp_cfg_idx = argv.index("--mcp-config")
    config = json.loads(argv[mcp_cfg_idx + 1])
    server_env = config["mcpServers"]["task"]["env"]
    assert server_env["SUPERSTATE_EVAL_CONTAINER"] == "cnt-test-123"
    assert "PYTHONPATH" in server_env
    blyte_keys = [k for k in server_env if k.startswith("BLYTE_")]
    assert blyte_keys == [], f"Plain claude arm must have no BLYTE_* env vars, got: {blyte_keys}"


def test_claude_blyte_arm_argv_and_env(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    stub = _make_stub(tmp_path, {"result": "ok", "total_cost_usd": 0.25})
    driver = ClaudeCliDriver(
        cli_path=str(stub),
        model="claude-sonnet-5",
        implementer_model="gemini-3.8-flash-high",
        report_dir=reports_dir,
    )
    assert driver.harness_name == "claude+blyte"

    driver.run(task=_task(tmp_path), workspace_path=tmp_path, container=FakeContainer())

    argv = (tmp_path / "argv.txt").read_text(encoding="utf-8").splitlines()
    prompt_indices = [i for i, a in enumerate(argv) if a == "--append-system-prompt"]
    assert len(prompt_indices) == 2, "Expected container prompt and offload prompt"
    assert argv[prompt_indices[0] + 1] == CONTAINER_EXEC_SYSTEM_PROMPT
    assert argv[prompt_indices[1] + 1] == OFFLOAD_SYSTEM_PROMPT
    # Offload prompt appears after the container prompt
    assert prompt_indices[1] > prompt_indices[0]

    mcp_cfg_idx = argv.index("--mcp-config")
    config = json.loads(argv[mcp_cfg_idx + 1])
    server_env = config["mcpServers"]["task"]["env"]
    assert server_env["SUPERSTATE_EVAL_CONTAINER"] == "cnt-test-123"
    assert server_env["BLYTE_IMPLEMENTER_MODEL"] == "gemini-3.8-flash-high"
    assert "BLYTE_DISPATCH_DIR" in server_env
    dispatch_path = Path(server_env["BLYTE_DISPATCH_DIR"])
    assert dispatch_path.is_dir()
    assert reports_dir in dispatch_path.parents or dispatch_path.parent == reports_dir


# --- Cost aggregation tests ---


def test_cost_aggregation_from_two_fake_dispatch_reports(tmp_path: Path) -> None:
    dispatch_dir = tmp_path / "dispatches"
    dispatch_dir.mkdir()
    (dispatch_dir / "dispatch-1.json").write_text(
        json.dumps({"outcome": "gated", "cost_usd": 0.12, "turns": 2}),
        encoding="utf-8",
    )
    (dispatch_dir / "dispatch-2.json").write_text(
        json.dumps({"outcome": "passed", "cost_usd": 0.18, "turns": 3}),
        encoding="utf-8",
    )

    stub = _make_stub(
        tmp_path,
        {
            "type": "result",
            "is_error": False,
            "result": "Done with dispatches.",
            "total_cost_usd": 0.50,
            "usage": {"input_tokens": 1000, "output_tokens": 500},
        },
    )
    driver = ClaudeCliDriver(
        cli_path=str(stub),
        model="claude-sonnet-5",
        implementer_model="gemini-3.8-flash-high",
        dispatch_dir=dispatch_dir,
    )

    telemetry = driver.run(task=_task(tmp_path), workspace_path=tmp_path, container=FakeContainer())

    assert telemetry.success is True
    # Claude cost: 0.50, Implementer cost: 0.12 + 0.18 = 0.30, Total: 0.80
    assert telemetry.cost_usd == pytest.approx(0.80)
    extra = telemetry.metrics
    assert extra["frontier_cost_usd"] == pytest.approx(0.50)
    assert extra["implementer_cost_usd"] == pytest.approx(0.30)
    assert extra["dispatches"] == 2
    assert extra["dispatch_outcomes"] == ["gated", "passed"]

    # Also test through VanillaAdapter provenance propagation
    adapter = VanillaAdapter()
    res = adapter.execute(
        tmp_path,
        _task(tmp_path),
        driver,
        timeout_sec=60.0,
        container=FakeContainer(),
    )
    assert res.cost_usd == pytest.approx(0.80)
    assert res.provenance["frontier_cost_usd"] == pytest.approx(0.50)
    assert res.provenance["implementer_cost_usd"] == pytest.approx(0.30)
    assert res.provenance["dispatches"] == 2
    assert res.provenance["dispatch_outcomes"] == ["gated", "passed"]


def test_cost_aggregation_zero_dispatches(tmp_path: Path) -> None:
    dispatch_dir = tmp_path / "empty_dispatches"
    dispatch_dir.mkdir()

    stub = _make_stub(
        tmp_path,
        {
            "type": "result",
            "is_error": False,
            "result": "Done myself.",
            "total_cost_usd": 0.50,
        },
    )
    driver = ClaudeCliDriver(
        cli_path=str(stub),
        model="claude-sonnet-5",
        implementer_model="gemini-3.8-flash-high",
        dispatch_dir=dispatch_dir,
    )

    telemetry = driver.run(task=_task(tmp_path), workspace_path=tmp_path, container=FakeContainer())

    assert telemetry.success is True
    assert telemetry.cost_usd == pytest.approx(0.50)
    assert telemetry.metrics["frontier_cost_usd"] == pytest.approx(0.50)
    assert telemetry.metrics["implementer_cost_usd"] == pytest.approx(0.0)
    assert telemetry.metrics["dispatches"] == 0
    assert telemetry.metrics["dispatch_outcomes"] == []
