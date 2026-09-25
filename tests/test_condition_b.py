"""Condition B is defined by stateless turns; guard against that drifting again."""

from __future__ import annotations

import pathlib

from lab.engine.condition_b import (
    CONDITION_A_ARMS,
    CONDITION_B_ARMS,
    carries_conversation,
    conversation_id_for,
)


def test_condition_b_arms_never_carry_a_conversation() -> None:
    """Zero-turn injection is the mechanism the 76% result was built on.

    Threading a conversation makes the arm a hybrid of the state engine and the
    conversational loop Condition B replaces, and forfeits the output-token efficiency
    the benchmark attributed to "eliminating conversational scaffolding".
    """
    for arm in CONDITION_B_ARMS:
        assert carries_conversation(arm) is False, arm
        assert conversation_id_for(arm, "conv-123") is None, arm


def test_condition_a_remains_conversational() -> None:
    """Condition A is the in-loop paradigm under test; making it stateless would erase it."""
    for arm in CONDITION_A_ARMS:
        assert carries_conversation(arm) is True, arm
        assert conversation_id_for(arm, "conv-123") == "conv-123", arm


def test_no_condition_b_adapter_threads_conversation_directly() -> None:
    """Every carry-over must route through conversation_id_for, or the invariant leaks."""
    offenders = []
    for name in ("superstate.py",):
        path = pathlib.Path("lab/engine/adapters") / name
        for num, line in enumerate(path.read_text().splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "telemetry.conversation_id or conversation_id" in stripped and (
                "conversation_id_for" not in stripped
            ):
                # Allowed only as the argument to conversation_id_for on a prior line.
                window = path.read_text().splitlines()[max(0, num - 3) : num]
                if not any("conversation_id_for" in w for w in window):
                    offenders.append(f"{name}:{num}")
    assert not offenders, f"conversation threaded without the Condition B guard: {offenders}"
