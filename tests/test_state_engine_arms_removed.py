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
