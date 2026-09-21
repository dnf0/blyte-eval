"""The perimeter guards must be verified before a benchmark run, not by one.

Four runs on 2026-09-21 were spent discovering wiring bugs rather than measuring anything:
a binary swapped mid-run, a NameError at the confirmation gate, a guard whose denial text
ended the worker's turn, and hooks invoking the previous day's binary because the command was
a bare name resolved through PATH. None needed a task corpus, a sealed grader or a scoring
pass -- each is visible in a prepared workspace in about two seconds.

`scripts/guard_smoke.sh` asserts the whole perimeter contract: whole-file reads denied through
both the viewing tool and the shell, bounded reads allowed, non-reads untouched, repeat polls
throttled rather than refused, and every denial recorded so the mechanism stays countable.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parent.parent
SMOKE = ROOT / "scripts" / "guard_smoke.sh"
DEFAULT_BIN = Path("/Users/danielfisher/repos/superstate/target/release/superstate")


def _binary() -> Path | None:
    env = os.environ.get("SUPERSTATE_BIN")
    candidate = Path(env) if env else DEFAULT_BIN
    return candidate if candidate.is_file() and os.access(candidate, os.X_OK) else None


def test_perimeter_guards_fire() -> None:
    binary = _binary()
    if binary is None:
        pytest.skip("no superstate binary available; build it or set SUPERSTATE_BIN")

    proc = subprocess.run(
        [str(SMOKE), str(binary)], capture_output=True, text=True, timeout=180
    )
    assert proc.returncode == 0, (
        "the perimeter is broken -- do not start a benchmark run:\n"
        f"{proc.stdout}{proc.stderr}"
    )
    assert "PERIMETER OK" in proc.stdout, proc.stdout


def test_generated_hooks_never_resolve_the_binary_through_path() -> None:
    """A bare `superstate` in a hook runs whatever is installed, not the build under test.

    EXP-077 ran the current build as the daemon and the previous day's build as its guards,
    so every fix it was registered to measure was absent from the process enforcing them.
    """
    daemon_rs = Path(
        os.environ.get("SUPERSTATE_SRC", "/Users/danielfisher/repos/superstate")
    ) / "crates/superstate-core/src/daemon.rs"
    if not daemon_rs.is_file():
        pytest.skip("superstate source not available")

    text = daemon_rs.read_text(encoding="utf-8")
    assert '"superstate guard' not in text, (
        "daemon.rs writes a hook command as a bare name; it must embed current_exe()"
    )
    assert "hook_binary()" in text, "daemon.rs no longer resolves the hook binary explicitly"
