"""The legacy MCP arms are gone (superstate #66 deleted the MCP server they drove).

Their results stay in results/ and FINDINGS.md; the arm names must no longer resolve, and no
live module may import the deleted adapters.
"""

import importlib.util
import pathlib
from pathlib import Path

import pytest

from lab.engine.runner import AblationRunner

REMOVED_ARMS = [
    "superstate_mcp", "superstate-mcp", "superstate_rust_mcp", "mcp",
    "superstate_mcp_worktree", "mcp_worktree", "superstate_mcp_planned",
    "superstate_agent_mcp", "agent_mcp", "superstate_agent_mcp_worktree",
    "superstate_agent_mcp_inplace",
]


@pytest.mark.parametrize("arm", REMOVED_ARMS)
def test_removed_arms_no_longer_resolve(arm: str) -> None:
    with pytest.raises(ValueError, match="Unknown evaluation arm"):
        AblationRunner(workspace_root=Path("/tmp"))._get_adapter(arm)


@pytest.mark.parametrize("module", [
    "lab.engine.adapters.superstate_mcp",
    "lab.engine.adapters.superstate_agent_mcp",
])
def test_removed_adapter_modules_are_gone(module: str) -> None:
    assert importlib.util.find_spec(module) is None


def test_the_claude_driver_has_no_superstate_mcp_option() -> None:
    from lab.engine.drivers.claude_cli import ClaudeCliDriver

    with pytest.raises(TypeError):
        ClaudeCliDriver(superstate_mcp=True)  # type: ignore[call-arg]


def test_no_live_code_imports_the_removed_adapters() -> None:
    offenders = [
        str(p)
        for root in ("lab", "scripts")
        for p in pathlib.Path(root).rglob("*.py")
        if any(
            s in p.read_text()
            for s in ("SuperstateMcpAdapter", "SuperstateAgentMcpAdapter",
                      "adapters.superstate_mcp", "adapters.superstate_agent_mcp")
        )
    ]
    assert offenders == []


@pytest.mark.parametrize("arm", ["vanilla", "superpowers"])
def test_the_remaining_arms_still_resolve(arm: str) -> None:
    assert AblationRunner(workspace_root=Path("/tmp"))._get_adapter(arm) is not None
