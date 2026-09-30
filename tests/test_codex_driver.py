"""The Codex CLI driver: same conditions as the Claude arms, with the operator's Codex setup kept
out (2026-09-30)."""

from __future__ import annotations

import json
from pathlib import Path
import stat
from typing import Any

import pytest
import sys

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.drivers.codex_cli import DISABLED_FEATURES, CodexCliDriver, parse_events
from lab.engine.harnesses import HarnessSpecError, build_harness, parse_harness_spec

EVENTS = "\n".join(json.dumps(e) for e in [
    {"type": "thread.started", "thread_id": "th-1"},
    {"type": "item.completed", "item": {"type": "agent_message", "text": "first"}},
    {"type": "item.completed", "item": {"type": "agent_message", "text": "Done: added slugify."}},
    {"type": "turn.completed", "usage": {"input_tokens": 100, "cached_input_tokens": 60,
                                         "output_tokens": 20, "reasoning_output_tokens": 5}},
])


class FakeContainer:
    id = "cnt-123"


def _task(tmp_path: Path) -> TaskSpec:
    return TaskSpec(id="org/t", name="t", instruction="Add slugify.", docker_image="img", task_dir=tmp_path)


def _stub(tmp_path: Path) -> Path:
    """A stand-in codex: records argv, stdin and the environment it saw, then prints EVENTS."""
    log = tmp_path / "codex-call.json"
    stub = tmp_path / "codex"
    body = """#!PYTHON
import json, os, sys
auth = os.path.join(os.environ["CODEX_HOME"], "auth.json")
json.dump({
    "argv": sys.argv[1:],
    "stdin": sys.stdin.read(),
    "home": os.environ["HOME"],
    "codex_home": os.environ["CODEX_HOME"],
    "files": sorted(os.listdir(os.environ["CODEX_HOME"])),
    "auth_link": os.readlink(auth) if os.path.islink(auth) else None,
}, open(LOG, "w"))
print(EVENTS)
"""
    # sys.executable, not /usr/bin/env python3: a pyenv shim needs the real HOME the driver replaces.
    body = body.replace("PYTHON", sys.executable).replace("LOG", repr(str(log))).replace("EVENTS", repr(EVENTS))
    stub.write_text(body)
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    return stub


def test_events_give_the_last_message_the_usage_and_the_thread() -> None:
    text, usage, thread, error = parse_events(EVENTS)
    assert (text, thread, error) == ("Done: added slugify.", "th-1", None)
    assert usage == {"input_tokens": 100, "cached_input_tokens": 60, "output_tokens": 20,
                     "reasoning_output_tokens": 5}
    failed = json.dumps({"type": "turn.failed", "error": {"message": "model not supported"}})
    assert parse_events(failed)[3] == "model not supported"


def test_the_host_tools_are_off_and_the_container_server_is_approved(tmp_path: Path) -> None:
    d = CodexCliDriver(cli_path=str(_stub(tmp_path)), implementer_model="gemini-3.8-flash-high")
    cmd = d._build_command(tmp_path, "cnt-123", tmp_path / "dispatches")
    for feature in DISABLED_FEATURES:
        i = cmd.index(feature)
        assert cmd[i - 1] == "--disable"
    assert "web_search=disabled" in cmd
    joined = " ".join(cmd)
    assert 'mcp_servers.task.default_tools_approval_mode="approve"' in joined
    assert '"BLYTE_EVAL_CONTAINER"' not in joined  # TOML keys are bare
    assert 'BLYTE_EVAL_CONTAINER="cnt-123"' in joined
    assert 'BLYTE_IMPLEMENTER_MODEL="gemini-3.8-flash-high"' in joined
    # The MCP server (and the blyte it starts) keeps the real HOME, where blyte's key file is.
    assert f"HOME={json.dumps(str(Path.home()))}" in joined
    assert cmd[-1] == "-"
    plain = CodexCliDriver(cli_path=str(_stub(tmp_path)))._build_command(tmp_path, "cnt-123", None)
    assert "BLYTE_IMPLEMENTER_MODEL" not in " ".join(plain)


def test_a_run_uses_a_fresh_home_with_only_the_auth_symlink(tmp_path: Path) -> None:
    auth = tmp_path / "real-auth.json"
    auth.write_text("{}")
    d = CodexCliDriver(cli_path=str(_stub(tmp_path)), implementer_model="gemini-3.8-flash-high",
                       report_dir=tmp_path / "reports", auth_file=auth)
    t = d.run(_task(tmp_path), tmp_path, container=FakeContainer())
    call: dict[str, Any] = json.loads((tmp_path / "codex-call.json").read_text())
    assert call["home"] != str(Path.home())
    assert call["files"] == ["auth.json"]
    assert call["auth_link"] == str(auth)
    assert not Path(call["home"]).exists(), "the scratch home is removed after the run"
    assert "run_in_container" in call["stdin"] and "dispatch_blyte" in call["stdin"]
    assert call["stdin"].endswith("## Task\n\nAdd slugify.")
    assert t.success and t.raw_response == "Done: added slugify."
    assert t.conversation_id == "th-1"
    assert t.metrics["frontier_tokens"]["cached_input_tokens"] == 60
    assert t.metrics["dispatches"] == 0 and t.metrics["frontier_cost_usd"] == 0.0
    assert d.harness_name == "codex+blyte"


def test_codex_harness_specs() -> None:
    assert parse_harness_spec("codex") == ("codex", [])
    assert parse_harness_spec("codex+blyte[gemini-3.8-flash-high]") == ("codex+blyte", ["gemini-3.8-flash-high"])
    with pytest.raises(HarnessSpecError):
        parse_harness_spec("codex+blyte")
    with pytest.raises(HarnessSpecError):
        build_harness("codex", "sonnet")
