# Remove the State-Engine Arms — Implementation Plan

> **For agentic workers:** Implement exactly one task. Do NOT `git push`, open PRs, start any benchmark or paid run, or call any model API; commit locally only. This plan is shadow-run: agy and blyte each implement it independently.

**Goal:** Delete the last bolt-on-era arms: `superstate` / `superstate_python`, `superstate_rust*` and `superstate_solo` (all built on `SuperstateAdapter`, which drives the legacy superstate state engine), in both the ablation runner and the pilot runner. Delete `lab/engine/condition_b.py`, whose only user is that adapter. Afterwards arm mode offers `vanilla` and `superpowers`; harness mode (`--harnesses agy blyte[...]`, the native blyte driver) is untouched.

**Why:** the superstate state engine and CLI these arms drive were deleted from the harness (superstate #66). Slices 1 and 2 (eval #46, #47) removed the MCP, daemon and relay arms; this is slice 3 of 3. Results stay in `results/` and `FINDINGS.md`, and the code in git history.

**Tech Stack:** Python 3, pytest, ruff, pyright, `uv`.

## Global Constraints

- Work only in your own worktree (already on its own branch). Run `uv sync` first.
- Do NOT edit `FINDINGS.md`, `EXPERIMENTS.md`, `CLAUDE.md`/`AGENTS.md`, anything under `results/`, or any `scripts/*.sh` launch script. They are the historical record.
- Do NOT touch the native blyte harness path: `lab/engine/drivers/superstate_native.py`, `lab/engine/harnesses.py`, and `paired_run.py`'s `--driver superstate` / `--harnesses` options. "superstate" there names the native driver (blyte's former name), not the state engine.
- `lab/engine/prompt_contracts.py` stays: `lab/engine/adapters/base.py` uses its generic rules (`apply_generic_rules` and friends) for every arm. Remove from it only what nothing live uses once the adapter is gone (e.g. `apply_contract`, `ENV_FLAG`, `contracts_enabled` if they are then unused), and update its module docstring to match. Keep `tests/test_generic_rules.py` checks of anything that stays.
- Arm names that appear only as **data** (telemetry fixtures, name sets in `scripts/*.py` analysis scripts) are historical labels. Leave them.
- **Keep coverage that is still valid.** When a test mixes checks of a removed arm with checks of an arm that stays (`vanilla`, `superpowers`, the base adapter, the reporter), delete only the removed arm's part.
- Commit with `--no-gpg-sign` and the exact message below.

---

### Task 1: Remove the state-engine arms

**Delete:**
- `lab/engine/adapters/superstate.py`
- `lab/engine/condition_b.py`
- `tests/test_condition_b.py`, `tests/test_state_engine_loop.py`, `tests/test_superstate_resilience.py`, `tests/test_adapter_worktree_symlink.py` (each exists only for the adapter or `condition_b`; confirm before deleting, and keep any test in them that covers live code by moving it)

**Edit** (find each use with `grep -rnE "SuperstateAdapter|adapters\.superstate\b|adapters\.superstate import|condition_b|ENGINE_RUST|ENGINE_PYTHON|find_superstate_binary|TARGETED_EXECUTION_CONTRACT|_extract_plan_milestones" lab tests scripts/*.py`):
- `lab/engine/adapters/__init__.py`: drop the import and `__all__` entry.
- `lab/engine/runner.py`: drop the imports and every branch returning `SuperstateAdapter` (the `superstate*`, `rust*`, `arm_d*`, `solo` aliases). They must fall through to the existing `ValueError`.
- `lab/engine/pilot.py`: the same for `PilotShowdownRunner._get_adapter`, and remove the mock driver's `superstate`-arm special case.
- `scripts/paired_run.py` and `scripts/pilot_run.py`: the `--arms` default is `["vanilla", "superpowers", "superstate"]`; make it `["vanilla", "superpowers"]`. Fix a help string or comment only where it describes the removed arms.
- `lab/engine/prompt_contracts.py`: see Global Constraints.
- Tests: in `tests/test_adapters.py`, `tests/test_arm_input_parity.py`, `tests/test_generic_rules.py`, `tests/test_mcp_arms_removed.py` and `tests/test_daemon_relay_removed.py`, remove only what uses the removed adapter or arms (the two `*_removed.py` files list `superstate`/`superstate_solo` among the arms that still resolve: drop those entries). If `tests/test_arm_input_parity.py` has nothing left to compare, delete it.

