"""Mechanical User and Autonomous Human-in-the-Loop Interceptor.

Prevents benchmark evaluation stall-outs by intercepting agent prompts,
clarifying questions, and planning confirmation gates, delivering automated
mechanical approval.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("superstate_eval.approval")

MECHANICAL_APPROVAL_PROMPT = (
    "Proceed with the recommended option (Option 1). Do not pause for human feedback or approval. "
    "Execute all tasks autonomously to completion, write tests, verify changes, and finalize your work."
)

APPROVAL_SIGNALS = [
    "proceed with option",
    "how would you like to proceed",
    "should i proceed",
    "would you like me to proceed",
    "do you approve",
    "please approve",
    "select an option",
    "which option would you prefer",
    "please confirm",
    "confirm whether to proceed",
    "awaiting your confirmation",
    "awaiting user input",
    "select an execution mode",
    "ready to execute plan?",
]

INTERACTIVE_QUESTION_PREFIXES = (
    "should i",
    "would you like",
    "do you want",
    "how would you like",
    "shall i",
    "please confirm",
    "please let me know",
    "can you confirm",
    "which option",
    "which approach",
    "which of these",
    "what would you like",
)


def is_waiting_for_user_input(response: str) -> bool:
    """Analyze agent response text to detect if the agent paused for human approval or clarification.

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

    # 4. If the response ends with an interactive question to the user (not a rhetorical question)
    non_empty_lines = [line.strip() for line in resp.splitlines() if line.strip()]
    if non_empty_lines:
        last_line = non_empty_lines[-1].rstrip("*_`'\" \t\r\n").lower()
        if last_line.endswith("?"):
            if any(
                last_line.startswith(prefix) or f" {prefix} " in f" {last_line} "
                for prefix in INTERACTIVE_QUESTION_PREFIXES
            ):
                return True
            if "option 1" in lower or "proceed with" in lower or "confirm" in lower:
                return True

    return False


def resolve_next_turn_prompt(agent_output: str) -> Optional[str]:
    """Inspect agent output and return automated approval prompt if waiting, or None if done."""
    if is_waiting_for_user_input(agent_output):
        logger.info("Agent waiting for user input. Dispatched Mechanical Approval prompt.")
        return MECHANICAL_APPROVAL_PROMPT
    return None
