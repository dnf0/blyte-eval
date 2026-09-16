"""The core set must account for every task, and never include an ungradeable one."""

from __future__ import annotations

from pathlib import Path

import pytest

from lab.benchmarks.gate_fixtures import UNMEASURABLE_TASKS, is_unmeasurable
from lab.benchmarks.task_loader import load_benchmark_tasks
from lab.benchmarks.task_sets import (
    DISCRIMINATING_TASKS,
    EXCLUDED_TASKS,
    excluded_reason,
    is_discriminating,
)

TASKS_ROOT = Path.home() / ".cache/agent-rules/frontier-eval/tasks"


def test_no_discriminating_task_is_ungradeable() -> None:
    """A task with no held-out grader cannot contribute signal, only self-grading.

    Across 55 paired runs the ungradeable tasks went vanilla 0/7, superstate_mcp 7/7,
    supplying 7 of the 18 discordant pairs behind the headline lift.
    """
    leaked = [name for name in DISCRIMINATING_TASKS if is_unmeasurable(name)]
    assert not leaked, f"ungradeable tasks in the core set: {leaked}"


def test_every_task_is_accounted_for() -> None:
    """A task is in the core set, excluded with a reason, or ungradeable -- never lost."""
    if not TASKS_ROOT.is_dir():
        pytest.skip("benchmark corpus not present")

    names = {t.name for t in load_benchmark_tasks(TASKS_ROOT)}
    classified = set(DISCRIMINATING_TASKS) | set(EXCLUDED_TASKS) | set(UNMEASURABLE_TASKS)
    unclassified = names - classified
    assert not unclassified, (
        "tasks belong to no category; classify them in task_sets.py or "
        f"UNMEASURABLE_TASKS: {sorted(unclassified)}"
    )


def test_the_three_categories_do_not_overlap() -> None:
    assert not (set(DISCRIMINATING_TASKS) & set(EXCLUDED_TASKS))
    assert not (set(DISCRIMINATING_TASKS) & set(UNMEASURABLE_TASKS))


def test_every_exclusion_states_a_reason() -> None:
    for name in EXCLUDED_TASKS:
        reason = excluded_reason(name)
        assert reason and ("ceiling" in reason or "floor" in reason), (
            f"{name} is excluded without saying whether it is a ceiling or a floor"
        )
        assert not is_discriminating(name)