- [ ] **Step 1: Write the acceptance test.** Create `tests/test_state_engine_arms_removed.py`:

```python
"""The state-engine arms are gone (superstate #66 deleted the state engine they drove).

Arm mode now offers vanilla and superpowers; harness mode (the native blyte driver) is
untouched. Results stay in results/ and FINDINGS.md."""

import importlib.util
import pathlib
from pathlib import Path

import pytest

from lab.engine.pilot import PilotShowdownRunner
from lab.engine.runner import AblationRunner

REMOVED_ARMS = [
    "superstate", "superstate_python", "superstate-python",
    "superstate_rust", "superstate-rust", "rust", "arm_d",
    "superstate_rust_planned", "superstate_rust_2phase",
    "superstate_rust_inplace", "rust_inplace",
    "superstate_solo", "superstate-solo", "solo",
]


def _gone(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is None
    except ModuleNotFoundError:
        return True


@pytest.mark.parametrize("arm", REMOVED_ARMS)
def test_removed_arms_no_longer_resolve_in_the_ablation_runner(arm: str) -> None:
    with pytest.raises(ValueError, match="Unknown evaluation arm"):
        AblationRunner(workspace_root=Path("/tmp"))._get_adapter(arm)


@pytest.mark.parametrize("arm", ["superstate", "superstate_rust", "superstate_rust_planned",
                                 "superstate_rust_inplace", "superstate_rust_fast"])
def test_removed_arms_no_longer_resolve_in_the_pilot_runner(arm: str) -> None:
    with pytest.raises(ValueError, match="Unknown evaluation arm"):
        PilotShowdownRunner.__new__(PilotShowdownRunner)._get_adapter(arm)


@pytest.mark.parametrize("module", ["lab.engine.adapters.superstate", "lab.engine.condition_b"])
def test_removed_modules_are_gone(module: str) -> None:
    assert _gone(module)


def test_no_live_code_uses_the_removed_modules() -> None:
    needles = ("SuperstateAdapter", "adapters.superstate import", "adapters.superstate ",
               "condition_b")
    offenders = [
        str(p)
        for root in ("lab", "scripts", "tests")
        for p in pathlib.Path(root).rglob("*.py")
        if p.name != "test_state_engine_arms_removed.py"
        and any(n in p.read_text() for n in needles)
    ]
    assert offenders == []


@pytest.mark.parametrize("arm", ["vanilla", "superpowers"])
def test_the_remaining_arms_still_resolve(arm: str) -> None:
    assert AblationRunner(workspace_root=Path("/tmp"))._get_adapter(arm) is not None
    assert PilotShowdownRunner.__new__(PilotShowdownRunner)._get_adapter(arm) is not None


def test_the_generic_rules_survive() -> None:
    from lab.engine.prompt_contracts import apply_generic_rules

    assert callable(apply_generic_rules)


def test_the_native_harness_path_is_untouched() -> None:
    from lab.engine.drivers.superstate_native import SuperstateNativeDriver
    from lab.engine.harnesses import parse_harness_spec

    assert SuperstateNativeDriver is not None
    assert parse_harness_spec("blyte[folded]")[0] == "blyte"
```

- [ ] **Step 2: Run to confirm it fails.** Run: `uv run pytest -q tests/test_state_engine_arms_removed.py`. Expected: the removal tests fail; the remaining-arms, generic-rules and native-harness tests pass.

- [ ] **Step 3: Implement** the deletions and edits above.

- [ ] **Step 4: Verify.** Run `uv run pytest -q tests/test_state_engine_arms_removed.py tests/test_mcp_arms_removed.py tests/test_daemon_relay_removed.py` (all pass), then `make lint` (ruff and pyright clean; remove imports the deletions left unused).

- [ ] **Step 5: Commit.**

```bash
git add -A lab tests scripts
git commit --no-gpg-sign -m "refactor(eval)!: remove the state-engine arms (the state engine was deleted from the harness)"
```
