"""The daemon and relay arms and the superstate MCP client are gone (superstate #66 deleted
the daemon, relay and MCP server they drove). Their results stay in results/ and FINDINGS.md."""

import importlib.util
import pathlib
from pathlib import Path

import pytest

from lab.engine.runner import AblationRunner

REMOVED_ARMS = [
    "superstate_daemon", "superstate-daemon", "daemon",
    "superstate_daemon_review", "daemon_review",
    "superstate_daemon_sliced", "daemon_sliced",
    "superstate_daemon_rollback", "daemon_rollback",
    "superstate_daemon_full", "daemon_full",
    "superstate_daemon_stall", "daemon_stall",
    "superstate_daemon_regression", "daemon_regression",
    "superstate_daemon_cache", "daemon_cache",
    "superstate_daemon_nocache", "daemon_nocache",
    "superstate_relay", "superstate-relay", "relay",
]


@pytest.mark.parametrize("arm", REMOVED_ARMS)
def test_removed_arms_no_longer_resolve(arm: str) -> None:
    with pytest.raises(ValueError, match="Unknown evaluation arm"):
        AblationRunner(workspace_root=Path("/tmp"))._get_adapter(arm)


@pytest.mark.parametrize("module", [
    "lab.engine.adapters.superstate_daemon",
    "lab.engine.adapters.superstate_relay",
    # The client module, not the package: a stale lab/engine/mcp/__pycache__ left in an existing
    # checkout makes the bare package importable as a namespace package.
    "lab.engine.mcp.client",
])
def test_removed_modules_are_gone(module: str) -> None:
    try:
        spec = importlib.util.find_spec(module)
    except ModuleNotFoundError:  # its parent package is gone too
        spec = None
    assert spec is None


def test_no_live_code_imports_the_removed_modules() -> None:
    needles = ("SuperstateDaemonAdapter", "SuperstateRelayAdapter", "adapters.superstate_daemon",
               "adapters.superstate_relay", "lab.engine.mcp.", "from lab.engine.mcp ")
    offenders = [
        str(p)
        for root in ("lab", "scripts", "tests")
        for p in pathlib.Path(root).rglob("*.py")
        if p.name != "test_daemon_relay_removed.py" and any(n in p.read_text() for n in needles)
    ]
    assert offenders == []


@pytest.mark.parametrize("arm", ["vanilla", "superpowers", "superstate", "superstate_solo"])
def test_the_remaining_arms_still_resolve(arm: str) -> None:
    assert AblationRunner(workspace_root=Path("/tmp"))._get_adapter(arm) is not None
