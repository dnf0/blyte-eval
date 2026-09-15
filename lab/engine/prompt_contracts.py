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


# ---------------------------------------------------------------------------
# The generic subset, for testing whether the discipline rules are portable
# ---------------------------------------------------------------------------
#
# TARGETED_EXECUTION_CONTRACT cannot simply be handed to every arm, because half of it is
# scaffolding FOR the state machine rather than advice about how to work:
#
#   rule 1  "the moment THE VERIFICATION COMMAND passes"     -- vanilla has no gate; inert
#   rule 2  "required to pass THE VERIFICATION COMMAND"      -- anchored to the gate
#   rule 4  "run only THE TARGETED TEST COMMAND"             -- anchored to the gate
#   rule 7  "THE ORCHESTRATOR automatically snapshots and commits upon MILESTONE completion"
#           -- for a baseline arm this is simply FALSE, and would mislead the agent into
#              believing its work is committed for it
#   rule 10 "confine ... to THE ACTIVE WORKTREE"             -- partly anchored
#
# The five rules below are the ones that are both true and meaningful without a state
# machine. Giving these to a baseline arm tests whether the discipline is portable:
#
#   * if they lift vanilla as much as the full contract lifts superstate, the rules are
#     doing the work and there is no synergy;
#   * if they lift vanilla much less, the discipline only pays off when there IS a gate to
#     stop at and a milestone to scope to -- which is a stronger claim for the control
#     plane than the original one, and a different claim than "superstate is better".
GENERIC_EXECUTION_RULES = (
    "## EXECUTION DISCIPLINE\n"
    "1. **SCOPE BOUNDARY:** Modify ONLY files directly related to this task. Do not touch unrelated files.\n"
    "2. **ZERO GLOBAL EXPLORATION:** Do not run recursive grep/find across the whole codebase or dump whole directories.\n"
    "3. **ZERO-READ EXECUTION:** Use targeted symbol lookup or line-bounded reads. Never cat entire files into context.\n"
    "4. **NO EXTERNAL LINTER PROBING:** Do not run external linters or formatters. Focus solely on making tests pass.\n"
    "5. **DO NOT READ SKILL OR RULES FILES:** Do not inspect GEMINI.md, AGENTS.md, or .cursorrules."
)

GENERIC_RULES_ENV_FLAG = "SUPERSTATE_EVAL_GENERIC_RULES"


def generic_rules_enabled() -> bool:
    """Whether the portable discipline rules are injected into baseline arms.

    Separate from ENV_FLAG on purpose: this leg tests a different hypothesis (are the rules
    portable?) from the contracts leg (do the rules help superstate?), and conflating them
    would make neither answerable.
    """
    return os.environ.get(GENERIC_RULES_ENV_FLAG, "0").strip().lower() in ("1", "true", "yes", "on")


def apply_generic_rules(prompt: str, arm: str) -> str:
    """Append the portable discipline rules to a baseline arm's prompt, if enabled."""
    if not generic_rules_enabled():
        return prompt
    logger.info("Injecting generic execution rules for %s (%s=1)", arm, GENERIC_RULES_ENV_FLAG)
    return f"{prompt}\n\n{GENERIC_EXECUTION_RULES}"
