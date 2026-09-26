# Remove the Daemon and Relay Arms and the MCP Client — Implementation Plan

> **For agentic workers:** Implement exactly one task. Do NOT `git push`, open PRs, start any benchmark or paid run, or call any model API; commit locally only. This plan is shadow-run: agy and blyte each implement it independently.

**Goal:** Delete the `superstate_daemon*` and `superstate_relay` evaluation arms, their adapters, and the superstate MCP client package (`lab/engine/mcp/`), with every test that exists only for them. Nothing that still runs changes.

**Why:** these arms drove the superstate daemon and relay, which the harness deleted (superstate #66); the MCP client's last user is the daemon adapter. They cannot run against current blyte. Their results stay in `results/` and `FINDINGS.md`, and the code in git history. This is slice 2 of 3: slice 1 (the MCP arms, eval #46) is done; slice 3 (the state-engine `superstate`/`superstate_solo` arms, `condition_b.py`, `prompt_contracts.py`) comes later, so **leave those alone**.

**Tech Stack:** Python 3, pytest, ruff, pyright, `uv`.

## Global Constraints

- Work only in your own worktree (already on its own branch). Run `uv sync` first.
- Do NOT edit `FINDINGS.md`, `EXPERIMENTS.md`, `CLAUDE.md`/`AGENTS.md`, anything under `results/`, or any `scripts/*.sh` launch script. They are the historical record.
- Do NOT touch `lab/engine/mcp_isolation.py`: despite its name it strips agy's own MCP servers and is live.
- Do NOT touch `lab/engine/adapters/superstate.py`, `lab/engine/condition_b.py` or `lab/engine/prompt_contracts.py` (slice 3). Comments elsewhere may still mention the daemon; fix a comment only if it now describes code that no longer exists.
- Arm names that appear only as **data** (e.g. `arm="superstate_daemon_full"` in a telemetry fixture for the reporter, void-outcome summary or offline review, or name sets in `scripts/*.py` analysis scripts) are historical labels. Leave them.
- **Keep coverage that is still valid.** When a test mixes checks of a deleted arm with checks of an arm that stays, delete only the deleted arm's part.
- Commit with `--no-gpg-sign` and the exact message below.

---

### Task 1: Remove the daemon and relay arms and the MCP client

**Delete:**
- `lab/engine/adapters/superstate_daemon.py`
- `lab/engine/adapters/superstate_relay.py`
- `lab/engine/mcp/` (the whole package)
- `tests/test_superstate_daemon_adapter.py`
- `tests/test_superstate_relay_adapter.py`
- `tests/test_superstate_mcp_client.py`
- `tests/test_runner_relay_and_daemon.py`

**Edit** (find each use with `grep -rnE "SuperstateDaemonAdapter|SuperstateRelayAdapter|adapters\.superstate_(daemon|relay)|lab\.engine\.mcp\b|lab\.engine\.mcp\.|superstate_daemon\.py|TDD_MODE" lab tests scripts/*.py`):
- `lab/engine/adapters/__init__.py`: drop the two imports and `__all__` entries.
- `lab/engine/runner.py`: drop the two imports and every `elif` branch that returns one of the two adapters (all `superstate_daemon*`, `daemon*`, `superstate_relay` and `relay` aliases), with comments that only explain those branches. Those names must now fall through to the existing `ValueError("Unknown evaluation arm: ...")`.
- `tests/test_mcp_arms_removed.py`: its `test_the_remaining_arms_still_resolve` parametrization lists `superstate_daemon` and `superstate_relay`; remove those two entries (leave the rest of the file).
- `tests/test_adapters.py`: `test_runner_resolves_daemon_and_solo_adapters` checks the daemon and `superstate_solo`; keep the `superstate_solo` check (rename the test to match), drop the daemon check.
- `tests/test_arm_input_parity.py`: tests whose subject is the daemon adapter (its source file, its spawn command, its read-cache arms, its arm-name distinctness) go; checks of `superstate.py` stay (e.g. drop `superstate_daemon.py` from `COMPARED_ARMS`, keep the rest).
- `tests/test_gate_fixtures.py`, `tests/test_void_outcomes.py`: delete only the test functions that import or read the daemon adapter; their other tests stay.

- [ ] **Step 1: Write the acceptance test.** Create `tests/test_daemon_relay_removed.py`:

```python
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
    "lab.engine.mcp",
])
def test_removed_modules_are_gone(module: str) -> None:
    assert importlib.util.find_spec(module) is None


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
```

- [ ] **Step 2: Run to confirm it fails.** Run: `uv run pytest -q tests/test_daemon_relay_removed.py`. Expected: the removal tests fail; `test_the_remaining_arms_still_resolve` passes.

- [ ] **Step 3: Implement** the deletions and edits above.

- [ ] **Step 4: Verify.** Run `uv run pytest -q tests/test_daemon_relay_removed.py tests/test_mcp_arms_removed.py` (all pass), then `make lint` (ruff and pyright clean; remove imports the deletions left unused).

- [ ] **Step 5: Commit.**

```bash
git add -A lab tests
git commit --no-gpg-sign -m "refactor(eval)!: remove the daemon and relay arms and the superstate MCP client"
```
