"""The generic-rules leg tests whether execution discipline is portable off superstate."""

from __future__ import annotations

import os
from unittest.mock import patch

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.vanilla import VanillaAdapter
from lab.engine.prompt_contracts import (
    GENERIC_EXECUTION_RULES,
    GENERIC_RULES_ENV_FLAG,
    apply_generic_rules,
    generic_rules_enabled,
)


def _task() -> TaskSpec:
    return TaskSpec(id="t/x", name="x", instruction="DO THE WORK", docker_image="img:latest")


def test_generic_rules_are_off_by_default() -> None:
    """The default measurement gives baselines the bare instruction, as it always has."""
    with patch.dict(os.environ, {}, clear=True):
        assert generic_rules_enabled() is False
        assert VanillaAdapter().get_initial_prompt(_task()) == "DO THE WORK"


def test_generic_rules_reach_the_baseline_arm_when_enabled() -> None:
    with patch.dict(os.environ, {GENERIC_RULES_ENV_FLAG: "1"}, clear=True):
        prompt = VanillaAdapter().get_initial_prompt(_task())
    assert prompt.startswith("DO THE WORK")
    assert "EXECUTION DISCIPLINE" in prompt
    assert "ZERO GLOBAL EXPLORATION" in prompt


def test_generic_rules_exclude_every_superstate_anchored_rule() -> None:
    """Half of TARGETED_EXECUTION_CONTRACT is scaffolding for the state machine.

    Rule 7 in particular ("the orchestrator automatically snapshots and commits upon
    milestone completion") is simply false for a baseline arm and would mislead the agent
    into believing its work is committed for it. Rules 1, 2 and 4 are anchored to a
    verification command the baselines do not have.
    """
    for anchored in (
        "verification command",
        "orchestrator",
        "milestone",
        "worktree",
        "targeted test command",
    ):
        assert anchored.lower() not in GENERIC_EXECUTION_RULES.lower(), (
            f"generic rules must not reference superstate machinery: {anchored}"
        )


def test_the_two_legs_are_independently_switchable() -> None:
    """Conflating the flags would make neither hypothesis answerable."""
    from lab.engine.prompt_contracts import ENV_FLAG, contracts_enabled

    with patch.dict(os.environ, {GENERIC_RULES_ENV_FLAG: "1"}, clear=True):
        assert generic_rules_enabled() is True
        assert contracts_enabled() is False
    with patch.dict(os.environ, {ENV_FLAG: "1"}, clear=True):
        assert contracts_enabled() is True
        assert generic_rules_enabled() is False
    assert apply_generic_rules("P", "vanilla") == "P"
