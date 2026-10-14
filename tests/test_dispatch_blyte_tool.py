"""Tests for the dispatch_blyte tool in the container MCP server."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Any

import pytest

from lab.engine.drivers.container_exec_mcp import (
    DISPATCH_TOOL_DESCRIPTION,
    DISPATCH_TOOL_NAME,
    TOOL_NAME,
    ContainerExec,
    handle,
)


@pytest.fixture(autouse=True)
def _no_container_copy(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Dispatches copy the workdir and apply their changes back through the container
    (ContainerExec._sh); these tests have no container, so every script succeeds silently."""
    scripts: list[str] = []

    def fake_sh(self: ContainerExec, script: str) -> tuple[int, str]:
        scripts.append(script)
        return (0, "")

    monkeypatch.setattr(ContainerExec, "_sh", fake_sh)
    return scripts


def test_tool_absent_without_implementer_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """The tool is absent from tools/list and rejected in tools/call without BLYTE_IMPLEMENTER_MODEL."""
    monkeypatch.delenv("BLYTE_IMPLEMENTER_MODEL", raising=False)
    monkeypatch.setenv("BLYTE_EVAL_CONTAINER", "cnt-1")
    executor = ContainerExec()

    # Absent from tools/list
    resp = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, executor)
    assert resp is not None
    tool_names = [t["name"] for t in resp["result"]["tools"]]
    assert DISPATCH_TOOL_NAME not in tool_names
    assert tool_names == [TOOL_NAME]

    # Calling it is rejected as unknown tool
    call_resp = handle(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": DISPATCH_TOOL_NAME,
                "arguments": {"task": "fix bug", "gate": "pytest"},
            },
        },
        executor,
    )
    assert call_resp is not None
    assert "error" in call_resp
    assert f"Unknown tool: {DISPATCH_TOOL_NAME}" in call_resp["error"]["message"]


def test_tool_present_with_implementer_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """The tool is present in tools/list with correct schema when BLYTE_IMPLEMENTER_MODEL is set."""
    monkeypatch.setenv("BLYTE_IMPLEMENTER_MODEL", "gemini-3.8-flash-high")
    monkeypatch.setenv("BLYTE_EVAL_CONTAINER", "cnt-1")
    executor = ContainerExec()

    resp = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, executor)
    assert resp is not None
    tools = resp["result"]["tools"]
    dispatch_tools = [t for t in tools if t["name"] == DISPATCH_TOOL_NAME]
    assert len(dispatch_tools) == 1
    tool = dispatch_tools[0]
    assert tool["description"] == DISPATCH_TOOL_DESCRIPTION
    assert tool["inputSchema"]["required"] == ["task", "gate"]
    assert "task" in tool["inputSchema"]["properties"]
    assert "gate" in tool["inputSchema"]["properties"]
    assert "max_seconds" in tool["inputSchema"]["properties"]


