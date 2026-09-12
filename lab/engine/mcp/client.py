"""Superstate MCP stdio JSON-RPC Client.

This module implements a robust stdio JSON-RPC client for interacting with
the `superstate mcp` server over standard input and output pipes. It handles
protocol negotiation (MCP 2024-11-05), server capability and tool discovery,
safe request-response messaging, non-blocking pipe reading, process lifecycle,
and domain-specific wrapper methods for deterministic state control.
"""

from __future__ import annotations

import io
import json
import logging
import os
from pathlib import Path
import select
import shutil
import subprocess
import threading
import time
from typing import Any, Optional

logger = logging.getLogger("superstate_eval.mcp.client")

# Standard MCP protocol specification version supported by superstate
MCP_PROTOCOL_VERSION = "2024-11-05"
CLIENT_NAME = "superstate-mcp-client"
CLIENT_VERSION = "0.1.0"

# Standard candidate paths for the compiled superstate binary
CANDIDATE_PATHS: tuple[Path, ...] = (
    Path.home() / ".cargo" / "bin" / "superstate",
    Path.home() / ".local" / "bin" / "superstate",
)


class McpError(Exception):
    """Base exception for all MCP client errors."""


class McpRpcError(McpError):
    """Raised when the MCP server returns a JSON-RPC error response."""

    def __init__(
        self,
        message: str,
        code: Optional[int] = None,
        data: Any = None,
    ) -> None:
        super().__init__(f"RPC error {code}: {message}" if code is not None else message)
        self.code = code
        self.data = data


class McpProcessError(McpError):
    """Raised when the MCP child process fails to launch, exits unexpectedly, or cannot be found."""


class McpTimeoutError(McpError):
    """Raised when an MCP request or response read operation times out."""


def resolve_superstate_binary(explicit_path: Optional[Path | str] = None) -> Path:
    """Resolve the executable path to the superstate binary.

    Parameters:
        explicit_path: An optional path provided by the caller.

    Returns:
        Path to the verified executable binary.

    Raises:
        McpProcessError: If no binary can be located on candidate paths or PATH.
    """
    # Accept explicit path if provided directly by caller
    if explicit_path is not None:
        return Path(explicit_path)

    # Check candidate installation locations first
    for candidate in CANDIDATE_PATHS:
        # Verify file exists and is executable before selecting
        if candidate.is_file() and os.access(candidate, os.X_OK):
            logger.debug("Resolved superstate binary at candidate path: %s", candidate)
            return candidate

    # Fall back to resolving from the system PATH
    which_bin = shutil.which("superstate")
    if which_bin is not None:
        logger.debug("Resolved superstate binary from PATH: %s", which_bin)
        return Path(which_bin)

    raise McpProcessError(
        "Could not resolve superstate binary. Checked explicit path, cargo, "
        "local bin, and system PATH."
    )


