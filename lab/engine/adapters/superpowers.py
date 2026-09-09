"""Arm B: Superpowers Adapter.

Installs standard AGENTS.md rules and vendored .agents/skills into the workspace.
Interprets brainstorming/planning approval gates and dispatches mechanical continuation.
"""

from __future__ import annotations

import logging
from pathlib import Path
import shutil
from typing import Any, Dict

from lab.engine.adapters.base import TurnBasedAdapter, strip_preexisting_guidance

logger = logging.getLogger("superstate_eval.adapters.superpowers")

SUPERPOWERS_AGENTS_MD = """# Engineering Guidance

- Write tests using pytest.
- Target high business-logic coverage, prioritizing edge cases.
- Follow test-driven development: implement reproducing tests first, then minimal fixes.
- Keep commits atomic; each commit should represent one logical change.
- Never commit broken code; verify tests pass locally before declaring task complete.
"""


class SuperpowersAdapter(TurnBasedAdapter):
    """Adapter configuring markdown rules and vendored superpowers skills."""

    def __init__(self) -> None:
        self.skills_installed: bool = False

    @property
    def name(self) -> str:
        return "superpowers"

    def setup_workspace(self, workspace_path: Path) -> None:
        """Install markdown guidance and copy superpowers skills into workspace."""
        # 0. Start from the same blank slate as the other arms. Without this, a repo
        #    that ships its own CLAUDE.md or GEMINI.md would be stripped for Vanilla
        #    and Superstate but kept here -- a difference between arms that is not
        #    the treatment.
        strip_preexisting_guidance(workspace_path)

        # 1. Install AGENTS.md
        agents_md = workspace_path / "AGENTS.md"
        agents_md.write_text(SUPERPOWERS_AGENTS_MD, encoding="utf-8")

        # 2. Copy superpowers skills from candidate paths
        skills_dest = workspace_path / ".agents" / "skills"
        skills_dest.mkdir(parents=True, exist_ok=True)
        self.skills_installed = False

        candidate_paths = [
            Path.home() / ".config/agent-rules-home/.agents/skills",
            Path.home() / "repos/agent-rules/.agents/skills",
            Path.cwd() / ".agents" / "skills",
            Path(__file__).resolve().parent.parent.parent.parent / "agent-rules" / ".agents" / "skills",
        ]

        for src in candidate_paths:
            if src.is_dir() and any(src.iterdir()):
                for item in src.iterdir():
                    dst_item = skills_dest / item.name
                    if item.is_dir():
                        shutil.copytree(item, dst_item, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, dst_item)
                self.skills_installed = True
                logger.info("Installed superpowers skills from %s", src)
                break

        if not self.skills_installed:
            logger.warning(
                "SuperpowersAdapter: Vendored .agents/skills not found in any candidate path. "
                "Superpowers arm is running with empty skills directory."
            )

    def prepare_workspace(self, workspace_path: Path) -> None:
        """Configure workspace with Superpowers guidance before execution begins."""
        self.setup_workspace(workspace_path)

    def get_provenance(self) -> Dict[str, Any]:
        """Record whether the vendored skills library was actually installed."""
        return {"skills_installed": self.skills_installed}
