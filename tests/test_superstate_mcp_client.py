"""Tests for SuperstateMcpClient.

Verifies stdio JSON-RPC MCP protocol handshake, tool execution, error handling,
context manager lifecycle, domain wrapper methods, and live integration with
the superstate binary.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import threading
from typing import Any
import pytest

from lab.engine.mcp.client import (
    McpError,
    McpProcessError,
    McpRpcError,
    McpTimeoutError,
    SuperstateMcpClient,
)


class FakeMcpServerProcess:
    """Mock subprocess simulating stdio JSON-RPC MCP server."""

    def __init__(self, responses: dict[str, Any] | None = None) -> None:
        self.stdin = FakePipe()
        self.stdout = FakePipe()
        self.stderr = FakePipe()
        self.returncode: int | None = None
        self._terminated = False
        self.responses = responses or {}

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self._terminated = True
        self.returncode = 0

    def kill(self) -> None:
        self._terminated = True
        self.returncode = -9

    def wait(self, timeout: float | None = None) -> int:
        self._terminated = True
        self.returncode = 0
        return 0


class FakePipe:
    """Mock file-like pipe supporting write and readline."""

    def __init__(self) -> None:
        self._buffer: list[str] = []
        self._lock = threading.Lock()
        self._closed = False

    def write(self, data: str) -> int:
        with self._lock:
            self._buffer.append(data)
        return len(data)

    def flush(self) -> None:
        pass

    def readline(self) -> str:
        with self._lock:
            if not self._buffer:
                return ""
            line = self._buffer.pop(0)
            return line

    def close(self) -> None:
        self._closed = True


def test_custom_exceptions_inheritance() -> None:
    """Verify custom exception hierarchy."""
    assert issubclass(McpRpcError, McpError)
    assert issubclass(McpProcessError, McpError)
    assert issubclass(McpTimeoutError, McpError)

    err = McpRpcError("RPC failed", code=-32603, data={"hint": "error"})
    assert err.code == -32603
    assert err.data == {"hint": "error"}
    assert "RPC failed" in str(err)


def test_binary_path_resolution(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verify resolution across explicit path, cargo, local bin, and PATH."""
    fake_bin = tmp_path / "custom-superstate"
    fake_bin.touch(mode=0o755)

    # 1. Explicit path
    client = SuperstateMcpClient(superstate_bin=fake_bin)
    assert client.superstate_bin == fake_bin

    # 2. PATH resolution fallback
    monkeypatch.setattr("shutil.which", lambda cmd: str(fake_bin) if cmd == "superstate" else None)
    monkeypatch.setattr(Path, "is_file", lambda p: False)
    client_auto = SuperstateMcpClient()
    assert client_auto.superstate_bin == fake_bin

    # 3. Missing binary raises McpProcessError
    monkeypatch.setattr("shutil.which", lambda cmd: None)
    with pytest.raises(McpProcessError, match="Could not resolve superstate binary"):
        SuperstateMcpClient()


def test_handshake_and_tool_caching(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify initialize, initialized notification, tools/list, and caching 25 tools."""
    server = FakeMcpServerProcess()

    def mock_popen(*args: Any, **kwargs: Any) -> FakeMcpServerProcess:
        init_resp = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "superstate-mcp", "version": "0.1.0"},
            },
        }
        tools_list_resp = {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {"tools": [{"name": f"tool_{i}", "inputSchema": {}} for i in range(25)]},
        }
        server.stdout._buffer.append(json.dumps(init_resp) + "\n")
        server.stdout._buffer.append(json.dumps(tools_list_resp) + "\n")
        return server

    monkeypatch.setattr(subprocess, "Popen", mock_popen)

    client = SuperstateMcpClient(superstate_bin="/mock/superstate")
    client.start()

    assert client.server_info == {"name": "superstate-mcp", "version": "0.1.0"}
    assert len(client.tools) == 25
    assert "tool_0" in client.tools
    assert "tool_24" in client.tools

    written = "".join(server.stdin._buffer)
    lines = [json.loads(line) for line in written.strip().split("\n") if line.strip()]

    assert lines[0]["method"] == "initialize"
    assert lines[0]["params"]["protocolVersion"] == "2024-11-05"
    assert lines[1]["method"] == "notifications/initialized"
    assert "id" not in lines[1]
    assert lines[2]["method"] == "tools/list"

    client.stop()
    assert server._terminated is True


def test_call_tool_parses_content_and_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify call_tool parses text and nested json in result.content."""
    server = FakeMcpServerProcess()
    json_text = json.dumps({"status": "in_progress", "step": 1})

    def mock_popen(*args: Any, **kwargs: Any) -> FakeMcpServerProcess:
        server.stdout._buffer.append(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "serverInfo": {},
                    },
                }
            )
            + "\n"
        )
        server.stdout._buffer.append(
            json.dumps({"jsonrpc": "2.0", "id": 2, "result": {"tools": []}}) + "\n"
        )
        server.stdout._buffer.append(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "result": {
                        "content": [{"type": "text", "text": json_text}],
                        "isError": False,
                    },
                }
            )
            + "\n"
        )
        return server

    monkeypatch.setattr(subprocess, "Popen", mock_popen)

    with SuperstateMcpClient(superstate_bin="/mock/superstate") as client:
        result = client.call_tool("state_status", {"json": True})
        assert result["isError"] is False
        assert "content" in result
        assert result["parsed_json"] == {"status": "in_progress", "step": 1}
        assert result["text"] == json_text


