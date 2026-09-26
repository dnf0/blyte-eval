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
COMPARED_ARMS = ("superstate.py",)


def test_no_compared_arm_consults_a_hand_authored_gate_table() -> None:
    """Parity is now maintained by removing the shared fixture table, not by sharing it.

    Until 2026-09-21 this file asserted the opposite: every arm had to call `agent_gate_for`,
    because `superstate_mcp.py` was once missed when fixtures were added and lost 5-0 on a
    20-task comparison purely from that asymmetry. Manifesto Invariant V then removed the
    table itself -- a hand-authored gate leaks the answer's shape and turns diagnosis into
    test-passing -- so the parity requirement inverts: no arm may consult one.
    """
    offenders = [
        name for name in COMPARED_ARMS
        if "agent_gate_for" in (ADAPTERS / name).read_text()
    ]
    assert not offenders, (
        f"these arms consult a hand-authored gate table: {offenders}. See "
        f"lab/benchmarks/gate_fixtures.py and docs/EVALUATION-PHILOSOPHY.md Invariant 2."
    )


def test_an_ungated_arm_says_so() -> None:
    """An arm that cannot gate must announce it rather than let `true` look like a verdict.

    `superstate` is single-milestone by construction, so it cannot
    run the RED/GREEN DAG that replaced the fixtures. On a task with no native runner it
    is genuinely ungated, and an ungated run measures the fallback, not the execution model.
    """
    for name in ("superstate.py",):
        text = (ADAPTERS / name).read_text()
        assert 'else "true"' in text, f"{name} no longer has the fallback this test guards"
        assert "UNGATED" in text, (
            f"{name} falls back to 'true' without warning that the run is ungated and "
            f"not comparable with a daemon arm."
        )


def test_every_arm_name_resolves_to_a_distinct_adapter_name() -> None:
    """Two configurations must never report the same name, or results pool them silently."""
    from lab.engine.runner import AblationRunner

    runner = AblationRunner.__new__(AblationRunner)
    pairs = [
        ("superstate_rust", "superstate_rust_planned"),
    ]
    for zero_turn, planned in pairs:
        a = runner._get_adapter(zero_turn)  # noqa: SLF001
        b = runner._get_adapter(planned)  # noqa: SLF001
        assert a.name != b.name, (
            f"{zero_turn!r} and {planned!r} both report {a.name!r}; "
            "results from the two would be pooled"
        )
        assert "planned" in b.name, f"{planned!r} must be identifiable in results, got {b.name!r}"


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


def test_every_arm_records_which_gating_regime_produced_its_numbers() -> None:
    """A results file must be able to answer "how many of these tasks were gated?".

    CLAUDE.md requires a write-up to state that, and the helper it named (`agent_gate_for`)
    was removed with the fixture table. `gate_source` replaces it: autonomous_tdd when the
    engine derived a RED/GREEN DAG, native_runner when the task shipped its own runner, and
    ungated when neither applied. The regimes have different failure modes, so a number is
    not interpretable without knowing which produced it.
    """
    from lab.engine.adapters.superstate import SuperstateAdapter

    for adapter in (SuperstateAdapter(),):
        provenance = adapter.get_provenance()
        assert "gate_source" in provenance, (
            f"{type(adapter).__name__} does not record its gating regime, so its results "
            f"cannot be read without guessing."
        )


def test_the_superseded_arms_are_labelled_as_such() -> None:
    """The state-engine arms are kept, not developed.

    They are retained so the results they produced stay reproducible, which is why the label
    lives in provenance rather than the arms being deleted.
    """
    from lab.engine.adapters.superstate import SuperstateAdapter

    for adapter in (SuperstateAdapter(),):
        assert adapter.get_provenance().get("deprecated_arm") is True
