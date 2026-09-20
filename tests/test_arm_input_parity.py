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


def test_daemon_reports_driver_turns_not_state_steps() -> None:
    """`turns` must count worker invocations in every arm, or arms cannot be compared.

    The daemon once reported its state-machine `step` counter as `turns`. A step
    advances on a transition whether or not the worker ran, so every gated daemon run
    recorded turns=2 while the wrapper had captured a single driver invocation in 19
    of 20 -- making a dormant iteration loop look active.
    """
    src = (
        pathlib.Path(__file__).resolve().parents[1]
        / "lab/engine/adapters/superstate_daemon.py"
    ).read_text(encoding="utf-8")

    assert "turns=max(1, driver_turns)" in src, (
        "daemon must report driver invocations as `turns`"
    )
    assert "turns=max(1, self.step_count)" not in src, (
        "daemon must not report state-machine steps as `turns`"
    )
    assert '"daemon_steps": self.step_count' in src, (
        "step count is still worth recording -- under its own name, in provenance"
    )


def test_every_arm_name_resolves_to_a_distinct_adapter_name() -> None:
    """Two configurations must never report the same name, or results pool them silently.

    `superstate_mcp_planned` is the multi-milestone configuration and `superstate_mcp` the
    zero-turn one. Both returned harness_name="superstate_mcp" until 2026-09-17, so running
    them together would have written one indistinguishable set of rows and the comparison
    the run existed to make would have been invisible.
    """
    from lab.engine.runner import AblationRunner

    runner = AblationRunner.__new__(AblationRunner)
    pairs = [
        ("superstate_mcp", "superstate_mcp_planned"),
        ("superstate_rust", "superstate_rust_planned"),
        ("superstate_daemon", "superstate_daemon_review"),
        ("superstate_daemon_review", "superstate_daemon_rollback"),
        ("superstate_daemon_rollback", "superstate_daemon_full"),
    ]
    for zero_turn, planned in pairs:
        a = runner._get_adapter(zero_turn)  # noqa: SLF001
        b = runner._get_adapter(planned)  # noqa: SLF001
        assert a.name != b.name, (
            f"{zero_turn!r} and {planned!r} both report {a.name!r}; "
            "results from the two would be pooled"
        )
        if "full" in planned:
            suffix = "full"
            assert getattr(b, "impact_slicing", False) is True, f"{planned!r} must have impact_slicing=True"
            assert getattr(b, "auto_rollback", False) is True, f"{planned!r} must have auto_rollback=True"
        elif "rollback" in planned:
            suffix = "rollback"
        elif "review" in planned:
            suffix = "review"
        else:
            suffix = "planned"
        assert suffix in b.name, f"{planned!r} must be identifiable in results, got {b.name!r}"


def test_no_adapter_synthesizes_milestones_or_harness_prompts() -> None:
    """Adapters are passive translation shims. They must NEVER synthesize task milestones or prompt engineering.

    In September 2026, an adapter synthesized a 2-node TDD milestone DAG with hardcoded
    Python files (tests/test_reproduce_issue.py) and pytest commands in the evaluation harness.
    This was harness-level prompt engineering: it broke cross-language tasks (TypeScript/Go),
    forced artificial turns on simple tasks, and violated arm input parity.

    All task decomposition and milestone planning must originate either from the benchmark
    specification itself or autonomously from Superstate inside the target binary, never
    from synthetic adapter code in superstate-eval.
    """
    for name in COMPARED_ARMS:
        text = (ADAPTERS / name).read_text()
        assert "def _build_tdd_milestones" not in text, (
            f"{name} contains synthetic milestone generation. Adapters must not decompose tasks."
        )
        assert "tdd_dag" not in text, (
            f"{name} contains synthetic DAG flags. Adapters must not script execution DAGs."
        )
        assert "test_reproduce_issue.py" not in text, (
            f"{name} contains hardcoded test file injections. Adapters must not prompt-engineer."
        )


def test_no_adapter_uses_raw_substring_matching_for_sealed_grader() -> None:
    """Adapters must use `references_sealed_grader()` rather than raw `"/tests/" in cmd`.

    A raw substring match on `"/tests/"` rejects or falsely passes in-repo test suites like
    `/app/pyknotid/tests/`, treating legitimate package tests as if they were the container-root
    sealed grader at `/tests/`.
    """
    for name in COMPARED_ARMS:
        text = (ADAPTERS / name).read_text()
        assert '"/tests/" in' not in text, (
            f"{name} uses raw `\"/tests/\" in` substring matching. Use `references_sealed_grader()`."
        )