class SuperstateMcpClient:
    """Client for communicating with the superstate MCP server over stdio JSON-RPC.

    Provides handshake management, tool discovery caching, robust non-blocking
    message exchange, and high-level wrappers for superstate domain commands.
    """

    def __init__(
        self,
        superstate_bin: Optional[Path | str] = None,
        timeout: float = 30.0,
        cwd: Optional[Path | str] = None,
    ) -> None:
        """Initialize the MCP client configuration.

        Parameters:
            superstate_bin: Path to the superstate binary (resolved if omitted).
            timeout: Default timeout in seconds for RPC requests.
            cwd: Working directory for spawning the server process.

        Raises:
            McpProcessError: If superstate_bin is omitted and cannot be resolved.
        """
        self.superstate_bin = resolve_superstate_binary(superstate_bin)
        self.timeout = timeout
        self.cwd = Path(cwd) if cwd is not None else None

        self._process: Optional[subprocess.Popen[str]] = None
        self._request_counter = 0
        self._lock = threading.Lock()
        self._tools: dict[str, dict[str, Any]] = {}
        self._server_info: dict[str, Any] = {}
        self._initialized = False
        self._read_buffer = ""

    @property
    def is_running(self) -> bool:
        """Return True if the underlying server process is active and alive."""
        return self._process is not None and self._process.poll() is None

    @property
    def tools(self) -> dict[str, dict[str, Any]]:
        """Return cached map of discovered tools keyed by name."""
        return self._tools

    @property
    def server_info(self) -> dict[str, Any]:
        """Return server identification info received during protocol handshake."""
        return self._server_info

    def __enter__(self) -> "SuperstateMcpClient":
        """Start the MCP server when entering the context block."""
        if not self.is_running:
            self.start()
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        """Terminate the server process cleanly upon exiting context."""
        self.stop()

    def _next_id(self) -> int:
        """Generate a monotonically increasing request ID."""
        with self._lock:
            self._request_counter += 1
            return self._request_counter

    def start(self) -> None:
        """Spawn the superstate mcp process and execute protocol handshake.

        Raises:
            McpProcessError: If process fails to launch or exits during handshake.
            McpRpcError: If initialization handshake returns an RPC error.
            McpTimeoutError: If handshake exceeds configured timeout.
        """
        if self.is_running:
            return

        self._read_buffer = ""
        cmd = [str(self.superstate_bin), "mcp"]
        logger.debug("Spawning superstate MCP process: %s (cwd=%s)", cmd, self.cwd)

        try:
            # Spawn process with line-buffered text stdio pipes
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=str(self.cwd) if self.cwd else None,
            )
        except Exception as exc:
            raise McpProcessError(f"Failed to spawn superstate MCP server: {exc}") from exc

        # Execute MCP handshake sequence
        self._perform_handshake()

    def _perform_handshake(self) -> None:
        """Execute standard MCP initialization handshake and populate tool cache."""
        init_id = self._next_id()
        init_req = {
            "jsonrpc": "2.0",
            "id": init_id,
            "method": "initialize",
            "params": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {
                    "name": CLIENT_NAME,
                    "version": CLIENT_VERSION,
                },
            },
        }

        # Step 1: Send initialize request and inspect server response
        resp = self._send_request(init_req)
        if "error" in resp:
            err = resp["error"]
            raise McpRpcError(
                err.get("message", "Initialize handshake failed"),
                code=err.get("code"),
                data=err.get("data"),
            )

        init_result = resp.get("result", {})
        self._server_info = init_result.get("serverInfo", {})

        # Step 2: Send initialized notification without expecting response
        self._send_notification({"jsonrpc": "2.0", "method": "notifications/initialized"})

        # Step 3: Discover and cache available tools
        list_tools_id = self._next_id()
        list_req = {
            "jsonrpc": "2.0",
            "id": list_tools_id,
            "method": "tools/list",
            "params": {},
        }
        tools_resp = self._send_request(list_req)
        if "error" in tools_resp:
            err = tools_resp["error"]
            raise McpRpcError(
                err.get("message", "tools/list request failed"),
                code=err.get("code"),
                data=err.get("data"),
            )

        tools_list = tools_resp.get("result", {}).get("tools", [])
        self._tools = {tool["name"]: tool for tool in tools_list if isinstance(tool, dict)}
        self._initialized = True
        logger.debug("MCP handshake complete. Cached %d tools.", len(self._tools))

    def stop(self) -> None:
        """Cleanly terminate the superstate child process and close pipes."""
        if self._process is None:
            return

        proc = self._process
        self._process = None
        self._initialized = False
        self._read_buffer = ""

        # Attempt graceful stdin closure first
        try:
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.close()
        except Exception:
            pass

        # Attempt graceful termination
        try:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=2.0)
        except Exception:
            # Force kill if process does not exit promptly
            try:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=2.0)
            except Exception:
                pass

        # Close remaining stdio pipes
        for pipe in (proc.stdout, proc.stderr):
            try:
                if pipe and not pipe.closed:
                    pipe.close()
            except Exception:
                pass

    def _send_notification(self, payload: dict[str, Any]) -> None:
        """Send a JSON-RPC notification message without awaiting reply."""
        if not self.is_running:
            self.start()

        if self._process is None or self._process.stdin is None:
            raise McpProcessError("MCP server process is not available for writing")

        data = json.dumps(payload) + "\n"
        with self._lock:
            self._process.stdin.write(data)
            self._process.stdin.flush()

    def _send_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a JSON-RPC request and wait for the corresponding response.

        Parameters:
            payload: JSON-RPC request dictionary containing method, id, and params.

        Returns:
            JSON-RPC response dictionary containing result or error.

        Raises:
            McpProcessError: If child process terminates unexpectedly.
            McpTimeoutError: If response is not received within timeout.
        """
        req_id = payload.get("id")
        if req_id is None:
            raise McpProcessError("Request payload must contain an 'id' field")

        if self._process is None or self._process.stdin is None:
            raise McpProcessError("MCP server process is not available for writing")

        data = json.dumps(payload) + "\n"
        # Hold lock across both stdin write and response reading to prevent concurrent interleaving
        with self._lock:
            self._process.stdin.write(data)
            self._process.stdin.flush()
            return self._read_response(req_id)

    def _readline_with_timeout(self, deadline: float) -> str:
        """Read a single line from stdout with a timeout deadline.

        Parameters:
            deadline: Absolute UNIX timestamp deadline for receiving data.

        Returns:
            The next line including newline delimiter, or empty string on EOF.

        Raises:
            McpTimeoutError: If no data arrives before deadline.
            McpProcessError: If child process terminates or pipe fails.
        """
        if self._process is None or self._process.stdout is None:
            raise McpProcessError("MCP server process stdout is not available")

        # Read into internal buffer until a complete line is available
        while "\n" not in self._read_buffer:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise McpTimeoutError(
                    f"Timed out waiting for response from MCP server after {self.timeout}s"
                )

            # Determine whether stdout has an underlying OS file descriptor
            fileno: Optional[int] = None
            if hasattr(self._process.stdout, "fileno"):
                try:
                    fileno = self._process.stdout.fileno()
                except (AttributeError, io.UnsupportedOperation, ValueError):
                    fileno = None

            if fileno is not None:
                # Use OS select directly on file descriptor to avoid TextIOWrapper pre-buffering
                readable, _, _ = select.select([fileno], [], [], remaining)
                if not readable:
                    # If process terminated during select wait, report process error rather than timeout
                    if self._process.poll() is not None:
                        poll = self._process.poll()
                        stderr_msg = ""
                        if self._process.stderr:
                            try:
                                stderr_msg = self._process.stderr.read() or ""
                            except Exception:
                                pass
                        raise McpProcessError(
                            f"Superstate MCP server exited unexpectedly with code {poll}: {stderr_msg.strip()}"
                        )
                    raise McpTimeoutError(
                        f"Timed out waiting for response from MCP server after {self.timeout}s"
                    )

                try:
                    # Read raw chunk from OS pipe and append decoded text to internal buffer
                    chunk = os.read(fileno, 4096)
                except OSError as exc:
                    raise McpProcessError(f"Error reading from MCP server stdout: {exc}") from exc

                if not chunk:
                    # Pipe closed (EOF)
                    break
                self._read_buffer += chunk.decode("utf-8", errors="replace")
            else:
                # Fallback for file-like mocks without a fileno
                line = self._process.stdout.readline()
                if not line:
                    break
                self._read_buffer += line

        # If a complete line is buffered, extract and return it
        if "\n" in self._read_buffer:
            line, self._read_buffer = self._read_buffer.split("\n", 1)
            return line + "\n"

        # If EOF was reached with unbuffered remainder, flush it
        if self._read_buffer:
            line = self._read_buffer
            self._read_buffer = ""
            return line

        return ""

    def _read_response(self, req_id: int) -> dict[str, Any]:
        """Read lines from stdout until receiving the matching JSON-RPC response.

        Filters out non-JSON log lines that may be emitted by subprocesses (e.g. git).

        Parameters:
            req_id: The request ID to match.

        Returns:
            The parsed JSON-RPC response dictionary.

        Raises:
            McpProcessError: If child process terminates unexpectedly.
            McpTimeoutError: If response is not received within timeout.
        """
        if self._process is None or self._process.stdout is None:
            raise McpProcessError("MCP server process stdout is not available")

        deadline = time.time() + self.timeout

        while True:
            # Read next line using timeout-bounded non-prebuffering read
            line = self._readline_with_timeout(deadline)
            if not line:
                # Handle process exit or unexpected pipe closure
                poll = self._process.poll()
                if poll is not None:
                    stderr_msg = ""
                    if self._process.stderr:
                        try:
                            stderr_msg = self._process.stderr.read() or ""
                        except Exception:
                            pass
                    raise McpProcessError(
                        f"Superstate MCP server exited unexpectedly with code {poll}: {stderr_msg.strip()}"
                    )
                raise McpProcessError("Superstate MCP server closed output pipe unexpectedly")

            line_str = line if isinstance(line, str) else line.decode("utf-8", errors="replace")
            trimmed = line_str.strip()
            if not trimmed:
                continue

            # Attempt JSON parse; ignore lines that are not valid JSON-RPC
            try:
                msg = json.loads(trimmed)
            except (json.JSONDecodeError, ValueError):
                logger.debug("Ignoring non-JSON stdout line from MCP server: %s", trimmed)
                continue

            # Match response by request ID
            if isinstance(msg, dict) and msg.get("id") == req_id:
                return msg

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Invoke an MCP tool and parse both text and structured JSON content.

        Parameters:
            name: Tool name as advertised by tools/list.
            arguments: Dictionary of arguments conforming to tool's inputSchema.

        Returns:
            Dictionary containing the tool call result with parsed content.

        Raises:
            McpRpcError: If the tool call fails or server returns an error.
            McpProcessError: If server process fails or cannot be reached.
            McpTimeoutError: If execution exceeds configured timeout.
        """
        # Ensure server process is alive before dispatching tool call
        if not self.is_running:
            self.start()

        call_id = self._next_id()
        payload = {
            "jsonrpc": "2.0",
            "id": call_id,
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments,
            },
        }

        resp = self._send_request(payload)

        # Handle top-level JSON-RPC protocol error
        if "error" in resp:
            err = resp["error"]
            raise McpRpcError(
                err.get("message", f"Tool call {name} failed"),
                code=err.get("code"),
                data=err.get("data"),
            )

        result: dict[str, Any] = resp.get("result", {})

        # Parse text and embedded JSON from content blocks
        content = result.get("content", [])
        text_blocks: list[str] = []
        parsed_json: Any = None

        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    txt = block.get("text", "")
                    text_blocks.append(txt)
                    # Attempt to parse text payload as JSON if not already resolved
                    if parsed_json is None:
                        try:
                            parsed_json = json.loads(txt.strip())
                        except (json.JSONDecodeError, ValueError):
                            pass

        if text_blocks and "text" not in result:
            result["text"] = "\n".join(text_blocks)
        if parsed_json is not None and "parsed_json" not in result:
            result["parsed_json"] = parsed_json

        return result

    # -------------------------------------------------------------------------
    # Domain-specific superstate state engine helper wrappers
    # -------------------------------------------------------------------------

    def _format_state_path(self, repo: Path | str) -> str:
        """Resolve a repo path or direct state file path into a state argument string."""
        path = Path(repo)
        if path.suffix == ".json" or path.name == "state.json":
            return str(path)
        return str(path / ".agent-state" / "state.json")

    def state_init(
        self,
        plan: Optional[Path | str] = None,
        repo: Optional[Path | str] = None,
        no_worktree: bool = False,
        worktree: bool = False,
        goal: Optional[str] = None,
        verify_cmd: Optional[str] = None,
    ) -> bool:
        """Initialize state machine tracking from a plan markdown or direct goal."""
        arguments: dict[str, Any] = {}
        if plan is not None:
            arguments["plan"] = str(plan)
        if repo is not None:
            arguments["state"] = self._format_state_path(repo)
        if no_worktree:
            arguments["no_worktree"] = True
        if worktree:
            arguments["worktree"] = True
        if goal is not None:
            arguments["goal"] = goal
        if verify_cmd is not None:
            arguments["verify_cmd"] = verify_cmd

        res = self.call_tool("state_init", arguments)
        return (
            res.get("status") in ("success", "ok")
            or res.get("result", {}).get("status") in ("success", "ok")
            or not res.get("isError", False)
        )

    def state_prompt(
        self,
        repo: Path | str,
        with_graph: bool = False,
        task: Optional[str] = None,
        no_worktree: bool = False,
    ) -> str:
        """Retrieve bounded turnkey prompt for the active task."""
        arguments: dict[str, Any] = {
            "state": self._format_state_path(repo),
            "with_graph": with_graph,
            "no_worktree": no_worktree,
        }
        if task is not None:
            arguments["task"] = task

        res = self.call_tool("state_prompt", arguments)
        return (
            res.get("prompt")
            or res.get("turnkey_prompt")
            or res.get("text")
            or (
                res.get("parsed_json", {}).get("prompt")
                if isinstance(res.get("parsed_json"), dict)
                else ""
            )
            or ""
        )

    def state_next(
        self,
        repo: Path | str,
        verify_cmd: Optional[str] = None,
        verify_git_clean: bool = False,
        ignore_untracked_glob: Optional[str] = None,
    ) -> bool:
        """Advance the milestone state machine past the current task."""
        arguments: dict[str, Any] = {
            "state": self._format_state_path(repo),
            "verify_git_clean": verify_git_clean,
        }
        if verify_cmd is not None:
            arguments["verify_cmd"] = verify_cmd
        if ignore_untracked_glob is not None:
            arguments["ignore_untracked_glob"] = ignore_untracked_glob

        res = self.call_tool("state_next", arguments)
        return (
            res.get("status") in ("success", "ok")
            or res.get("result", {}).get("status") in ("success", "ok")
            or not res.get("isError", False)
        )

    def state_status(
        self,
        repo: Path | str,
        json_format: bool = True,
    ) -> dict[str, Any]:
        """Query current execution state and active milestone metadata."""
        arguments: dict[str, Any] = {
            "state": self._format_state_path(repo),
            "json": json_format,
        }
        res = self.call_tool("state_status", arguments)
        if isinstance(res.get("parsed_json"), dict):
            return res["parsed_json"]
        if isinstance(res.get("state"), dict):
            return res["state"]
        return res

    def state_ready(self, repo: Path | str) -> list[str]:
        """Query unblocked tasks eligible for parallel or sequential execution."""
        arguments: dict[str, Any] = {
            "state": self._format_state_path(repo),
            "json": True,
        }
        res = self.call_tool("state_ready", arguments)
        if isinstance(res.get("ready"), list):
            return res["ready"]
        if isinstance(res.get("parsed_json"), dict) and isinstance(
            res["parsed_json"].get("ready"), list
        ):
            return res["parsed_json"]["ready"]
        return []

    def state_doctor(self, repo: Path | str, repair: bool = False) -> dict[str, Any]:
        """Perform health checks and diagnosis on state integrity."""
        arguments: dict[str, Any] = {
            "state": self._format_state_path(repo),
            "repair": repair,
            "json": True,
        }
        res = self.call_tool("state_doctor", arguments)
        if isinstance(res.get("parsed_json"), dict):
            return res["parsed_json"]
        return res

    def state_exec(
        self,
        repo: Path | str,
        cmd: str,
        verify_cmd: Optional[str] = None,
        rollback_on_fail: bool = False,
        advance: bool = False,
    ) -> dict[str, Any]:
        """Execute a verification command under safety checkpointing."""
        arguments: dict[str, Any] = {
            "state": self._format_state_path(repo),
            "verify_cmd": verify_cmd or cmd,
            "rollback_on_fail": rollback_on_fail,
            "advance": advance,
            "json": True,
        }
        res = self.call_tool("state_exec", arguments)
        if isinstance(res.get("parsed_json"), dict):
            return res["parsed_json"]
        return res

    def state_note(self, repo: Path | str, message: str) -> bool:
        """Record architectural discoveries or findings into the epistemic ledger."""
        arguments: dict[str, Any] = {
            "state": self._format_state_path(repo),
            "note": message,
        }
        res = self.call_tool("state_note", arguments)
        return (
            res.get("note_recorded") is True
            or res.get("status") in ("success", "ok")
            or not res.get("isError", False)
        )

    def worktree_clean(self, repo: Path | str, force: bool = False) -> dict[str, Any]:
        """Clean orphaned or merged worktrees in the target repository."""
        arguments: dict[str, Any] = {
            "repo": str(repo),
            "force": force,
        }
        res = self.call_tool("worktree_clean", arguments)
        if isinstance(res.get("parsed_json"), dict):
            return res["parsed_json"]
        return res
