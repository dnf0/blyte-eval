# Remove the Legacy MCP Arms — Implementation Plan

> **For agentic workers:** Implement exactly one task. Do NOT `git push`, open PRs, start any benchmark or paid run, or call any model API; commit locally only. This plan is shadow-run: agy and blyte each implement it independently.

**Goal:** Delete the `superstate_mcp*` and `superstate_agent_mcp*` evaluation arms, their adapters, and the Claude driver's `superstate_mcp` option, with every test that exists only for them. Nothing that still runs changes.

**Why:** these arms drove the superstate MCP server, which the harness deleted (superstate #66). They cannot be run against current blyte, and no MCP arm has run since EXP-065. Their results stay in `results/` and `FINDINGS.md`, and the code stays in git history. This is the first of three slices removing the bolt-on era; the daemon, relay and MCP client (slice 2) and the state-engine arms (slice 3) come later, so **leave those alone**.

**Tech Stack:** Python 3, pytest, ruff, pyright, `uv`.

## Global Constraints

- Work only in your own worktree (already on its own branch). Run `uv sync` first.
- Do NOT edit `FINDINGS.md`, `EXPERIMENTS.md`, `CLAUDE.md`/`AGENTS.md`, anything under `results/`, or any `scripts/*.sh` launch script. They are the historical record.
- Do NOT touch the MCP client (`lab/engine/mcp/`): `lab/engine/adapters/superstate_daemon.py` still imports it (slice 2).
- Do NOT touch `lab/engine/condition_b.py`, `lab/engine/prompt_contracts.py`, `lab/engine/adapters/superstate.py`, `superstate_daemon.py` or `superstate_relay.py` (slices 2 and 3). Their comments may still mention `superstate_mcp`; that is fine.
- Arm names that appear only as **data** in tests (e.g. `arm="superstate_mcp"` in a telemetry fixture for the reporter, extractor or offline review) are historical labels, not uses of the adapter. Leave them.
- Commit with `--no-gpg-sign` and the exact message below.

---

### Task 1: Remove the MCP arms

**Delete:**
- `lab/engine/adapters/superstate_mcp.py`
- `lab/engine/adapters/superstate_agent_mcp.py`
- `tests/test_superstate_mcp_adapter.py`
- `tests/test_superstate_agent_mcp.py`

**Edit** (find each use with `grep -rnE "SuperstateMcpAdapter|SuperstateAgentMcpAdapter|adapters\.superstate_(agent_)?mcp|superstate_mcp=" lab tests scripts/*.py`):
- `lab/engine/adapters/__init__.py`: drop the two imports and `__all__` entries.
- `lab/engine/runner.py`: drop the two imports and every `elif` branch that returns one of the two adapters (all `superstate_mcp*`, `mcp`, `mcp_worktree`, `superstate_agent_mcp*`, `agent_mcp*` aliases). Those names must now fall through to the existing `ValueError("Unknown evaluation arm: ...")`. Fix any comment that only explains a deleted branch.
- `lab/engine/drivers/claude_cli.py`: remove the `superstate_mcp` constructor parameter and everything that exists only to serve it (the attribute, the MCP-config entry it adds, and its part of the `container_id or self.superstate_mcp` condition). Keep `superstate_bin` and `find_superstate_binary` only if something else still uses them; otherwise remove them too, and with them the import from `lab.engine.mcp.client`.
- Tests that construct or resolve the deleted adapters, or pass `superstate_mcp=True`: delete those test functions (or parametrize cases), in `tests/test_runner.py`, `tests/test_adapters.py` and `tests/test_claude_cli_driver.py`.
- Tests that read the deleted source files by name: `tests/test_arm_input_parity.py` and `tests/test_condition_b.py` loop over `superstate_mcp.py`. Drop that file from their lists and keep the checks for the files that remain. Delete a test whose only subject was a deleted adapter.

- [ ] **Step 1: Write the acceptance test.** Create `tests/test_mcp_arms_removed.py`:

```python
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


@pytest.mark.parametrize("arm", ["vanilla", "superpowers", "superstate", "superstate_daemon", "superstate_relay"])
def test_the_remaining_arms_still_resolve(arm: str) -> None:
    assert AblationRunner(workspace_root=Path("/tmp"))._get_adapter(arm) is not None
```

- [ ] **Step 2: Run to confirm it fails.** Run: `uv run pytest -q tests/test_mcp_arms_removed.py`. Expected: the removal tests fail; `test_the_remaining_arms_still_resolve` passes.

- [ ] **Step 3: Implement** the deletions and edits above.

- [ ] **Step 4: Verify.** Run `uv run pytest -q tests/test_mcp_arms_removed.py` (all pass), then `make lint` (ruff and pyright clean; remove imports the deletions left unused).

- [ ] **Step 5: Commit.**

```bash
git add -A lab tests
git commit --no-gpg-sign -m "refactor(eval)!: remove the legacy MCP arms (the MCP server was deleted from the harness)"
```
