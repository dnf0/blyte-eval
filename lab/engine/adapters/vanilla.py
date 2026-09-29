"""Arm A: Vanilla (Control) Adapter.

Runs unguided SWE-bench baseline execution with NO markdown rules,
NO skills, and NO agent-rules or blyte steering.
"""

from __future__ import annotations

import logging
from pathlib import Path
import shutil

from lab.engine.adapters.base import TurnBasedAdapter

logger = logging.getLogger("blyte_eval.adapters.vanilla")


class VanillaAdapter(TurnBasedAdapter):
    """Unguided baseline adapter enforcing complete isolation from rules or skills."""

    def __init__(self, max_turns: int = 50, max_stream_retries: int = 5) -> None:
        super().__init__(max_turns=max_turns, max_stream_retries=max_stream_retries)

    @property
    def name(self) -> str:
        return "vanilla"

    def clean_workspace(self, workspace_path: Path) -> None:
        """Sanitize workspace by removing all guidance, rule files, and skills."""
        rule_files = [
            workspace_path / "AGENTS.md",
            workspace_path / "GEMINI.md",
            workspace_path / "CLAUDE.md",
            workspace_path / ".cursorrules",
            workspace_path / ".windsurfrules",
        ]
        for rf in rule_files:
            if rf.is_file():
                try:
                    rf.unlink()
                except OSError as err:
                    logger.warning("Failed to remove rule file %s: %s", rf, err)

        skills_dir = workspace_path / ".agents" / "skills"
        if skills_dir.is_dir():
            try:
                shutil.rmtree(skills_dir)
            except OSError as err:
                logger.warning("Failed to remove skills dir %s: %s", skills_dir, err)

    def prepare_workspace(self, workspace_path: Path) -> None:
        """Ensure pristine unguided workspace before execution."""
        self.clean_workspace(workspace_path)
