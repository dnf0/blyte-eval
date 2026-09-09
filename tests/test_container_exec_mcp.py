"""Tests for the container-exec MCP server.

Protocol handling is tested in-process; the exec path is covered end-to-end
against real Docker in tests/test_docker_integration.py.
"""

from __future__ import annotations

from typing import Any

import pytest

from lab.engine.drivers.container_exec_mcp import (
    TOOL_NAME,
    ContainerExec,
    handle,
)


class _FakeExec(ContainerExec):
    def __init__(self, text: str = "exit_code=0\nok", is_error: bool = False) -> None:
        self.container_id = "cnt-1"
        self.default_workdir = "/app"
        self.timeout = 60
        self.max_output = 1000
        self._container = None
        self._text = text
        self._is_error = is_error
        self.calls: list[tuple[str, Any]] = []

    def run(self, command: str, workdir: str | None = None) -> tuple[str, bool]:
        self.calls.append((command, workdir))
        return self._text, self._is_error


def test_initialize_echoes_the_client_protocol_version() -> None:
    resp = handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-06-18"},
        },
        _FakeExec(),
    )
    assert resp is not None
    assert resp["result"]["protocolVersion"] == "2025-06-18"
    assert "tools" in resp["result"]["capabilities"]


def test_initialized_notification_gets_no_response() -> None:
    assert handle({"jsonrpc": "2.0", "method": "notifications/initialized"}, _FakeExec()) is None


def test_tools_list_exposes_only_the_exec_tool() -> None:
    resp = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, _FakeExec())
    assert resp is not None
    tools = resp["result"]["tools"]
    assert [t["name"] for t in tools] == [TOOL_NAME]
    assert tools[0]["inputSchema"]["required"] == ["command"]


def test_tools_call_runs_the_command() -> None:
    executor = _FakeExec(text="exit_code=0\nTASK-TOOLCHAIN")
    resp = handle(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": TOOL_NAME, "arguments": {"command": "go test ./..."}},
        },
        executor,
    )
    assert resp is not None
    assert resp["result"]["content"][0]["text"] == "exit_code=0\nTASK-TOOLCHAIN"
    assert resp["result"]["isError"] is False
    assert executor.calls == [("go test ./...", None)]


def test_a_failing_command_is_a_result_not_a_tool_error() -> None:
    # A failing test must come back as output the agent can read and act on.
    executor = _FakeExec(text="exit_code=1\nFAIL vm")
    resp = handle(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": TOOL_NAME, "arguments": {"command": "go test ./vm"}},
        },
        executor,
    )
    assert resp is not None
    assert resp["result"]["isError"] is False
    assert "exit_code=1" in resp["result"]["content"][0]["text"]


@pytest.mark.parametrize("bad", [{}, {"command": ""}, {"command": 5}])
def test_tools_call_rejects_a_missing_command(bad: dict[str, Any]) -> None:
    resp = handle(
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": TOOL_NAME, "arguments": bad}},
        _FakeExec(),
    )
    assert resp is not None and "error" in resp


def test_unknown_tool_is_rejected() -> None:
    resp = handle(
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {"name": "docker_run", "arguments": {}},
        },
        _FakeExec(),
    )
    assert resp is not None and "error" in resp
    assert "Unknown tool" in resp["error"]["message"]


def test_server_refuses_to_run_without_a_bound_container(monkeypatch: Any) -> None:
    monkeypatch.delenv("SUPERSTATE_EVAL_CONTAINER", raising=False)
    executor = ContainerExec()
    text, is_error = executor.run("echo hi")
    assert is_error is True
    assert "not set" in text


def test_container_is_fixed_at_launch(monkeypatch: Any) -> None:
    # The agent must not be able to choose which container it executes in.
    monkeypatch.setenv("SUPERSTATE_EVAL_CONTAINER", "cnt-fixed")
    executor = ContainerExec()
    assert executor.container_id == "cnt-fixed"
    schema_props = set()
    resp = handle({"jsonrpc": "2.0", "id": 7, "method": "tools/list"}, executor)
    assert resp is not None
    schema_props = set(resp["result"]["tools"][0]["inputSchema"]["properties"])
    assert schema_props == {"command", "workdir"}, (
        "no parameter may let the caller target a different container"
    )
