"""Deleting code must not leave a name behind that only fails at runtime.

Three defects on 2026-09-21 came from one refactor, and the most expensive was this class:
`BRIDGE_PREFIX_RE` was removed with the gate-derivation block, nothing referenced it until the
confirmation gate at the very end of a 40-minute run, and EXP-074 recorded Passed=False with
zero telemetry for two tasks that had in fact completed their milestones. Ruff's F821 finds it
in under a second.

F821 undefined name, F811 redefinition, F401 unused import -- the three signatures a deletion
leaves behind.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
TARGETS = ("lab", "scripts", "tests")


def test_no_undefined_or_orphaned_names() -> None:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "--select", "F821,F811,F401", *TARGETS],
            cwd=ROOT, capture_output=True, text=True, timeout=120,
        )
    except FileNotFoundError:  # pragma: no cover
        pytest.skip("ruff is not available in this environment")
    if "No module named" in (proc.stderr or ""):  # pragma: no cover
        pytest.skip("ruff is not installed in this interpreter")
    assert proc.returncode == 0, (
        "a deletion left a name that only fails at runtime:\n"
        f"{proc.stdout}{proc.stderr}"
    )
