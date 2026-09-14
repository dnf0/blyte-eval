"""Arm-specific behavioural prompt contracts, OFF by default.

WHY THIS SWITCH EXISTS
----------------------
The thesis under test is that managing state produces better performance. That claim is
only measurable if state management is the *only* thing that differs between arms.

It was not. Three arm-specific prompt contracts were being injected, and every one landed
on a superstate arm:

    TARGETED_EXECUTION_CONTRACT        -> superstate, superstate_mcp      (10 rules)
    TARGETED_EXECUTION_CONTRACT_INPLACE-> superstate, superstate_mcp      (10 rules)
    AUTONOMOUS_MCP_EXECUTION_CONTRACT  -> superstate_agent_mcp            (tool tutorial)

`vanilla` and `superpowers` received none. Several of those rules -- "zero global
exploration", "never cat entire files", "targeted verification only" -- improve any
agent's focus and cost with or without a state engine. So published numbers measured
`control plane + hand-tuned prompt` against `neither`, and the lift attributed to the
architecture was partly prompt lift.

The contracts are preserved rather than deleted: they encode real operational practice and
are worth applying deliberately later, to every arm at once. They are simply not part of
the default measurement, so a run reports raw gains from state management alone.

Driver-level guidance (CONTAINER_GUIDANCE_TEMPLATE, CONTAINER_EXEC_SYSTEM_PROMPT) is NOT
gated here: every arm receives it, it describes the environment rather than how to behave
in it, and without it no arm can reach the sandbox at all. The same is true of
MECHANICAL_APPROVAL_PROMPT, which every turn-based arm inherits from TurnBasedAdapter and
which exists to stop an autonomous run stalling on a request for human approval.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("superstate_eval.prompt_contracts")

ENV_FLAG = "SUPERSTATE_EVAL_PROMPT_CONTRACTS"


def contracts_enabled() -> bool:
    """Whether arm-specific behavioural contracts are injected into agent prompts.

    Default OFF. Enable with SUPERSTATE_EVAL_PROMPT_CONTRACTS=1 to reproduce historical
    runs, but note that any arm-vs-arm comparison made with it on is confounded unless
    every arm receives an equivalent contract.
    """
    return os.environ.get(ENV_FLAG, "0").strip().lower() in ("1", "true", "yes", "on")


def apply_contract(prompt: str, contract: str, arm: str) -> str:
    """Append an arm-specific behavioural contract, if the switch is on.

    Returns the prompt unchanged by default, so the run measures state management rather
    than prompt engineering.
    """
    if not contracts_enabled():
        return prompt
    logger.info("Injecting arm-specific prompt contract for %s (%s=1)", arm, ENV_FLAG)
    return f"{prompt}\n\n{contract}"
