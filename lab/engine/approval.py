"""Mechanical User and autonomous continuation engine for non-interactive benchmark runs.

Eliminates human-in-the-loop blocking by inspecting agent responses for approval requests,
clarifications, or option prompts, and automatically supplying decisive approvals.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("superstate_eval.approval")

MECHANICAL_APPROVAL_PROMPT: str = (
    "Proceed with the recommended option (Option 1). "
    "Accept all recommended planning decisions and continue autonomously to implement and verify each task. "
    "Do not stop to ask for confirmation; complete the task end-to-end."
)

APPROVAL_SIGNALS: tuple[str, ...] = (
    "how would you like to proceed",
    "should i proceed",
    "would you like me to",
    "please confirm",
    "please review",
    "let me know how you would like",
    "let me know if you would like",
    "let me know if you'd like",
    "do you approve",
    "shall i proceed",
    "ready to proceed",
    "which option would you prefer",
    "what would you like to build",
    "how would you like to continue",
    "choose an execution mode",
    "select an execution mode",
    "looks good to you",
    "look good to you",
    "awaiting spec review",
    "awaiting plan review",
    "any adjustments before",
    "before we proceed",
    "before i proceed",
    "before i write",
)


def is_waiting_for_user_input(response: str) -> bool:
    """Determine whether the agent response is waiting for user feedback, approval, or input.

    Parameters:
        response: Output text or error payload returned by the agent.

    Returns:
        True if the agent prompted for user intervention or decision; False if completed.
    """
    resp = response.strip()
    if not resp:
        return False
    lower = resp.lower()

    # 1. Explicit tool invocation or notification that ask_question was called
    if "the `ask_question` tool has been called" in lower or "`ask_question`" in lower:
        return True

    # 2. State evaluations that pause for user review (State 1: Idea or State 2: Plan)
    if "<state-evaluation>" in lower and "</state-evaluation>" in lower:
        last_eval = lower.rsplit("<state-evaluation>", 1)[-1].split("</state-evaluation>")[0]
        if "state: 1" in last_eval or "state: 2" in last_eval:
            return True

    # 3. Standard approval, confirmation, and planning decision prompts from skills
    if any(sig in lower for sig in APPROVAL_SIGNALS):
        return True

    # 4. If the response ends with a direct question to the user
    non_empty_lines = [line.strip() for line in resp.splitlines() if line.strip()]
    if non_empty_lines and non_empty_lines[-1].rstrip("*_`'\" \t\r\n").endswith("?"):
        return True

    return False


def resolve_next_turn_prompt(agent_output: str) -> Optional[str]:
    """Inspect agent output and return automated approval prompt if waiting, or None if done."""
    if is_waiting_for_user_input(agent_output):
        logger.info("Agent waiting for user input. Dispatched Mechanical Approval prompt.")
        return MECHANICAL_APPROVAL_PROMPT
    return None
