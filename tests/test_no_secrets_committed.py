"""No secret file may become trackable by git.

This exists because .env landed in both repos while `git add -A` was in routine use by an
agent. It was never committed -- checked at the time -- but nothing except that check stood
between the key and history, and the check was manual.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

SECRET_FILES = [".env", ".env.local", ".env.production", "secrets.env"]


@pytest.mark.parametrize("name", SECRET_FILES)
def test_secret_file_is_gitignored(name: str):
    """Ignored whether or not it exists right now -- the next one to appear is covered too."""
    r = subprocess.run(
        ["git", "check-ignore", "-q", name], cwd=REPO, capture_output=True
    )
    assert r.returncode == 0, (
        f"{name} is NOT gitignored. A single `git add -A` would commit it. "
        f"Add it to .gitignore before doing anything else."
    )


def test_no_secret_file_is_tracked():
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True
    ).stdout.split()
    leaked = [f for f in tracked if Path(f).name in SECRET_FILES or f.endswith(".pem")]
    assert not leaked, f"secret files are tracked by git: {leaked}"


def test_no_api_key_shaped_string_is_tracked():
    """Catches a key pasted into a tracked file, which gitignore cannot prevent."""
    r = subprocess.run(
        ["git", "grep", "-lE", r"AIza[0-9A-Za-z_-]{30,}|sk-ant-[0-9A-Za-z_-]{20,}", "--", "."],
        cwd=REPO, capture_output=True, text=True,
    )
    assert r.returncode != 0 or not r.stdout.strip(), (
        f"an API-key-shaped string appears in tracked files:\n{r.stdout}"
    )
