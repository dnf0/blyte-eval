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
    BLYTE_EVAL_CONTAINER   required, the container id or name to exec in
    BLYTE_EVAL_WORKDIR     optional, default /app
    BLYTE_EVAL_EXEC_TIMEOUT optional seconds, default 600
    BLYTE_EVAL_MAX_OUTPUT  optional chars, default 30000
    BLYTE_IMPLEMENTER_MODEL     optional, enables dispatch_blyte tool when set
    BLYTE_DISPATCH_DIR          required when dispatch_blyte is enabled
    BLYTE_BIN                   optional path to blyte binary (default: blyte on PATH)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from typing import Any, Iterable, TextIO

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "blyte-eval-container-exec"
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

DISPATCH_TOOL_NAME = "dispatch_blyte"
# `blyte dispatch`'s own default. Without it blyte used the headless default of 25 turns: all
# three dispatches of the first offload task stopped there before reaching the gate (2026-09-28).
DISPATCH_MAX_TURNS = 300
# Git as the dispatch copies use it: any owner (the copy is root's), and an identity for the
# snapshot commits, which exist only in the copy.
DISPATCH_GIT = "git -c safe.directory='*' -c user.name=dispatch -c user.email=dispatch@local"
DISPATCH_TOOL_DESCRIPTION = (
    "Hand one well-specified implementation task to blyte, a cheaper implementer model "
    "working in this same container. It edits files, runs commands, and stops when `gate` "
    "(a shell command, e.g. the relevant test command) exits 0 or its budget runs out. "
    "Each dispatch works in its own copy of the repository, taken from its current state "
    "(uncommitted changes included). For several independent tasks that touch different "
    "files, use dispatch_blyte_start for each and then dispatch_blyte_wait: they run at the same "
    "time (calls to this tool run one after another). When a "
    "dispatch ends, its changes are applied to the repository; if they clash with changes "
    "applied since it started, nothing is applied and `merge` is \"conflict\", with the copy's "
    "path for you to inspect. The gate runs in the copy, so give it relative paths. Returns the "
    "outcome, any gate failures and `merge`. You remain responsible for the result: review the "
    "changes with run_in_container afterwards."
)

DISPATCH_TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "task": {
            "type": "string",
            "description": "Task description for the implementer model to perform in the container",
        },
        "gate": {
            "type": "string",
            "description": "Shell command to verify completion (stops when it exits 0)",
        },
        "max_seconds": {
            "type": "integer",
            "description": "Maximum seconds for the implementer run (optional, default 1200)",
            "default": 1200,
        },
    },
    "required": ["task", "gate"],
    "additionalProperties": False,
}

# Start-then-wait (2026-09-29): Claude Code runs an MCP server's tool calls one after another, so
# parallel dispatch_blyte calls still ran in sequence. A start returns at once; wait collects.
DISPATCH_START_TOOL_NAME = "dispatch_blyte_start"
DISPATCH_START_TOOL_DESCRIPTION = (
    "Start one implementation task on blyte in the background and return at once with its "
    "`dispatch_id`. Same arguments and behaviour as dispatch_blyte (its own copy of the "
    "repository, applied back when it ends). Start every independent task this way, then call "
    "dispatch_blyte_wait to collect their results: the started tasks run at the same time."
)
DISPATCH_WAIT_TOOL_NAME = "dispatch_blyte_wait"
DISPATCH_WAIT_TOOL_DESCRIPTION = (
    "Wait for dispatches started with dispatch_blyte_start to finish and return their results "
    "(the same fields as dispatch_blyte, plus `dispatch_id`), in the order given. With no ids, "
    "waits for every started dispatch not yet collected."
)
DISPATCH_WAIT_TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "dispatch_ids": {
            "type": "array",
            "items": {"type": "integer"},
            "description": "The dispatch_ids to wait for (optional; default: all not yet collected)",
        },
    },
    "additionalProperties": False,
}


def log(message: str) -> None:
    """Diagnostics go to stderr; stdout carries protocol messages only."""
    print(f"[container-exec-mcp] {message}", file=sys.stderr, flush=True)