def test_call_tool_raises_rpc_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify call_tool raises McpRpcError on JSON-RPC error payload."""
    server = FakeMcpServerProcess()

    def mock_popen(*args: Any, **kwargs: Any) -> FakeMcpServerProcess:
        server.stdout._buffer.append(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "serverInfo": {},
                    },
                }
            )
            + "\n"
        )
        server.stdout._buffer.append(
            json.dumps({"jsonrpc": "2.0", "id": 2, "result": {"tools": []}}) + "\n"
        )
        server.stdout._buffer.append(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "error": {"code": -32603, "message": "Internal error in tool"},
                }
            )
            + "\n"
        )
        return server

    monkeypatch.setattr(subprocess, "Popen", mock_popen)

    with SuperstateMcpClient(superstate_bin="/mock/superstate") as client:
        with pytest.raises(McpRpcError, match="Internal error in tool") as exc_info:
            client.call_tool("failing_tool", {})
        assert exc_info.value.code == -32603


def test_context_manager_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify context manager automatically starts and terminates child process."""
    server = FakeMcpServerProcess()

    def mock_popen(*args: Any, **kwargs: Any) -> FakeMcpServerProcess:
        server.stdout._buffer.append(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "serverInfo": {},
                    },
                }
            )
            + "\n"
        )
        server.stdout._buffer.append(
            json.dumps({"jsonrpc": "2.0", "id": 2, "result": {"tools": []}}) + "\n"
        )
        return server

    monkeypatch.setattr(subprocess, "Popen", mock_popen)

    client = SuperstateMcpClient(superstate_bin="/mock/superstate")
    assert client.is_running is False

    with client:
        assert client.is_running is True

    assert client.is_running is False
    assert server._terminated is True


