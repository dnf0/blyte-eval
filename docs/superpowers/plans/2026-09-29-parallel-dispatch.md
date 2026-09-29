# Parallel Dispatches in the Eval — Plan

> **For agentic workers:** Execution is delegated to headless `blyte` (with a sampled A/B against `agy`), one task per dispatch; Claude reviews each task before the next is sent. Steps use checkbox (`- [ ]`) syntax for tracking. Do NOT `git push` or open PRs; commit locally only. Do NOT start any benchmark or paid run, or call any model API. Do not edit `FINDINGS.md`, `EXPERIMENTS.md`, `CLAUDE.md`/`AGENTS.md`, `results/`, `traces/` or `data/`.

**Why (2026-09-29):** the eval's `dispatch_blyte` tool (the offload arm, where Claude plans and
blyte implements) ran a turn's parallel dispatches one after another: the MCP server answered one
message at a time, and every dispatch worked in the same `/app`, so running them at once would
have had them edit over each other. The user chose option B: each dispatch gets its own copy of
the repository, as `blyte dispatch` gives each task its own worktree in real use.

**Design.** A dispatch copies the workdir (`cp -a`, uncommitted changes and untracked files
included) to `$BLYTE_DISPATCH_COPY_ROOT/blyte-dispatch-<n>` (default `/tmp`) inside the container,
snapshots it as a commit in the copy, and runs blyte there. When blyte ends (any outcome), the copy's
changes since the snapshot become one patch, applied to the workdir with `git apply` under a lock,
so dispatches land one at a time. A patch that no longer applies (the workdir changed in the same
places since the dispatch started) is not forced: the result says `"merge": "conflict"` and keeps
the copy for the orchestrator to inspect. The server answers each tool call in its own thread.
Known limit: a Python project installed in editable mode from `/app` imports `/app`'s code, not the
copy's, when tested in the copy; choose tasks in other languages for the first parallel runs.

## Global Constraints

- Base branch `feat/parallel-dispatch`. Work only in your own worktree.
- Existing tests pass, except the two edits to `tests/test_dispatch_blyte_tool.py` in Step 2.
- Checks: `make lint && make test`.
- Commit with `--no-gpg-sign` and the exact message below.

### Task 1: each dispatch in its own copy, run in parallel

**Files:**
- Replace: `lab/engine/drivers/container_exec_mcp.py` (whole file, Step 1)
- Modify: `tests/test_dispatch_blyte_tool.py` (Step 2)
- Create: `tests/test_parallel_dispatch.py` (Step 3)

- [ ] **Step 1: replace the whole of `lab/engine/drivers/container_exec_mcp.py` with exactly this**
  (write the file in one go, for example with a heredoc or a short script; do not edit it piece by piece):

````python
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
    "(uncommitted changes included), so several dispatches can run at the same time: call the "
    "tool more than once in one turn for independent tasks that touch different files. When a "
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
        if tool_name == DISPATCH_TOOL_NAME and os.environ.get("BLYTE_IMPLEMENTER_MODEL", "").strip():
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
````

- [ ] **Step 2: two edits to `tests/test_dispatch_blyte_tool.py`.** These tests have no container,
  so they stub the copy step. Directly after the import block (the line `)` that closes
  `from lab.engine.drivers.container_exec_mcp import (`), add two blank lines and:

```python
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
```

  and in `test_argv_contains_required_flags`, replace

```python
    workdir_idx = captured_cmd.index("--container-workdir")
    assert captured_cmd[workdir_idx + 1] == "/workspace"
```

  with

```python
    # blyte works in the dispatch's own copy of /workspace, not in /workspace itself.
    workdir_idx = captured_cmd.index("--container-workdir")
    assert captured_cmd[workdir_idx + 1] == "/tmp/blyte-dispatch-1"
```

- [ ] **Step 3: create `tests/test_parallel_dispatch.py` with exactly this:**

````python
"""Parallel dispatches (2026-09-29): each works in its own copy of the repository, they run at
the same time, and each one's changes are applied back to the workdir when it ends."""

from __future__ import annotations

import io
import json
from pathlib import Path
import stat
import subprocess
import threading
import time
from typing import Any

import pytest

from lab.engine.drivers import container_exec_mcp as mcp

# A fake blyte: waits, then writes `<text>` to `<file>` in the dispatch's workdir, for the task
# "write <file> <text>", and writes a verified report.
STUB = """#!/usr/bin/env python3
import json, sys, time
from pathlib import Path
a = sys.argv[1:]
work = Path(a[a.index("--container-workdir") + 1])
report = Path(a[a.index("--report") + 1])
_, name, text = a[-1].split(" ", 2)
time.sleep(1.5)
(work / name).write_text(text + "\\n")
report.parent.mkdir(parents=True, exist_ok=True)
report.write_text(json.dumps({"outcome": "verified", "turns": 1, "gate_attempts": 1}))
"""


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


