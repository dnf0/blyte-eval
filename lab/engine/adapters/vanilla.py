"""Arm A: Vanilla (Control) Adapter.

Runs unguided SWE-bench baseline execution with NO markdown rules,
NO skills, and NO agent-rules or blyte steering.
"""

from __future__ import annotations

import logging
from pathlib import Path

from lab.engine.adapters.base import TurnBasedAdapter, strip_preexisting_guidance

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
        strip_preexisting_guidance(workspace_path)

    def prepare_workspace(self, workspace_path: Path) -> None:
        """Ensure pristine unguided workspace before execution."""
        self.clean_workspace(workspace_path)
