"""Tests for Mechanical User and Autonomous Human-in-the-Loop Elimination."""

from __future__ import annotations

from lab.engine.approval import (
    MECHANICAL_APPROVAL_PROMPT,
    is_waiting_for_user_input,
    resolve_next_turn_prompt,
)


def test_is_waiting_for_user_input_detects_ask_question_tool() -> None:
    output = (
        "I need some clarification. The `ask_question` tool has been called with options A and B."
    )
    assert is_waiting_for_user_input(output) is True


def test_is_waiting_for_user_input_detects_superpowers_state_gates() -> None:
    output = (
        "<state-evaluation>\n"
        "State: 1. Idea / Request Received\n"
        "Required Skill: brainstorming\n"
        "</state-evaluation>\n"
        "Here are two design options. Which would you prefer?"
    )
    assert is_waiting_for_user_input(output) is True


def test_is_waiting_for_user_input_detects_standard_approval_prompts() -> None:
    samples = [
        "How would you like to proceed?",
        "Should I proceed with creating these files?",
        "Do you approve this implementation plan?",
        "Would you like me to run the tests now?",
        "Please confirm if this matches your expectation.",
        "Select an execution mode to continue:",
    ]
    for s in samples:
        assert is_waiting_for_user_input(s) is True, f"Failed to detect: {s}"


def test_is_waiting_for_user_input_ignores_normal_completions() -> None:
    samples = [
        "Implementation complete. All 12 unit tests pass.",
        "Fixed the issue by adding validation in user.py.",
        "Refactoring complete.",
        "What did this accomplish? It simplified the routing table.",
        "Why was this needed? The base commit had a memory leak.",
    ]
    for s in samples:
        assert is_waiting_for_user_input(s) is False, f"False positive on: {s}"


def test_resolve_next_turn_prompt_returns_mechanical_approval() -> None:
    prompt = resolve_next_turn_prompt("Should I proceed with Option 1?")
    assert prompt is not None
    assert prompt == MECHANICAL_APPROVAL_PROMPT
    assert "Proceed with the recommended option" in prompt


def test_resolve_next_turn_prompt_returns_none_when_no_input_needed() -> None:
    assert resolve_next_turn_prompt("Task finished successfully.") is None
