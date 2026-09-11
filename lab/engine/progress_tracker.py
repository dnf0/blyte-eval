"""Universal progress tracker for granting runtime lease extensions across evaluation arms."""

from __future__ import annotations

import json
import logging
from pathlib import Path
import subprocess

from lab.engine.budget_policy import BudgetPolicy

logger = logging.getLogger("superstate_eval.progress_tracker")


class ProgressTracker:
    """Monitors workspace state and awards progress-earned lease extensions to any arm."""

    def __init__(
        self,
        policy: BudgetPolicy,
        workspace_path: Path | str,
        arm: str,
        last_commit: str | None = None,
    ) -> None:
        self.policy = policy
        self.workspace_path = Path(workspace_path)
        self.arm = arm.lower()
        self.last_commit = last_commit or self._get_current_head_commit()
        self.completed_tasks_count = self._get_superstate_completed_count()

    def _get_current_head_commit(self) -> str | None:
        """Query current HEAD commit hash from workspace git repository."""
        git_dir = self.workspace_path / ".git"
        if not git_dir.exists():
            return None
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception as err:
            logger.debug(f"Failed to query git HEAD: {err}")
        return None

    def _get_superstate_completed_count(self) -> int:
        """Parse completed task count from .agent-state/state.json if present."""
        state_file = self.workspace_path / ".agent-state" / "state.json"
        if not state_file.is_file():
            return 0
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
            completed = data.get("completed_tasks", [])
            if isinstance(completed, list):
                return len(completed)
        except Exception as err:
            logger.debug(f"Failed to parse superstate state file: {err}")
        return 0

    def poll_for_progress(self) -> tuple[bool, str]:
        """Check for forward progress signals and trigger lease extension on advancement."""
        # 1. Superstate explicit milestone progression check
        if "superstate" in self.arm:
            count = self._get_superstate_completed_count()
            if count > self.completed_tasks_count:
                delta = count - self.completed_tasks_count
                self.completed_tasks_count = count
                for i in range(delta):
                    title = f"Superstate task completion #{count - delta + i + 1}"
                    self.policy.record_milestone_progress(milestone_title=title)
                reason = f"Superstate milestone completed (count={count})"
                logger.info(f"[{self.arm.upper()}] {reason}. Lease extended.")
                return True, reason

        # 2. Universal Git commit progress check (for Vanilla, Superpowers, and Superstate fallback)
        current_commit = self._get_current_head_commit()
        if current_commit and current_commit != self.last_commit:
            old_commit = self.last_commit
            self.last_commit = current_commit
            title = f"Git commit: {current_commit[:8]}"
            self.policy.record_milestone_progress(milestone_title=title)
            reason = f"New git commit detected: {current_commit[:8]} (prev={old_commit[:8] if old_commit else 'None'})"
            logger.info(f"[{self.arm.upper()}] {reason}. Lease extended.")
            return True, reason

        return False, "No new progress signals detected"
