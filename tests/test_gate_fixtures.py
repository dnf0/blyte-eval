"""The gate module after the fixture ban: what must stay gone, and what must remain.

Manifesto Invariant V bans hand-authored gate fixtures, because pre-seeding a reproduction
test leaks the function names, argument shapes and assertion values and turns an open-ended
diagnosis into a narrow test-passing game. These tests stop the table growing back, and pin
the two things in this module that were never part of the ban: sealed-grader detection, and
the record of tasks that cannot be scored at all.
"""

from __future__ import annotations

from pathlib import Path

import lab.benchmarks.gate_fixtures as gate_module
from lab.benchmarks.gate_fixtures import references_sealed_grader

ADAPTERS = Path(__file__).resolve().parent.parent / "lab" / "engine" / "adapters"


def test_the_fixture_table_is_gone_and_stays_gone() -> None:
    """Manifesto Invariant V: no hand-authored gate may live in the harness."""
    assert not hasattr(gate_module, "GATE_FIXTURES"), (
        "GATE_FIXTURES was removed on 2026-09-21. A verification command may come only from "
        "the repository's own runner or from the autonomous TDD DAG the engine derives; see "
        "the module docstring and docs/EVALUATION-PHILOSOPHY.md Invariant 2."
    )
    assert not hasattr(gate_module, "agent_gate_for")


def test_no_adapter_consults_a_fixture_table() -> None:
    """An adapter that looks up a per-task gate has reintroduced the ban."""
    offenders = [
        path.name
        for path in ADAPTERS.glob("*.py")
        if "agent_gate_for" in path.read_text(encoding="utf-8")
    ]
    assert not offenders, (
        f"adapters consult a hand-authored gate table: {offenders}. The referee translates; "
        f"it does not author verification commands."
    )


def test_the_daemon_hands_off_under_tdd_when_no_native_runner_exists() -> None:
    """The replacement path must actually be wired, or tasks silently run ungated."""
    from lab.engine.adapters.superstate_daemon import TDD_MODE

    src = (ADAPTERS / "superstate_daemon.py").read_text(encoding="utf-8")
    assert "return TDD_MODE, None" in src, "no TDD fallback in _derive_gate"
    assert '"--tdd"' in src, "the handoff never passes --tdd to the engine"
    assert TDD_MODE not in ("", "true"), "the sentinel must not be executable as a command"


def test_references_sealed_grader_distinguishes_in_repo_tests() -> None:
    """The sealed grader is at /tests/, whereas /app/<pkg>/tests/ is an in-repo suite."""
    assert references_sealed_grader("python -m pytest /tests/test_patch.py") is True
    assert references_sealed_grader("bash /tests/run.sh") is True
    assert references_sealed_grader("pytest /tests/") is True

    # In-repo suites must NOT be treated as sealed graders
    assert references_sealed_grader("python -m pytest /app/pyknotid/tests") is False
    assert references_sealed_grader("cd /app/repo && pytest tests/") is False
    assert references_sealed_grader("pytest ./tests/test_foo.py") is False


def test_unmeasurable_tasks_are_documented_with_a_reason() -> None:
    """A task whose grader cannot run scores every arm zero and shrinks the denominator.

    sqlite-db-truncate ships no tests/ dir, so the loader falls back to `pytest tests/`
    and the image has no pytest -- exit 127 for vanilla, solo and daemon alike. Recording
    it stops it silently creeping back into a run.
    """
    from lab.benchmarks.gate_fixtures import UNMEASURABLE_TASKS, is_unmeasurable

    assert UNMEASURABLE_TASKS, "expected at least the known-broken task to be recorded"
    for name, reason in UNMEASURABLE_TASKS.items():
        assert reason.strip(), f"{name} excluded without a stated reason"
        assert is_unmeasurable(name) == reason
    assert is_unmeasurable("db-wal-recovery") is None


def test_tasks_without_a_sealed_grader_are_marked_unmeasurable() -> None:
    """A task with no held-out tests/ cannot be scored, so it must be listed.

    The harness falls back to `pytest tests/` run in the agent's own container, which
    grades the agent against tests it wrote. That inflated superstate_mcp by 7 discordant
    pairs against vanilla before it was caught.
    """
    from pathlib import Path

    from lab.benchmarks.gate_fixtures import is_unmeasurable
    from lab.benchmarks.task_loader import load_benchmark_tasks

    root = Path.home() / ".cache/agent-rules/frontier-eval/tasks"
    if not root.is_dir():
        import pytest as _pytest

        _pytest.skip("benchmark corpus not present")

    ungradeable = [t.name for t in load_benchmark_tasks(root) if t.tests_dir is None]
    unlisted = [name for name in ungradeable if not is_unmeasurable(name)]
    assert not unlisted, (
        f"tasks ship no held-out grader but are not listed in UNMEASURABLE_TASKS: {unlisted}"
    )
