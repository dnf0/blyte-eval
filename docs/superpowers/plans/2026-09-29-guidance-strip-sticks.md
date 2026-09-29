# Keep Stripped Guidance Stripped — Plan

> **For agentic workers:** Execution is delegated to headless `blyte` (with a sampled A/B against `agy`), one task per dispatch; Claude reviews each task before the next is sent. Steps use checkbox (`- [ ]`) syntax for tracking. Do NOT `git push` or open PRs; commit locally only. Do NOT start any benchmark or paid run, or call any model API. Do not edit `FINDINGS.md`, `EXPERIMENTS.md`, `CLAUDE.md`/`AGENTS.md`, `results/`, `traces/` or `data/`.

**Why (2026-09-29):** every arm strips the guidance files a task repository ships (`AGENTS.md`,
`CLAUDE.md`, ...) so all arms start from the same files. The strip only deletes the files from the
working tree. They are still tracked, so an agent can bring them back with `git checkout -- AGENTS.md`,
and in offload v2 (2026-09-28) Sonnet did exactly that in some runs and not others. The deletion also
lands in the graded patch whenever the file stays deleted (`git add -A` stages it), so the patch
differs by whether the agent restored it. Marking the stripped, tracked paths `skip-worktree` fixes
both: git then treats them as unchanged (no deletion in the patch, `git status` clean) and refuses
`git checkout`/`git restore` of them ("pathspec did not match"; checked with git 2.50).

## Global Constraints

- Base branch `feat/guidance-strip`. Work only in your own worktree.
- Existing tests pass unchanged.
- Checks: `make lint && make test`.
- Commit with `--no-gpg-sign` and the exact message below.

### Task 1: mark stripped guidance skip-worktree

**Files:**
- Modify: `lab/engine/adapters/base.py`
- Modify: `lab/engine/adapters/vanilla.py`
- Create: `tests/test_guidance_strip_sticks.py`

- [ ] **Step 1: add the helper to `lab/engine/adapters/base.py`.** Add `import subprocess` to the
  imports (after `import shutil`). Add this function directly above `def strip_preexisting_guidance`:

```python
def _hide_from_git(workspace_path: Path, removed: list[str]) -> None:
    """Keep stripped guidance stripped. Marks the tracked copies skip-worktree, so the deletion
    is not part of the agent's diff and `git checkout -- AGENTS.md` cannot bring the file back
    (offload v2, 2026-09-28: Sonnet restored AGENTS.md with git checkout in some runs)."""
    if not removed or not (workspace_path / ".git").exists():
        return
    try:
        listed = subprocess.run(
            ["git", "-C", str(workspace_path), "ls-files", "-z", "--", *removed],
            capture_output=True,
            check=True,
        ).stdout.split(b"\0")
        tracked = [p.decode() for p in listed if p]
        if tracked:
            subprocess.run(
                ["git", "-C", str(workspace_path), "update-index", "--skip-worktree", "--", *tracked],
                capture_output=True,
                check=True,
            )
    except (OSError, subprocess.CalledProcessError) as err:
        logger.warning("Could not hide stripped guidance from git in %s: %s", workspace_path, err)
```

  In `strip_preexisting_guidance`, replace its final `return removed` with:

```python
    _hide_from_git(workspace_path, removed)
    return removed
```

- [ ] **Step 2: make the vanilla arm use the shared strip.** In `lab/engine/adapters/vanilla.py`,
  replace the whole body of `clean_workspace` (keep its signature and docstring) with:

```python
        strip_preexisting_guidance(workspace_path)
```

  change the import line to `from lab.engine.adapters.base import TurnBasedAdapter, strip_preexisting_guidance`,
  and remove `import shutil` if nothing else in the file uses it.

- [ ] **Step 3: create `tests/test_guidance_strip_sticks.py`:**

```python
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
```

  Run: `.venv/bin/python -m pytest tests/test_guidance_strip_sticks.py -q`
  Expected: 3 passed (it fails before Steps 1–2: `git status` shows the deletion).

- [ ] **Step 4: run the checks and commit.**

  Run: `make lint && make test`. Expected: both pass.

```bash
git add lab/engine/adapters/base.py lab/engine/adapters/vanilla.py tests/test_guidance_strip_sticks.py
git commit --no-gpg-sign -m "fix(eval): stripped guidance stays stripped (skip-worktree), out of the diff and not restorable"
```
