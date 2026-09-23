"""MCP isolation must never leave the user's setup broken.

The mechanism is global state with no per-invocation flag, and CLAUDE.md's standing warning is
that a crashed run leaves the servers disabled. These tests exist for the failure modes, not
the happy path.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lab.engine import mcp_isolation


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    path = tmp_path / "mcp_config.json"
    path.write_text(json.dumps({"mcpServers": {
        "slack": {"command": "npx", "args": ["slack"]},
        "github": {"command": "npx", "args": ["gh"]},
        "notion": {"command": "npx", "args": ["notion"]},
        "superstate": {"command": "superstate", "args": ["mcp"]},
    }}), encoding="utf-8")
    monkeypatch.setattr(mcp_isolation, "MCP_CONFIG", path)
    monkeypatch.setattr(mcp_isolation, "STASH", path.with_suffix(".json.stash"))
    return path


def _servers(path: Path) -> set[str]:
    return set(json.loads(path.read_text())["mcpServers"])


def test_strips_the_unrelated_servers_and_keeps_superstate(cfg):
    # superstate is Condition B's transport -- stripping it would change what is under test
    # rather than what surrounds it.
    with mcp_isolation.stripped_mcp_servers() as stripped:
        assert _servers(cfg) == {"superstate"}
        assert stripped == ["github", "notion", "slack"]
    assert _servers(cfg) == {"slack", "github", "notion", "superstate"}


def test_restores_even_when_the_run_raises(cfg):
    with pytest.raises(RuntimeError):
        with mcp_isolation.stripped_mcp_servers():
            assert _servers(cfg) == {"superstate"}
            raise RuntimeError("run exploded")
    assert _servers(cfg) == {"slack", "github", "notion", "superstate"}, "a crash must not degrade the user's setup"


def test_self_heals_from_a_previous_run_that_died(cfg):
    """The case a try/finally cannot cover: the process was killed outright."""
    # Simulate a killed run: stash holds the original, live config is the stripped stub.
    original = cfg.read_text()
    mcp_isolation.STASH.write_text(original, encoding="utf-8")
    cfg.write_text(json.dumps({"mcpServers": {"superstate": {}}}), encoding="utf-8")

    with mcp_isolation.stripped_mcp_servers():
        pass

    assert _servers(cfg) == {"slack", "github", "notion", "superstate"}, (
        "the next run must repair what a killed run left behind"
    )
    assert not mcp_isolation.STASH.exists()


def test_disabled_is_a_no_op(cfg):
    with mcp_isolation.stripped_mcp_servers(enabled=False) as stripped:
        assert stripped == []
        assert _servers(cfg) == {"slack", "github", "notion", "superstate"}


def test_missing_config_does_not_break_a_run(cfg):
    cfg.unlink()
    with mcp_isolation.stripped_mcp_servers() as stripped:
        assert stripped == []


def test_the_original_is_moved_not_copied(cfg):
    """The config holds live credentials; a copy would put a second copy of them on disk."""
    inode_before = cfg.stat().st_ino
    with mcp_isolation.stripped_mcp_servers():
        assert mcp_isolation.STASH.stat().st_ino == inode_before, (
            "the stash must be the SAME inode, i.e. renamed rather than copied"
        )
    assert cfg.stat().st_ino == inode_before
