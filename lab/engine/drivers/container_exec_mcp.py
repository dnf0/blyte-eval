"""A minimal stdio MCP server exposing exactly one tool: exec in ONE container.

Why this exists: the agent runs on the host, because the task sandbox is
network-isolated and the agent needs the API. But a host agent with a shell can
reach the Docker daemon, and from there read the held-out tests baked into the
verifier image (`docker run <verifier> cat /tests/test.patch`) or mount the host
filesystem. Disallowing the CLI's Bash tool closes that door; this server
reopens just the part the agent legitimately needs -- running build and test
commands in the task's own toolchain.

The container id is fixed by the environment at launch, so the agent cannot
choose a different container, start one, or enumerate images.

Run as: python -m lab.engine.drivers.container_exec_mcp
Environment:
    SUPERSTATE_EVAL_CONTAINER   required, the container id or name to exec in
    SUPERSTATE_EVAL_WORKDIR     optional, default /app
    SUPERSTATE_EVAL_EXEC_TIMEOUT optional seconds, default 600
    SUPERSTATE_EVAL_MAX_OUTPUT  optional chars, default 30000
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "superstate-eval-container-exec"
SERVER_VERSION = "1.0.0"

TOOL_NAME = "run_in_container"
TOOL_DESCRIPTION = (
    "Run a shell command inside the task's Docker container, where the project's "
    "toolchain and dependencies are installed. The working directory is the task "
    "repository. Use this for ALL build, test and inspection commands -- the host "
    "has neither the toolchain nor the task's dependencies. Returns the combined "
    "stdout and stderr, prefixed with the exit code."
)

TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "command": {
            "type": "string",
            "description": "Shell command to run inside the container, e.g. 'go test ./vm'",
        },
        "workdir": {
            "type": "string",
            "description": "Optional working directory inside the container (default /app)",
        },
    },
    "required": ["command"],
    "additionalProperties": False,
}


def log(message: str) -> None:
    """Diagnostics go to stderr; stdout carries protocol messages only."""
    print(f"[container-exec-mcp] {message}", file=sys.stderr, flush=True)


class ContainerExec:
    """Execs commands in a single, fixed container."""

    def __init__(self) -> None:
        self.container_id = os.environ.get("SUPERSTATE_EVAL_CONTAINER", "").strip()
        self.default_workdir = os.environ.get("SUPERSTATE_EVAL_WORKDIR", "/app")
        self.timeout = int(os.environ.get("SUPERSTATE_EVAL_EXEC_TIMEOUT", "600"))
        self.max_output = int(os.environ.get("SUPERSTATE_EVAL_MAX_OUTPUT", "30000"))
        self._container: Any = None

    def _resolve(self) -> Any:
        if self._container is None:
            import docker

            self._container = docker.from_env().containers.get(self.container_id)
        return self._container

    def run(self, command: str, workdir: str | None = None) -> tuple[str, bool]:
        """Execute `command`; return (text, is_error)."""
        if not self.container_id:
            return ("SUPERSTATE_EVAL_CONTAINER is not set; no container to execute in.", True)
        try:
            container = self._resolve()
            exec_res = container.exec_run(
                ["/bin/sh", "-c", command],
                workdir=workdir or self.default_workdir,
                demux=False,
            )
        except Exception as err:
            return (f"Failed to execute in container {self.container_id}: {err}", True)

        if isinstance(exec_res, tuple):
            exit_code, raw = exec_res[0], exec_res[1]
        else:
            exit_code = getattr(exec_res, "exit_code", 1)
            raw = getattr(exec_res, "output", b"")
        output = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)

        if len(output) > self.max_output:
            dropped = len(output) - self.max_output
            output = output[: self.max_output] + f"\n...[truncated {dropped} chars]"

        # A non-zero exit is a legitimate result (a failing test), not a tool error.
        return (f"exit_code={exit_code}\n{output}", False)


def _result(request_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": payload}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle(message: dict[str, Any], executor: ContainerExec) -> dict[str, Any] | None:
    """Handle one JSON-RPC message. Returns a response, or None for notifications."""
    method = message.get("method")
    request_id = message.get("id")

    if method == "initialize":
        # Echo the client's protocol version when it names one.
        requested = (message.get("params") or {}).get("protocolVersion") or PROTOCOL_VERSION
        return _result(
            request_id,
            {
                "protocolVersion": requested,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        )

    if method in ("notifications/initialized", "initialized"):
        return None

    if method == "tools/list":
        return _result(
            request_id,
            {
                "tools": [
                    {
                        "name": TOOL_NAME,
                        "description": TOOL_DESCRIPTION,
                        "inputSchema": TOOL_SCHEMA,
                    }
                ]
            },
        )

    if method == "tools/call":
        params = message.get("params") or {}
        if params.get("name") != TOOL_NAME:
            return _error(request_id, -32602, f"Unknown tool: {params.get('name')}")
        args = params.get("arguments") or {}
        command = args.get("command")
        if not isinstance(command, str) or not command.strip():
            return _error(request_id, -32602, "'command' must be a non-empty string")
        text, is_error = executor.run(command, args.get("workdir"))
        return _result(
            request_id,
            {"content": [{"type": "text", "text": text}], "isError": is_error},
        )

    if method == "ping":
        return _result(request_id, {})

    if request_id is None:
        return None  # unknown notification
    return _error(request_id, -32601, f"Method not found: {method}")


def main() -> int:
    executor = ContainerExec()
    log(f"serving exec for container {executor.container_id or '<unset>'}")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as err:
            log(f"malformed message: {err}")
            continue
        try:
            response = handle(message, executor)
        except Exception as err:  # never take the transport down
            log(f"handler error: {err}")
            response = _error(message.get("id"), -32603, str(err))
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
