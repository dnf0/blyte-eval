"""Unit tests for the Canary 3 task set and runner configuration."""

from __future__ import annotations

import os
from pathlib import Path

from lab.benchmarks.gate_fixtures import is_unmeasurable
from lab.benchmarks.task_sets import (
    CANARY_TASKS,
    DISCRIMINATING_TASKS,
    is_canary,
    is_discriminating,
)


def test_canary_tasks_definition() -> None:
    """Canary set must contain exactly the 3 designated fast discriminating tasks."""
    expected = (
        "build-cython-ext",
        "chess-best-move",
        "httpx-multipart-response-parsing",
    )
    assert CANARY_TASKS == expected
    assert len(CANARY_TASKS) == 3


def test_is_canary() -> None:
    """is_canary must identify canary tasks and reject others."""
    for task_name in CANARY_TASKS:
        assert is_canary(task_name) is True

    assert is_canary("scc-bounded-memory-spilling") is False
    assert is_canary("openssl-selfsigned-cert") is False
    assert is_canary("nonexistent-task") is False


def test_canary_tasks_are_discriminating() -> None:
    """Every canary task must belong to DISCRIMINATING_TASKS to provide valid signal."""
    for task_name in CANARY_TASKS:
        assert task_name in DISCRIMINATING_TASKS, f"{task_name} is not in DISCRIMINATING_TASKS"
        assert is_discriminating(task_name) is True


def test_canary_tasks_are_measurable() -> None:
    """Canary tasks must have held-out verifiers and not be unmeasurable."""
    for task_name in CANARY_TASKS:
        assert not is_unmeasurable(task_name), f"{task_name} is marked unmeasurable"


def test_run_canary_script_exists_and_executable() -> None:
    """The turnkey scripts/run_canary.sh script must exist and have execute permissions."""
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "run_canary.sh"
    assert script_path.is_file(), f"Expected {script_path} to exist"
    assert os.access(script_path, os.X_OK), f"Expected {script_path} to be executable"


def test_paired_run_canary_flag() -> None:
    """paired_run.py must accept the --canary flag."""
    from scripts.paired_run import build_parser

    parser = build_parser()
    args = parser.parse_args(["--canary"])
    assert args.canary is True

