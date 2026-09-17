"""A worker must be sized from what the tasks declare, not from a constant."""

from __future__ import annotations

from pathlib import Path

import pytest

from lab.benchmarks.task_loader import load_benchmark_tasks
from lab.engine.governor import ConcurrencyGovernor

TASKS_ROOT = Path.home() / ".cache/agent-rules/frontier-eval/tasks"


def test_tasks_declare_their_memory_requirement() -> None:
    """Sizing depends on memory_mb being present; without it the fix silently reverts."""
    if not TASKS_ROOT.is_dir():
        pytest.skip("benchmark corpus not present")
    tasks = load_benchmark_tasks(TASKS_ROOT)
    undeclared = [t.name for t in tasks if not getattr(t, "memory_mb", None)]
    assert not undeclared, f"tasks declare no memory_mb, so a worker cannot be sized: {undeclared}"


def test_heavier_tasks_lower_the_concurrency_ceiling() -> None:
    """The flat 1.5 GB assumption advertised a ceiling the machine could not honour.

    datacurve containers are capped at 8 GB each. Run at the flat-assumption ceiling, workers
    wait for a governor slot, give up at 300s, and are recorded as TASK failures -- EXP-053
    lost 12 of 54 runs that way, and the failures are indistinguishable from real ones in the
    results JSON unless you read the reason string.
    """
    flat = ConcurrencyGovernor(
        cpus_per_worker=1.0, ram_gb_per_worker=1.5, ram_headroom_gb=4.0
    ).calculate_max_concurrency()
    heavy = ConcurrencyGovernor(
        cpus_per_worker=1.0, ram_gb_per_worker=8.0, ram_headroom_gb=4.0
    ).calculate_max_concurrency()
    assert heavy < flat, (
        f"an 8 GB worker must yield a lower ceiling than a 1.5 GB one ({heavy} vs {flat})"
    )


def test_paired_run_refuses_to_oversubscribe() -> None:
    """Over-subscription must fail loudly, not silently record starved workers as failures."""
    source = (Path(__file__).resolve().parents[1] / "scripts/paired_run.py").read_text()
    assert "t.memory_mb / 1024" in source, "worker size must come from the tasks"
    assert "exceeds the governor's ceiling" in source, "over-subscription must be refused"
