"""Tests for Universal Progress Tracker across evaluation arms."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import pytest

from lab.engine.budget_policy import BudgetPolicy
from lab.engine.progress_tracker import ProgressTracker


def test_progress_tracker_detects_git_commit_for_vanilla_or_superpowers(tmp_path: Path) -> None:
    # Setup mock git repo
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.local"], cwd=repo_dir, check=True)
    
    # Initial commit
    file1 = repo_dir / "README.md"
    file1.write_text("initial", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_dir, check=True, capture_output=True)
    base_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir, check=True, capture_output=True, text=True).stdout.strip()

    policy = BudgetPolicy(base_timeout_sec=900, lease_extension_sec=1200)
    tracker = ProgressTracker(policy=policy, workspace_path=repo_dir, arm="vanilla", last_commit=base_commit)

    # No new commit yet -> no progress
    advanced, reason = tracker.poll_for_progress()
    assert not advanced
    assert policy.extensions_granted_count == 0

    # Agent makes a commit
    code_file = repo_dir / "solution.py"
    code_file.write_text("def solve(): pass", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "feat: add solution skeleton"], cwd=repo_dir, check=True, capture_output=True)

    # Poll again -> progress detected and lease extended!
    advanced, reason = tracker.poll_for_progress()
    assert advanced
    assert "New git commit" in reason
    assert policy.extensions_granted_count == 1
    assert policy.milestones_completed == 1


def test_progress_tracker_detects_superstate_milestone_advance(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    state_dir = repo_dir / ".agent-state"
    state_dir.mkdir()
    state_file = state_dir / "state.json"

    # Initial state with 0 completed tasks
    state_file.write_text(json.dumps({
        "plan_id": "test-plan",
        "active_task": "Task 1",
        "completed_tasks": [],
    }), encoding="utf-8")

    policy = BudgetPolicy(base_timeout_sec=900, lease_extension_sec=1200)
    tracker = ProgressTracker(policy=policy, workspace_path=repo_dir, arm="superstate")

    # Initial check -> no extension
    advanced, reason = tracker.poll_for_progress()
    assert not advanced
    assert policy.extensions_granted_count == 0

    # Superstate state engine advances Task 1 to completed
    state_file.write_text(json.dumps({
        "plan_id": "test-plan",
        "active_task": "Task 2",
        "completed_tasks": ["Task 1"],
    }), encoding="utf-8")

    # Poll again -> milestone detected and lease extended!
    advanced, reason = tracker.poll_for_progress()
    assert advanced
    assert "Superstate milestone" in reason
    assert policy.extensions_granted_count == 1
    assert policy.milestones_completed == 1