@pytest.fixture
def executor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> mcp.ContainerExec:
    work = tmp_path / "app"
    work.mkdir()
    (work / "a.txt").write_text("a\n")
    (work / "b.txt").write_text("b\n")
    _git(work, "init", "-q")
    _git(work, "add", "-A")
    _git(work, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base")
    (work / "wip.txt").write_text("uncommitted\n")  # the orchestrator's own work in progress
    stub = tmp_path / "blyte"
    stub.write_text(STUB)
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    copies = tmp_path / "copies"
    copies.mkdir()
    monkeypatch.setenv("BLYTE_EVAL_CONTAINER", "cnt-test")
    monkeypatch.setenv("BLYTE_EVAL_WORKDIR", str(work))
    monkeypatch.setenv("BLYTE_IMPLEMENTER_MODEL", "gemini-test")
    monkeypatch.setenv("BLYTE_DISPATCH_DIR", str(tmp_path / "dispatches"))
    monkeypatch.setenv("BLYTE_DISPATCH_COPY_ROOT", str(copies))
    monkeypatch.setenv("BLYTE_BIN", str(stub))
    ex = mcp.ContainerExec()

    def local_sh(script: str) -> tuple[int, str]:
        p = subprocess.run(["/bin/sh", "-c", script], capture_output=True, text=True)
        return (p.returncode, p.stdout + p.stderr)

    monkeypatch.setattr(ex, "_sh", local_sh)
    return ex


def _dispatch_all(ex: mcp.ContainerExec, tasks: list[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    lock = threading.Lock()

    def go(task: str) -> None:
        r = json.loads(ex.dispatch(task, "true")[0])
        with lock:
            results.append(r)

    threads = [threading.Thread(target=go, args=(t,)) for t in tasks]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def test_parallel_dispatches_run_at_once_in_their_own_copies_and_land(executor: mcp.ContainerExec) -> None:
    work = Path(executor.default_workdir)
    start = time.monotonic()
    results = _dispatch_all(executor, ["write a.txt from-a", "write b.txt from-b"])
    elapsed = time.monotonic() - start

    assert elapsed < 2.8, f"the dispatches ran one after another ({elapsed:.1f}s)"
    assert [r["merge"] for r in results] == ["applied", "applied"]
    assert (work / "a.txt").read_text() == "from-a\n"
    assert (work / "b.txt").read_text() == "from-b\n"
    assert (work / "wip.txt").read_text() == "uncommitted\n"
    assert len(_git(work, "log", "--oneline").splitlines()) == 1  # the workdir's history is untouched
    assert [p for p in Path(executor.copy_root).iterdir() if p.is_dir()] == []  # copies removed


def test_a_dispatch_that_clashes_with_one_already_applied_is_reported_not_forced(
    executor: mcp.ContainerExec,
) -> None:
    work = Path(executor.default_workdir)
    results = _dispatch_all(executor, ["write a.txt first", "write a.txt second"])

    assert sorted(r["merge"] for r in results) == ["applied", "conflict"]
    clash = next(r for r in results if r["merge"] == "conflict")
    assert Path(clash["copy"]).is_dir()  # kept for the orchestrator to inspect
    assert (work / "a.txt").read_text() in ("first\n", "second\n")


def test_a_running_dispatch_does_not_hold_up_other_tool_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    class Slow(mcp.ContainerExec):
        def dispatch(self, task: str, gate: str, max_seconds: int = 1200) -> tuple[str, bool]:
            time.sleep(1.0)
            return ("{}", False)

        def run(self, command: str, workdir: str | None = None) -> tuple[str, bool]:
            return ("exit_code=0\nok", False)

    monkeypatch.setenv("BLYTE_IMPLEMENTER_MODEL", "gemini-test")
    lines = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": mcp.DISPATCH_TOOL_NAME, "arguments": {"task": "t", "gate": "true"}}}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                    "params": {"name": mcp.TOOL_NAME, "arguments": {"command": "echo ok"}}}),
    ]
    out = io.StringIO()
    mcp.serve(lines, out, Slow())
    assert [json.loads(line)["id"] for line in out.getvalue().splitlines()] == [2, 1]
````

  Run: `.venv/bin/python -m pytest tests/test_parallel_dispatch.py tests/test_dispatch_blyte_tool.py tests/test_container_exec_mcp.py -q`
  Expected: all pass (31 tests). Before Step 1 the new file fails (`serve` does not exist).

- [ ] **Step 4: run the checks and commit.**

  Run: `make lint && make test`. Expected: both pass.

```bash
git add lab/engine/drivers/container_exec_mcp.py tests/test_dispatch_blyte_tool.py tests/test_parallel_dispatch.py
git commit --no-gpg-sign -m "feat(eval): parallel dispatches, each in its own copy of the repository, applied back when done"
```