def test_argv_contains_required_flags(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The argv contains --container, model, gate, --rollback=false and report path under BLYTE_DISPATCH_DIR."""
    monkeypatch.setenv("BLYTE_EVAL_CONTAINER", "cnt-test-123")
    monkeypatch.setenv("BLYTE_EVAL_WORKDIR", "/workspace")
    monkeypatch.setenv("BLYTE_IMPLEMENTER_MODEL", "gemini-3.8-flash-high")
    dispatch_dir = tmp_path / "dispatches"
    monkeypatch.setenv("BLYTE_DISPATCH_DIR", str(dispatch_dir))

    captured_cmd: list[str] = []

    def mock_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured_cmd.extend(cmd)
        report_idx = cmd.index("--report")
        report_file = Path(cmd[report_idx + 1])
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_file.write_text(json.dumps({"outcome": "verified"}))
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", mock_run)

    executor = ContainerExec()
    resp = handle(
        {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": DISPATCH_TOOL_NAME,
                "arguments": {
                    "task": "implement the feature",
                    "gate": "pytest tests/test_feature.py",
                    "max_seconds": 600,
                },
            },
        },
        executor,
    )

    assert resp is not None
    assert resp["result"]["isError"] is False

    # Check argv contents
    assert captured_cmd[0] == "blyte"

    container_idx = captured_cmd.index("--container")
    assert captured_cmd[container_idx + 1] == "cnt-test-123"

    # blyte works in the dispatch's own copy of /workspace, not in /workspace itself.
    workdir_idx = captured_cmd.index("--container-workdir")
    assert captured_cmd[workdir_idx + 1] == "/tmp/blyte-dispatch-1"

    model_idx = captured_cmd.index("--model")
    assert captured_cmd[model_idx + 1] == "gemini-3.8-flash-high"

    gate_idx = captured_cmd.index("--gate")
    assert captured_cmd[gate_idx + 1] == "pytest tests/test_feature.py"

    assert "--rollback=false" in captured_cmd

    seconds_idx = captured_cmd.index("--max-seconds")
    assert captured_cmd[seconds_idx + 1] == "600"

    # blyte's headless default of 25 turns ended every dispatch before its gate.
    turns_idx = captured_cmd.index("--max-turns")
    assert captured_cmd[turns_idx + 1] == "300"

    report_idx = captured_cmd.index("--report")
    report_arg = captured_cmd[report_idx + 1]
    assert report_arg.startswith(str(dispatch_dir))
    assert Path(report_arg).name == "dispatch-1.json"

    sep_idx = captured_cmd.index("--")
    assert captured_cmd[sep_idx + 1 :] == ["implement the feature"]


def test_dispatch_argv_includes_max_cost_when_env_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("BLYTE_EVAL_MAX_COST", "2.5")
    monkeypatch.setenv("BLYTE_EVAL_CONTAINER", "cnt-test-123")
    monkeypatch.setenv("BLYTE_EVAL_WORKDIR", "/workspace")
    monkeypatch.setenv("BLYTE_IMPLEMENTER_MODEL", "gemini-3.8-flash-high")
    monkeypatch.setenv("BLYTE_DISPATCH_DIR", str(tmp_path / "dispatches"))

    captured_cmd: list[str] = []

    def mock_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured_cmd.extend(cmd)
        report_idx = cmd.index("--report")
        report_file = Path(cmd[report_idx + 1])
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_file.write_text(json.dumps({"outcome": "verified"}))
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", mock_run)

    executor = ContainerExec()
    executor.dispatch("implement the feature", "pytest tests/test_feature.py")

    assert "--max-cost" in captured_cmd
    idx = captured_cmd.index("--max-cost")
    assert captured_cmd[idx + 1] == "2.5"
    assert idx < captured_cmd.index("--")


def test_dispatch_argv_omits_max_cost_when_env_unset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("BLYTE_EVAL_MAX_COST", raising=False)
    monkeypatch.setenv("BLYTE_EVAL_CONTAINER", "cnt-test-123")
    monkeypatch.setenv("BLYTE_EVAL_WORKDIR", "/workspace")
    monkeypatch.setenv("BLYTE_IMPLEMENTER_MODEL", "gemini-3.8-flash-high")
    monkeypatch.setenv("BLYTE_DISPATCH_DIR", str(tmp_path / "dispatches"))

    captured_cmd: list[str] = []

    def mock_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured_cmd.extend(cmd)
        report_idx = cmd.index("--report")
        report_file = Path(cmd[report_idx + 1])
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_file.write_text(json.dumps({"outcome": "verified"}))
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", mock_run)

    executor = ContainerExec()
    executor.dispatch("implement the feature", "pytest tests/test_feature.py")

    assert "--max-cost" not in captured_cmd


def test_report_on_disk_is_summarised(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A report on disk is summarised into {outcome, gate_attempts, gate_failures, turns, cost_usd, seconds, report}."""
    monkeypatch.setenv("BLYTE_EVAL_CONTAINER", "cnt-1")
    monkeypatch.setenv("BLYTE_IMPLEMENTER_MODEL", "gemini-3.8-flash-high")
    dispatch_dir = tmp_path / "reports"
    monkeypatch.setenv("BLYTE_DISPATCH_DIR", str(dispatch_dir))

    fake_report = {
        "outcome": "verified",
        "gate_attempts": 3,
        "gate_failures": ["test_first failed", "test_second failed"],
        "turns": 15,
        "cost_usd": 0.4215,
        "duration_seconds": 234.5,
    }

    def mock_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        report_file = Path(cmd[cmd.index("--report") + 1])
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_file.write_text(json.dumps(fake_report))
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", mock_run)

    executor = ContainerExec()
    resp = handle(
        {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {
                "name": DISPATCH_TOOL_NAME,
                "arguments": {"task": "fix edge case", "gate": "pytest"},
            },
        },
        executor,
    )

    assert resp is not None
    assert resp["result"]["isError"] is False
    summary = json.loads(resp["result"]["content"][0]["text"])

    assert summary["outcome"] == "verified"
    assert summary["gate_attempts"] == 3
    assert summary["gate_failures"] == ["test_first failed", "test_second failed"]
    assert summary["turns"] == 15
    assert summary["cost_usd"] == 0.4215
    assert summary["seconds"] == 234.5
    assert summary["report"] == str(dispatch_dir / "dispatch-1.json")


def test_missing_report_gives_outcome_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A missing report gives outcome: error."""
    monkeypatch.setenv("BLYTE_EVAL_CONTAINER", "cnt-1")
    monkeypatch.setenv("BLYTE_IMPLEMENTER_MODEL", "gemini-3.8-flash-high")
    dispatch_dir = tmp_path / "reports"
    monkeypatch.setenv("BLYTE_DISPATCH_DIR", str(dispatch_dir))

    def mock_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        # Do not write report; simulate crash or non-zero exit
        return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="failed to connect to model")

    monkeypatch.setattr(subprocess, "run", mock_run)

    executor = ContainerExec()
    resp = handle(
        {
            "jsonrpc": "2.0",
            "id": 12,
            "method": "tools/call",
            "params": {
                "name": DISPATCH_TOOL_NAME,
                "arguments": {"task": "do work", "gate": "pytest"},
            },
        },
        executor,
    )

    assert resp is not None
    assert resp["result"]["isError"] is False
    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload["outcome"] == "error"
    assert "error" in payload
    assert "failed to connect to model" in payload["error"]


def test_gate_failures_cut_to_1000_characters(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """gate_failures in the report are each cut to 1,000 characters."""
    monkeypatch.setenv("BLYTE_EVAL_CONTAINER", "cnt-1")
    monkeypatch.setenv("BLYTE_IMPLEMENTER_MODEL", "gemini-3.8-flash-high")
    dispatch_dir = tmp_path / "reports"
    monkeypatch.setenv("BLYTE_DISPATCH_DIR", str(dispatch_dir))

    long_failure_1 = "A" * 1500
    long_failure_2 = "B" * 3000
    short_failure = "C" * 200

    fake_report = {
        "outcome": "failed",
        "gate_attempts": 3,
        "gate_failures": [long_failure_1, long_failure_2, short_failure],
        "turns": 5,
        "cost_usd": 0.10,
        "duration_seconds": 45.0,
    }

    def mock_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        report_file = Path(cmd[cmd.index("--report") + 1])
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_file.write_text(json.dumps(fake_report))
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", mock_run)

    executor = ContainerExec()
    resp = handle(
        {
            "jsonrpc": "2.0",
            "id": 13,
            "method": "tools/call",
            "params": {
                "name": DISPATCH_TOOL_NAME,
                "arguments": {"task": "failing task", "gate": "pytest"},
            },
        },
        executor,
    )

    assert resp is not None
    summary = json.loads(resp["result"]["content"][0]["text"])
    assert summary["outcome"] == "failed"
    failures = summary["gate_failures"]
    assert len(failures) == 3
    assert len(failures[0]) == 1000
    assert failures[0] == "A" * 1000
    assert len(failures[1]) == 1000
    assert failures[1] == "B" * 1000
    assert len(failures[2]) == 200
    assert failures[2] == "C" * 200


def test_dispatch_count_increments_per_call(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """<n> in dispatch-<n>.json counts from 1 across multiple dispatches."""
    monkeypatch.setenv("BLYTE_EVAL_CONTAINER", "cnt-1")
    monkeypatch.setenv("BLYTE_IMPLEMENTER_MODEL", "gemini-3.8-flash-high")
    dispatch_dir = tmp_path / "reports"
    monkeypatch.setenv("BLYTE_DISPATCH_DIR", str(dispatch_dir))

    report_paths: list[str] = []

    def mock_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        report_arg = cmd[cmd.index("--report") + 1]
        report_paths.append(report_arg)
        report_file = Path(report_arg)
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_file.write_text(json.dumps({"outcome": "verified"}))
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", mock_run)

    executor = ContainerExec()

    handle(
        {
            "jsonrpc": "2.0",
            "id": 20,
            "method": "tools/call",
            "params": {"name": DISPATCH_TOOL_NAME, "arguments": {"task": "task 1", "gate": "gate 1"}},
        },
        executor,
    )
    handle(
        {
            "jsonrpc": "2.0",
            "id": 21,
            "method": "tools/call",
            "params": {"name": DISPATCH_TOOL_NAME, "arguments": {"task": "task 2", "gate": "gate 2"}},
        },
        executor,
    )

    assert len(report_paths) == 2
    assert Path(report_paths[0]).name == "dispatch-1.json"
    assert Path(report_paths[1]).name == "dispatch-2.json"


def test_two_container_exec_instances_claim_distinct_reports_and_copy_dirs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Two separate ContainerExec instances (as two hook processes make) get dispatch-1 and dispatch-2."""
    monkeypatch.setenv("BLYTE_EVAL_CONTAINER", "cnt-1")
    monkeypatch.setenv("BLYTE_IMPLEMENTER_MODEL", "gemini-3.8-flash-high")
    dispatch_dir = tmp_path / "reports"
    monkeypatch.setenv("BLYTE_DISPATCH_DIR", str(dispatch_dir))

    report_paths: list[Path] = []
    copy_dirs: list[str] = []

    def mock_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        report_arg = Path(cmd[cmd.index("--report") + 1])
        workdir_arg = cmd[cmd.index("--container-workdir") + 1]
        report_paths.append(report_arg)
        copy_dirs.append(workdir_arg)
        report_arg.write_text(json.dumps({"outcome": "verified"}), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", mock_run)

    exec1 = ContainerExec()
    out1, err1 = exec1.dispatch("task 1", "pytest")
    assert err1 is False and json.loads(out1)["outcome"] == "verified"

    exec2 = ContainerExec()
    out2, err2 = exec2.dispatch("task 2", "pytest")
    assert err2 is False and json.loads(out2)["outcome"] == "verified"

    assert [p.name for p in report_paths] == ["dispatch-1.json", "dispatch-2.json"]
    assert copy_dirs[0] != copy_dirs[1]
    assert copy_dirs == ["/tmp/blyte-dispatch-1", "/tmp/blyte-dispatch-2"]
    assert (dispatch_dir / "dispatch-1.events.log").is_file()
    assert (dispatch_dir / "dispatch-2.events.log").is_file()


def test_blyte_bin_from_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The blyte binary is $BLYTE_BIN or blyte on PATH."""
    monkeypatch.setenv("BLYTE_EVAL_CONTAINER", "cnt-1")
    monkeypatch.setenv("BLYTE_IMPLEMENTER_MODEL", "gemini-3.8-flash-high")
    monkeypatch.setenv("BLYTE_DISPATCH_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("BLYTE_BIN", "/custom/path/to/blyte")

    captured_cmd: list[str] = []

    def mock_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured_cmd.extend(cmd)
        report_file = Path(cmd[cmd.index("--report") + 1])
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_file.write_text(json.dumps({"outcome": "verified"}))
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", mock_run)

    executor = ContainerExec()
    handle(
        {
            "jsonrpc": "2.0",
            "id": 30,
            "method": "tools/call",
            "params": {"name": DISPATCH_TOOL_NAME, "arguments": {"task": "t", "gate": "g"}},
        },
        executor,
    )

    assert captured_cmd[0] == "/custom/path/to/blyte"


def test_missing_dispatch_dir_gives_outcome_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing BLYTE_DISPATCH_DIR gives outcome: error when calling dispatch."""
    monkeypatch.setenv("BLYTE_EVAL_CONTAINER", "cnt-1")
    monkeypatch.setenv("BLYTE_IMPLEMENTER_MODEL", "gemini-3.8-flash-high")
    monkeypatch.delenv("BLYTE_DISPATCH_DIR", raising=False)

    executor = ContainerExec()
    resp = handle(
        {
            "jsonrpc": "2.0",
            "id": 40,
            "method": "tools/call",
            "params": {"name": DISPATCH_TOOL_NAME, "arguments": {"task": "t", "gate": "g"}},
        },
        executor,
    )

    assert resp is not None
    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload["outcome"] == "error"
    assert "BLYTE_DISPATCH_DIR is not set" in payload["error"]


@pytest.mark.parametrize(
    "bad_args",
    [
        {},
        {"task": ""},
        {"task": "t"},
        {"gate": "g"},
        {"task": "t", "gate": ""},
        {"task": "t", "gate": "g", "max_seconds": -5},
        {"task": "t", "gate": "g", "max_seconds": "not-an-int"},
    ],
)
def test_dispatch_invalid_arguments_rejected(monkeypatch: pytest.MonkeyPatch, bad_args: dict[str, Any]) -> None:
    """Invalid arguments for dispatch_blyte are rejected with a JSON-RPC error."""
    monkeypatch.setenv("BLYTE_IMPLEMENTER_MODEL", "gemini-3.8-flash-high")
    executor = ContainerExec()
    resp = handle(
        {
            "jsonrpc": "2.0",
            "id": 50,
            "method": "tools/call",
            "params": {"name": DISPATCH_TOOL_NAME, "arguments": bad_args},
        },
        executor,
    )
    assert resp is not None
    assert "error" in resp
    assert resp["error"]["code"] == -32602


def test_dispatch_keeps_blytes_event_log(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Each dispatch saves blyte's event stream, so the commands it ran can be counted."""
    monkeypatch.setenv("BLYTE_EVAL_CONTAINER", "cnt-1")
    monkeypatch.setenv("BLYTE_IMPLEMENTER_MODEL", "gemini-3.8-flash-high")
    dispatch_dir = tmp_path / "reports"
    monkeypatch.setenv("BLYTE_DISPATCH_DIR", str(dispatch_dir))
    events = "[Turn 1] \n● bash python -m pytest -q -> exit 0\n"

    def mock_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        report_file = Path(cmd[cmd.index("--report") + 1])
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_file.write_text(json.dumps({"outcome": "verified"}))
        return subprocess.CompletedProcess(cmd, returncode=0, stdout=events, stderr="blyte: note")

    monkeypatch.setattr(subprocess, "run", mock_run)
    resp = handle(
        {
            "jsonrpc": "2.0",
            "id": 12,
            "method": "tools/call",
            "params": {"name": DISPATCH_TOOL_NAME, "arguments": {"task": "t", "gate": "g"}},
        },
        ContainerExec(),
    )
    assert resp is not None
    summary = json.loads(resp["result"]["content"][0]["text"])
    log_path = dispatch_dir / "dispatch-1.events.log"
    assert summary["events_log"] == str(log_path)
    text = log_path.read_text(encoding="utf-8")
    assert "● bash python -m pytest -q -> exit 0" in text
    assert "--- stderr ---\nblyte: note" in text
