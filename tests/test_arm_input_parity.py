"""Every arm must receive the same inputs, or a comparison measures the harness.

Five separate times, an apparent architectural difference between arms turned out to be one
arm receiving something another did not: model pinning, usage telemetry, container guidance,
`--print-timeout`, and the verification command itself. Each produced a plausible finding
that dissolved on inspection, and each cost a benchmark run.

Documentation did not prevent the fifth. These tests fail instead.
"""

from __future__ import annotations

import pathlib

ADAPTERS = pathlib.Path("lab/engine/adapters")

# Arms whose results are compared against each other in reports.
COMPARED_ARMS = ("superstate.py", "superstate_mcp.py", "superstate_daemon.py")


def test_every_compared_arm_resolves_the_same_verification_command() -> None:
    """All arms must consult GATE_FIXTURES before falling back.

    superstate_mcp.py was missed when fixtures were added. It ran on `true` while
    superstate_daemon ran on a strict hand-written gate, and the daemon lost 5-0 on a
    20-task comparison purely because of that asymmetry.
    """
    missing = [
        name for name in COMPARED_ARMS
        if "agent_gate_for" not in (ADAPTERS / name).read_text()
    ]
    assert not missing, (
        f"these arms do not resolve the shared verification command: {missing}. "
        "An arm-vs-arm result is meaningless while they differ."
    )


def test_no_compared_arm_falls_back_to_true_before_checking_fixtures() -> None:
    """The `true` fallback must come AFTER the fixture lookup, not instead of it."""
    for name in COMPARED_ARMS:
        text = (ADAPTERS / name).read_text()
        if 'else "true"' not in text:
            continue
        fixture_at = text.index("agent_gate_for")
        fallback_at = text.index('else "true"')
        assert fixture_at < fallback_at, (
            f"{name} falls back to 'true' before consulting the fixtures"
        )


def test_daemon_worker_invocation_matches_the_shared_driver() -> None:
    """The daemon spawns its own worker, bypassing AgyCliDriver.

    Each flag AgyCliDriver sets and the wrapper omits has produced a false architectural
    finding: --model (ran a different model), --output-format json (lost all telemetry),
    --print-timeout (truncated every turn at agy's 5-minute default, which read as the
    daemon being unable to do long tasks).
    """
    wrapper_src = (ADAPTERS / "superstate_daemon.py").read_text()
    for flag in ("--model", "--output-format", "--print-timeout", "--add-dir"):
        assert flag in wrapper_src, (
            f"the daemon's worker wrapper omits {flag}, which AgyCliDriver sets for every "
            "other arm. Differences here look like architectural weaknesses."
        )
