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


def test_started_dispatches_run_at_the_same_time_and_wait_collects_them(executor: mcp.ContainerExec) -> None:
    # Claude Code runs an MCP server's calls one after another, so each start must return at once.
    work = Path(executor.default_workdir)
    start = time.monotonic()
    ids = []
    for task in ("write a.txt from-a", "write b.txt from-b"):
        t0 = time.monotonic()
        started = json.loads(executor.start_dispatch(task, "true")[0])
        assert time.monotonic() - t0 < 1.0, "a start blocked until its dispatch finished"
        assert started["status"] == "started"
        ids.append(started["dispatch_id"])
    results = json.loads(executor.wait_dispatches(ids)[0])["results"]
    elapsed = time.monotonic() - start

    assert elapsed < 2.8, f"the started dispatches ran one after another ({elapsed:.1f}s)"
    assert [r["dispatch_id"] for r in results] == ids
    assert [r["merge"] for r in results] == ["applied", "applied"]
    assert (work / "a.txt").read_text() == "from-a\n"
    assert (work / "b.txt").read_text() == "from-b\n"
    assert json.loads(executor.wait_dispatches([ids[0]])[0])["results"][0]["outcome"] == "error"


def test_start_and_wait_are_offered_with_the_implementer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLYTE_IMPLEMENTER_MODEL", "gemini-test")
    resp = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, mcp.ContainerExec())
    assert resp is not None
    names = [t["name"] for t in resp["result"]["tools"]]
    assert names == [mcp.TOOL_NAME, mcp.DISPATCH_TOOL_NAME, mcp.DISPATCH_START_TOOL_NAME, mcp.DISPATCH_WAIT_TOOL_NAME]
    bad = mcp.handle(
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": mcp.DISPATCH_WAIT_TOOL_NAME, "arguments": {"dispatch_ids": ["x"]}}},
        mcp.ContainerExec(),
    )
    assert bad is not None and "error" in bad
