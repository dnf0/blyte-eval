"""The Condition B execution contract, written down so it stops drifting.

WHY THIS FILE EXISTS
--------------------
Condition B is the architecture the 2026-09-13 frontier benchmark validated at 76.0%
(19/25) against Condition A's 64.0% (16/25). Its defining property is stated plainly in
that report:

    "demonstrating the superiority of ZERO-TURN plan initialization and deterministic
     runtime gating over prompting an LLM to manage its own state loop"

    "Structured state eliminated verbose, repetitive CONVERSATIONAL SCAFFOLDING"
    (95,793 output tokens/solve vs 113,164 for vanilla)

The mechanism is stateless turns: each turn is a fresh headless invocation carrying a
rendered turnkey prompt and nothing else. No chat history, no conversation id, no replay.
That is the thing being measured -- eliminating conversational carry-over is not an
implementation detail of Condition B, it IS Condition B.

THE DRIFT THIS GUARDS AGAINST
-----------------------------
Three arms had quietly reintroduced conversation threading, carrying `conversation_id`
across turns so each turn resumed the previous chat. An arm that does this is no longer
Condition B; it is a hybrid of the state engine and the conversational loop Condition B
was built to replace. The code even acknowledged the cost while doing it:

    # Bounded stateless retry: clear conversation_id to avoid quadratic token bloat
    # & anchoring bias
    conversation_id = None

-- statelessness used as the *recovery* path while running stateful by default, which is
exactly backwards.

WHICH ARMS ARE WHICH
--------------------
From the benchmark report's own labelling:

    Condition A = superstate_agent_mcp
        An autonomous agent invoking state tools in-loop via JSON-RPC. It is SUPPOSED to
        be conversational -- that is the paradigm under test, and the one that scored
        lower. Do not make this arm stateless.

    Condition B = superstate_mcp, superstate_solo, superstate_daemon
        Native runtime, zero-turn injection, stateless turns. These must not thread
        conversation state.

INVARIANTS
----------
1. Zero-turn injection: every turn receives a freshly rendered turnkey prompt.
2. No conversation carry-over between turns.
3. Verification is a deterministic OS gate, not the agent's self-report.
4. Persistence is progress-gated (lease extension / retry budget), not turn-counted alone.
"""

from __future__ import annotations

from typing import Optional

# Arms whose turns must be stateless. Keyed by adapter name.
CONDITION_B_ARMS = frozenset(
    {
        "superstate",
        "superstate_solo",
        "superstate_mcp",
        "superstate_daemon",
    }
)

# Arms that are deliberately conversational because that is the paradigm they represent.
CONDITION_A_ARMS = frozenset({"superstate_agent_mcp"})


def carries_conversation(arm: str) -> bool:
    """Whether this arm may thread a conversation id across turns.

    Condition B arms must not: stateless turnkey turns are the mechanism the validated
    architecture depends on, and the measured token efficiency comes directly from it.
    """
    return arm not in CONDITION_B_ARMS


def conversation_id_for(arm: str, previous: Optional[str]) -> Optional[str]:
    """The conversation id to use for the next turn of `arm`.

    Returns None for Condition B arms regardless of what the driver reported, so a turn
    is always a fresh invocation carrying only its rendered prompt.
    """
    return previous if carries_conversation(arm) else None