class ContainerExec:
    """Execs commands in a single, fixed container."""

    def __init__(self) -> None:
        self.container_id = os.environ.get("BLYTE_EVAL_CONTAINER", "").strip()
        self.default_workdir = os.environ.get("BLYTE_EVAL_WORKDIR", "/app")
        self.timeout = int(os.environ.get("BLYTE_EVAL_EXEC_TIMEOUT", "600"))
        self.max_output = int(os.environ.get("BLYTE_EVAL_MAX_OUTPUT", "30000"))
        self._container: Any = None
        self.dispatch_count: int = 0
        # Parallel dispatches (2026-09-29): each works in a copy under copy_root, as `blyte dispatch`
        # gives each task its own worktree, and lands in the workdir one at a time.
        self.copy_root = os.environ.get("BLYTE_DISPATCH_COPY_ROOT", "/tmp")
        self._count_lock = threading.Lock()
        self._merge_lock = threading.Lock()
        # Background dispatches (dispatch_blyte_start): id -> thread, and id -> result once done.
        self._jobs: dict[int, threading.Thread] = {}
        self._job_results: dict[int, str] = {}
        self._job_count = 0

    def _resolve(self) -> Any:
        if self._container is None:
            import docker

            self._container = docker.from_env().containers.get(self.container_id)
        return self._container

    def run(self, command: str, workdir: str | None = None) -> tuple[str, bool]:
        """Execute `command`; return (text, is_error)."""
        if not self.container_id:
            return ("BLYTE_EVAL_CONTAINER is not set; no container to execute in.", True)
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

    def _sh(self, script: str) -> tuple[int, str]:
        """Run a shell script in the container; return (exit code, output)."""
        exec_res = self._resolve().exec_run(["/bin/sh", "-c", script], workdir="/", demux=False)
        if isinstance(exec_res, tuple):
            code, raw = exec_res[0], exec_res[1]
        else:
            code = getattr(exec_res, "exit_code", 1)
            raw = getattr(exec_res, "output", b"")
        out = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw or "")
        return (1 if code is None else int(code), out)

    def _merge_back(self, copy: str) -> dict[str, Any]:
        """Apply a finished dispatch's changes to the workdir. Dispatches land one at a time; one
        whose changes clash with changes applied since it started is reported, not forced, and
        its copy is kept for the orchestrator to inspect."""
        patch = f"{copy}.patch"
        code, out = self._sh(
            f"cd {copy} && {DISPATCH_GIT} add -A && "
            f"{DISPATCH_GIT} commit -q --allow-empty --no-verify -m dispatch-result && "
            f"{DISPATCH_GIT} diff --binary refs/dispatch/base HEAD > {patch}"
        )
        if code != 0:
            return {"merge": "error", "merge_detail": out[-500:], "copy": copy}
        with self._merge_lock:
            code, out = self._sh(
                f"if [ ! -s {patch} ]; then echo no-changes; exit 0; fi; cd {self.default_workdir} && "
                f"{DISPATCH_GIT} apply --check {patch} && {DISPATCH_GIT} apply {patch} && echo applied"
            )
        if code != 0:
            return {"merge": "conflict", "merge_detail": out[-1000:], "copy": copy, "patch": patch}
        self._sh(f"rm -rf {copy}")
        return {"merge": "no changes" if "no-changes" in out else "applied"}

    def start_dispatch(self, task: str, gate: str, max_seconds: int = 1200) -> tuple[str, bool]:
        """Run `dispatch` in a background thread; return its dispatch_id at once."""
        with self._count_lock:
            self._job_count += 1
            job = self._job_count

        def work() -> None:
            text, _ = self.dispatch(task, gate, max_seconds)
            self._job_results[job] = text

        thread = threading.Thread(target=work, daemon=True)
        self._jobs[job] = thread
        thread.start()
        return (json.dumps({"dispatch_id": job, "status": "started"}), False)

    def wait_dispatches(self, ids: list[int] | None = None) -> tuple[str, bool]:
        """Wait for the given background dispatches (default: all not yet collected)."""
        if ids is None:
            ids = sorted(self._jobs)
        results: list[dict[str, Any]] = []
        for job in ids:
            thread = self._jobs.pop(job, None)
            if thread is None:
                results.append({"dispatch_id": job, "outcome": "error", "error": "no such running dispatch"})
                continue
            thread.join()
            results.append({"dispatch_id": job, **json.loads(self._job_results.pop(job))})
        return (json.dumps({"results": results}), False)

    def dispatch(
        self,
        task: str,
        gate: str,
        max_seconds: int = 1200,
    ) -> tuple[str, bool]:
        """Dispatch an implementation task to blyte in the container; return (json_text, is_error)."""
        if not self.container_id:
            return (
                json.dumps({"outcome": "error", "error": "BLYTE_EVAL_CONTAINER is not set; no container to execute in."}),
                False,
            )
        model = os.environ.get("BLYTE_IMPLEMENTER_MODEL", "").strip()
        if not model:
            return (
                json.dumps({"outcome": "error", "error": "BLYTE_IMPLEMENTER_MODEL is not set."}),
                False,
            )
        dispatch_dir = os.environ.get("BLYTE_DISPATCH_DIR", "").strip()
        if not dispatch_dir:
            return (
                json.dumps({"outcome": "error", "error": "BLYTE_DISPATCH_DIR is not set."}),
                False,
            )

        with self._count_lock:
            self.dispatch_count += 1
            n = self.dispatch_count
        reports_dir = Path(dispatch_dir)
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / f"dispatch-{n}.json"
        # blyte's event stream (one line per tool call, with the command). The report says how
        # long commands took but not which ones; without this, how often a dispatch ran the full
        # test suite could only be estimated (offload v2, 2026-09-28).
        events_path = reports_dir / f"dispatch-{n}.events.log"

        # The dispatch's own copy, snapshotted so its changes can be applied back as one patch.
        copy = f"{self.copy_root}/blyte-dispatch-{n}"
        code, out = self._sh(
            f"rm -rf {copy} && cp -a {self.default_workdir}/. {copy} && cd {copy} && "
            f"{DISPATCH_GIT} add -A && {DISPATCH_GIT} commit -q --allow-empty --no-verify -m dispatch-base && "
            f"{DISPATCH_GIT} update-ref refs/dispatch/base HEAD"
        )
        if code != 0:
            return (
                json.dumps({"outcome": "error", "error": f"Could not copy {self.default_workdir} for the dispatch: {out[-500:]}"}),
                False,
            )

        blyte_bin = os.environ.get("BLYTE_BIN", "").strip() or "blyte"
        cmd = [
            blyte_bin,
            "--container",
            self.container_id,
            "--container-workdir",
            copy,
            "--model",
            model,
            "--gate",
            gate,
            "--rollback=false",
            "--max-seconds",
            str(max_seconds),
            "--max-turns",
            str(DISPATCH_MAX_TURNS),
            "--report",
            str(report_path),
            "--",
            task,
        ]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
            )
        except Exception as err:
            return (
                json.dumps({"outcome": "error", "error": f"Failed to execute blyte: {err}", **self._merge_back(copy)}),
                False,
            )

        events = proc.stdout or ""
        if proc.stderr:
            events += f"\n--- stderr ---\n{proc.stderr}"
        try:
            events_path.write_text(events, encoding="utf-8")
        except OSError as err:
            log(f"could not write {events_path}: {err}")

        merge = self._merge_back(copy)
        if not report_path.is_file():
            err_msg = (proc.stderr or "").strip() or f"Dispatch report not found at {report_path}"
            return (
                json.dumps({"outcome": "error", "error": err_msg, **merge}),
                False,
            )

        try:
            with open(report_path, "r", encoding="utf-8") as f:
                report_data = json.load(f)
        except Exception as err:
            return (
                json.dumps({"outcome": "error", "error": f"Failed to parse dispatch report: {err}", **merge}),
                False,
            )

        raw_gf = report_data.get("gate_failures")
        gate_failures = [
            str(f)[:1000]
            for f in raw_gf
        ] if isinstance(raw_gf, list) else []

        summary = {
            "outcome": report_data.get("outcome"),
            "gate_attempts": report_data.get("gate_attempts"),
            "gate_failures": gate_failures,
            "turns": report_data.get("turns"),
            "cost_usd": report_data.get("cost_usd"),
            "seconds": (
                report_data.get("seconds")
                if report_data.get("seconds") is not None
                else report_data.get("duration_seconds")
            ),
            "report": report_data.get("report") or str(report_path),
            "events_log": str(events_path),
            **merge,
        }
        return (json.dumps(summary), False)


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
        tools = [
            {
                "name": TOOL_NAME,
                "description": TOOL_DESCRIPTION,
                "inputSchema": TOOL_SCHEMA,
            }
        ]
        if os.environ.get("BLYTE_IMPLEMENTER_MODEL", "").strip():
            tools.append(
                {
                    "name": DISPATCH_TOOL_NAME,
                    "description": DISPATCH_TOOL_DESCRIPTION,
                    "inputSchema": DISPATCH_TOOL_SCHEMA,
                }
            )
            tools.append(
                {
                    "name": DISPATCH_START_TOOL_NAME,
                    "description": DISPATCH_START_TOOL_DESCRIPTION,
                    "inputSchema": DISPATCH_TOOL_SCHEMA,
                }
            )
            tools.append(
                {
                    "name": DISPATCH_WAIT_TOOL_NAME,
                    "description": DISPATCH_WAIT_TOOL_DESCRIPTION,
                    "inputSchema": DISPATCH_WAIT_TOOL_SCHEMA,
                }
            )
        return _result(
            request_id,
            {"tools": tools},
        )

    if method == "tools/call":
        params = message.get("params") or {}
        tool_name = params.get("name")
        if tool_name == TOOL_NAME:
            args = params.get("arguments") or {}
            command = args.get("command")
            if not isinstance(command, str) or not command.strip():
                return _error(request_id, -32602, "'command' must be a non-empty string")
            text, is_error = executor.run(command, args.get("workdir"))
            return _result(
                request_id,
                {"content": [{"type": "text", "text": text}], "isError": is_error},
            )
        dispatching = bool(os.environ.get("BLYTE_IMPLEMENTER_MODEL", "").strip())
        if tool_name == DISPATCH_WAIT_TOOL_NAME and dispatching:
            args = params.get("arguments") or {}
            raw_ids = args.get("dispatch_ids")
            if raw_ids is not None and (
                not isinstance(raw_ids, list) or not all(isinstance(i, int) and not isinstance(i, bool) for i in raw_ids)
            ):
                return _error(request_id, -32602, "'dispatch_ids' must be a list of integers")
            text, is_error = executor.wait_dispatches(raw_ids)
            return _result(
                request_id,
                {"content": [{"type": "text", "text": text}], "isError": is_error},
            )
        if tool_name in (DISPATCH_TOOL_NAME, DISPATCH_START_TOOL_NAME) and dispatching:
            args = params.get("arguments") or {}
            task = args.get("task")
            if not isinstance(task, str) or not task.strip():
                return _error(request_id, -32602, "'task' must be a non-empty string")
            gate = args.get("gate")
            if not isinstance(gate, str) or not gate.strip():
                return _error(request_id, -32602, "'gate' must be a non-empty string")
            raw_max_seconds = args.get("max_seconds", 1200)
            try:
                if isinstance(raw_max_seconds, bool):
                    raise ValueError
                max_seconds = int(raw_max_seconds)
                if max_seconds <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                return _error(request_id, -32602, "'max_seconds' must be a positive integer")
            if tool_name == DISPATCH_START_TOOL_NAME:
                text, is_error = executor.start_dispatch(task, gate, max_seconds)
            else:
                text, is_error = executor.dispatch(task, gate, max_seconds)
            return _result(
                request_id,
                {"content": [{"type": "text", "text": text}], "isError": is_error},
            )
        return _error(request_id, -32602, f"Unknown tool: {tool_name}")

    if method == "ping":
        return _result(request_id, {})

    if request_id is None:
        return None  # unknown notification
    return _error(request_id, -32601, f"Method not found: {method}")


def serve(lines: Iterable[str], out: TextIO, executor: ContainerExec) -> int:
    """Answer each message. Tool calls are answered from their own threads, so parallel dispatches
    run at the same time and other tool calls are not held up behind one (2026-09-29: the server
    answered one message at a time, so a turn's parallel dispatches ran one after another)."""
    write_lock = threading.Lock()
    threads: list[threading.Thread] = []

    def answer(message: dict[str, Any]) -> None:
        try:
            response = handle(message, executor)
        except Exception as err:  # never take the transport down
            log(f"handler error: {err}")
            response = _error(message.get("id"), -32603, str(err))
        if response is not None:
            with write_lock:
                out.write(json.dumps(response) + "\n")
                out.flush()

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as err:
            log(f"malformed message: {err}")
            continue
        if message.get("method") == "tools/call":
            thread = threading.Thread(target=answer, args=(message,), daemon=True)
            thread.start()
            threads.append(thread)
        else:
            answer(message)
    for thread in threads:
        thread.join()
    return 0


def main() -> int:
    executor = ContainerExec()
    log(f"serving exec for container {executor.container_id or '<unset>'}")
    return serve(sys.stdin, sys.stdout, executor)


if __name__ == "__main__":
    raise SystemExit(main())
