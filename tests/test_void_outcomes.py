"""A run that produced no measurement must never be scored as a task failure.

Regression cover for FINDINGS 13.20: `build-cython-ext` passed 17 of 18 runs, then failed
seven consecutive canaries in 5-8 seconds at $0.00 because autonomous TDD cannot derive a gate
from the empty `/app` the task deliberately ships. It was recorded `passed=False` every time,
so every canary pass rate from EXP-074 to EXP-080 was over three tasks of which one could not
be scored at all.
"""

from __future__ import annotations

from lab.engine.budget_policy import RunTelemetry
from lab.engine.reporter import generate_comparison_summary, render_summary_table
from lab.engine.void import (
    UNGATEABLE_PREFIX,
    UNMEASURABLE_PREFIX,
    is_void,
    void_kind,
)


def _run(task, passed, reason=None, cost=1.0):
    return RunTelemetry(
        task_id=task, arm="superstate_daemon_full", passed=passed,
        wall_clock_sec=100.0, cost_usd=cost, input_tokens=1000, output_tokens=100,
        failure_reason=reason,
    )


def test_void_markers_are_recognised_anywhere_in_the_reason():
    # The runner composes a reason from the agent-side cause and the grading message, so the
    # marker can land mid-string. Matching only a prefix would miss exactly the real case.
    assert is_void(f"{UNGATEABLE_PREFIX} could not identify a test runner")
    assert is_void(f"{UNMEASURABLE_PREFIX} no held-out tests/")
    assert is_void(f"something | {UNGATEABLE_PREFIX} nested")
    assert not is_void("Verification failed: Reward was 0.0 < 1.0")
    assert not is_void(None)


def test_void_kind_separates_arm_gaps_from_task_gaps():
    # The distinction decides what you fix: an unmeasurable TASK leaves the corpus, an
    # ungateable run is a gap in the ARM.
    assert void_kind(f"{UNGATEABLE_PREFIX} x") == "ungateable"
    assert void_kind(f"{UNMEASURABLE_PREFIX} x") == "unmeasurable"
    assert void_kind("Verification failed") is None


def test_ungateable_run_leaves_the_pass_rate_denominator():
    """The exact EXP-080 shape: two scored near-misses and one run that never started."""
    runs = [
        _run("scc", False),
        _run("katex", False),
        _run("build-cython-ext", False,
             f"{UNGATEABLE_PREFIX} could not identify a test runner", cost=0.0),
    ]
    summary = generate_comparison_summary(runs)["superstate_daemon_full"]

    assert summary["total_tasks"] == 2, "the ungateable run must not be scored"
    assert summary["attempted_tasks"] == 3, "but it must still be visible as attempted"
    assert summary["void"] == 1
    assert summary["void_kinds"] == {"ungateable": 1}
    assert summary["failures"] == 2, "two real failures, not three"


def test_a_pass_rate_is_computed_over_scored_runs_only():
    runs = [
        _run("a", True),
        _run("b", False),
        _run("void", False, f"{UNGATEABLE_PREFIX} no runner", cost=0.0),
    ]
    summary = generate_comparison_summary(runs)["superstate_daemon_full"]
    # 1 of 2 scored, not 1 of 3. Before this fix the same runs reported 33.3%.
    assert summary["pass_rate_pct"] == 50.0


def test_void_count_is_rendered_not_merely_excluded():
    """Silently dropping a void run hides that the corpus shrank -- show it."""
    runs = [_run("a", True), _run("v", False, f"{UNMEASURABLE_PREFIX} no grader", cost=0.0)]
    table = render_summary_table(generate_comparison_summary(runs))
    assert "Void" in table, f"summary table must carry a Void column:\n{table}"


def test_cost_still_counts_every_run_attempted():
    # A void run that burned money must not vanish from the spend, only from the score.
    runs = [_run("a", True, cost=2.0), _run("v", False, f"{UNGATEABLE_PREFIX} x", cost=0.5)]
    summary = generate_comparison_summary(runs)["superstate_daemon_full"]
    assert summary["total_cost_usd"] == 2.5


def test_adapter_marks_an_ungateable_run_and_runner_does_not_relabel_it(tmp_path):
    """End to end through the two places the old behaviour went wrong.

    The adapter must emit the marker when TDD handoff fails, and the runner must not wrap it
    in "Agent run failed:" -- that wrapping is what made seven runs that never started read as
    seven runs the agent lost.
    """
    from unittest.mock import patch

    from lab.benchmarks.task_loader import TaskSpec
    from lab.engine.adapters.superstate_daemon import SuperstateDaemonAdapter

    adapter = SuperstateDaemonAdapter(driver_preset="agy", poll_interval_sec=0.01)

    task = TaskSpec(
        id="build-cython-ext",
        name="build-cython-ext",
        instruction="clone pyknotid into /app and build the extension",
        docker_image="test:latest",
        verification_cmd="bash /tests/test.sh",
    )

    # Stand in for the real failure: `tdd.rs` refusing to emit a gate it cannot derive.
    def _fail(*_a, **_k):
        adapter._ungateable_reason = f"{UNGATEABLE_PREFIX} could not identify a test runner"
        return False

    with patch.object(adapter, "_init_daemon_state", side_effect=_fail):
        result = adapter.execute(tmp_path, task)

    assert result.success is False
    assert is_void(result.error_message), (
        f"an ungateable handoff must be marked void, got {result.error_message!r}"
    )
    assert void_kind(result.error_message) == "ungateable"