def test_domain_wrapper_methods(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verify all domain helper wrappers delegate to call_tool correctly."""
    client = SuperstateMcpClient(superstate_bin="/mock/superstate")
    client._initialized = True
    client._tools = {}

    calls: list[tuple[str, dict[str, Any]]] = []

    def mock_call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        calls.append((name, arguments))
        if name == "state_init":
            return {"status": "success", "result": {"status": "success"}}
        elif name == "state_prompt":
            return {"prompt": "Turnkey prompt content", "text": "Turnkey prompt content"}
        elif name == "state_next":
            return {"status": "success", "result": {"step": 2}}
        elif name == "state_status":
            return {"status": "in_progress", "parsed_json": {"step": 1, "status": "in_progress"}}
        elif name == "state_ready":
            return {"ready": ["Task 1: Build"], "parsed_json": {"ready": ["Task 1: Build"]}}
        elif name == "state_doctor":
            return {"is_healthy": True, "issues": []}
        elif name == "state_exec":
            return {"passed": True, "output": "ok"}
        elif name == "state_note":
            return {"note_recorded": True}
        elif name == "worktree_clean":
            return {"cleaned": 1, "branches": ["wt-1"]}
        return {}

    monkeypatch.setattr(client, "call_tool", mock_call_tool)

    repo = tmp_path / "repo"
    plan = repo / "plan.md"

    # state_init
    assert client.state_init(plan=plan, repo=repo, no_worktree=True) is True
    assert calls[-1][0] == "state_init"
    assert calls[-1][1]["plan"] == str(plan)
    assert calls[-1][1]["no_worktree"] is True

    # state_prompt
    prompt = client.state_prompt(repo=repo, with_graph=True, task="Task 1")
    assert prompt == "Turnkey prompt content"
    assert calls[-1][0] == "state_prompt"
    assert calls[-1][1]["with_graph"] is True
    assert calls[-1][1]["task"] == "Task 1"

    # state_next
    assert client.state_next(repo=repo, verify_cmd="pytest", verify_git_clean=True) is True
    assert calls[-1][0] == "state_next"
    assert calls[-1][1]["verify_cmd"] == "pytest"
    assert calls[-1][1]["verify_git_clean"] is True

    # state_status
    status = client.state_status(repo=repo)
    assert status.get("status") == "in_progress"
    assert calls[-1][0] == "state_status"

    # state_ready
    ready = client.state_ready(repo=repo)
    assert ready == ["Task 1: Build"]
    assert calls[-1][0] == "state_ready"

    # state_doctor
    doc = client.state_doctor(repo=repo, repair=True)
    assert doc.get("is_healthy") is True
    assert calls[-1][0] == "state_doctor"
    assert calls[-1][1]["repair"] is True

    # state_exec
    exec_res = client.state_exec(repo=repo, cmd="pytest", advance=True)
    assert exec_res.get("passed") is True
    assert calls[-1][0] == "state_exec"
    assert calls[-1][1]["verify_cmd"] == "pytest"

    # state_note
    assert client.state_note(repo=repo, message="Root cause found") is True
    assert calls[-1][0] == "state_note"
    assert calls[-1][1]["note"] == "Root cause found"

    # worktree_clean
    cleaned = client.worktree_clean(repo=repo, force=True)
    assert cleaned.get("cleaned") == 1
    assert calls[-1][0] == "worktree_clean"
    assert calls[-1][1]["force"] is True


def test_real_superstate_mcp_integration(tmp_path: Path) -> None:
    """Live integration test against the local superstate binary."""
    try:
        client = SuperstateMcpClient(cwd=tmp_path)
    except McpProcessError:
        pytest.skip("superstate binary not found on this system")

    # Initialize a git repo in tmp_path
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=tmp_path, check=True)

    plan_file = tmp_path / "plan.md"
    plan_file.write_text(
        "# Plan\n\n### Task 1: Initialize baseline\nVerification Command: `echo baseline_ok`\n",
        encoding="utf-8",
    )

    with client:
        # Handshake verification
        assert len(client.tools) == 25
        assert "state_init" in client.tools
        assert "worktree_clean" in client.tools

        # state_init
        init_ok = client.state_init(plan=plan_file, repo=tmp_path, no_worktree=True)
        assert init_ok is True

        # state_status
        status = client.state_status(repo=tmp_path)
        assert status.get("status") == "in_progress"

        # state_ready
        ready = client.state_ready(repo=tmp_path)
        assert len(ready) >= 1
        assert "Task 1" in ready[0]

        # state_prompt
        prompt = client.state_prompt(repo=tmp_path, no_worktree=True)
        assert "Task 1" in prompt

        # state_note
        note_ok = client.state_note(repo=tmp_path, message="Integration note test")
        assert note_ok is True

        # state_exec
        exec_res = client.state_exec(repo=tmp_path, cmd="echo baseline_ok", advance=False)
        assert exec_res.get("passed") is True

        # state_doctor
        doc = client.state_doctor(repo=tmp_path)
        assert doc.get("is_healthy") is True

        # state_next
        next_ok = client.state_next(repo=tmp_path, verify_cmd="echo baseline_ok")
        assert next_ok is True

        # worktree_clean
        clean_res = client.worktree_clean(repo=tmp_path)
        assert "cleaned" in clean_res

    # Context exit cleanly terminated the process
    assert client.is_running is False


def test_read_response_timeout() -> None:
    """Verify McpTimeoutError is raised when no response arrives within timeout."""
    r_fd, w_fd = os.pipe()
    proc = FakeMcpServerProcess()
    proc.stdout = open(r_fd, "r")  # type: ignore[assignment]
    try:
        client = SuperstateMcpClient(superstate_bin="/mock/superstate", timeout=0.1)
        client._process = proc  # type: ignore[assignment]
        client._initialized = True

        with pytest.raises(McpTimeoutError):
            client._read_response(req_id=1)
    finally:
        try:
            os.close(w_fd)
        except OSError:
            pass
        try:
            proc.stdout.close()
        except Exception:
            pass


def test_non_json_interleaved_stdout() -> None:
    """Verify non-JSON lines preceding a valid JSON-RPC response do not hang."""
    r_fd, w_fd = os.pipe()
    proc = FakeMcpServerProcess()
    proc.stdout = open(r_fd, "r")  # type: ignore[assignment]
    try:
        client = SuperstateMcpClient(superstate_bin="/mock/superstate", timeout=0.2)
        client._process = proc  # type: ignore[assignment]
        client._initialized = True

        # Write non-JSON lines followed by a valid JSON-RPC response in a single burst
        burst = (
            "Git progress: counting objects 100%\n"
            "warning: some non-json log message\n"
            + json.dumps({"jsonrpc": "2.0", "id": 42, "result": {"status": "ok"}})
            + "\n"
        )
        os.write(w_fd, burst.encode("utf-8"))

        resp = client._read_response(req_id=42)
        assert resp == {"jsonrpc": "2.0", "id": 42, "result": {"status": "ok"}}
    finally:
        try:
            os.close(w_fd)
        except OSError:
            pass
        try:
            proc.stdout.close()
        except Exception:
            pass


def test_process_crash_raises_process_error() -> None:
    """Verify McpProcessError is raised when the child process dies unexpectedly."""
    r_fd, w_fd = os.pipe()
    proc = FakeMcpServerProcess()
    proc.stdout = open(r_fd, "r")  # type: ignore[assignment]
    proc.returncode = 137
    try:
        client = SuperstateMcpClient(superstate_bin="/mock/superstate", timeout=0.5)
        client._process = proc  # type: ignore[assignment]
        client._initialized = True

        # Close the write pipe to simulate child process death closing stdout
        os.close(w_fd)
        w_fd = -1

        with pytest.raises(McpProcessError, match="exited unexpectedly with code 137"):
            client._read_response(req_id=1)
    finally:
        if w_fd != -1:
            try:
                os.close(w_fd)
            except OSError:
                pass
        try:
            proc.stdout.close()
        except Exception:
            pass

