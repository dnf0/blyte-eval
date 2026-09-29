"""Stripped guidance stays stripped: not in the agent's diff, and not restorable by git checkout."""

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from lab.engine.adapters.base import strip_preexisting_guidance
from lab.engine.adapters.vanilla import VanillaAdapter


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "AGENTS.md").write_text("project rules\n")
    (tmp_path / ".agents" / "skills").mkdir(parents=True)
    (tmp_path / ".agents" / "skills" / "s.md").write_text("skill\n")
    (tmp_path / "a.py").write_text("x = 1\n")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base")
    return tmp_path


@pytest.mark.parametrize("strip", [strip_preexisting_guidance, VanillaAdapter().clean_workspace])
def test_stripped_guidance_stays_out_of_the_diff_and_cannot_be_checked_out(repo: Path, strip) -> None:
    strip(repo)

    assert not (repo / "AGENTS.md").exists()
    assert _git(repo, "status", "--porcelain").stdout == ""

    _git(repo, "checkout", "--", "AGENTS.md")
    _git(repo, "restore", "--", ".agents/skills/s.md")
    assert not (repo / "AGENTS.md").exists()
    assert not (repo / ".agents" / "skills" / "s.md").exists()

    (repo / "a.py").write_text("x = 2\n")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "work")
    changed = _git(repo, "show", "--name-only", "--format=", "HEAD").stdout.split()
    assert changed == ["a.py"]


def test_a_workspace_without_git_is_still_stripped(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("rules\n")
    assert strip_preexisting_guidance(tmp_path) == ["AGENTS.md"]
    assert not (tmp_path / "AGENTS.md").exists()
