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


def test_guard_bench_provisions_hooks_for_every_config() -> None:
    """The offline harness must provision hooks the same way the daemon does.

    A guard is only evaluatable offline if the offline arm is wired identically to the live
    one -- absolute binary path included, since a bare name resolves through PATH at hook time
    and made EXP-077 measure the previous day's build.
    """
    import importlib.util
    import json as _json
    import tempfile

    spec = importlib.util.spec_from_file_location(
        "guard_bench", ROOT / "scripts" / "guard_bench.py"
    )
    assert spec and spec.loader
    bench = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bench)

    assert {"none", "file", "command", "full"} <= set(bench.CONFIGS)

    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        for config, expected_groups in [("none", 0), ("file", 1), ("command", 1), ("full", 2)]:
            bench.write_hooks(ws, config, Path("/abs/path/superstate"))
            hooks = _json.loads((ws / ".agents" / "hooks.json").read_text())
            assert len(hooks) == expected_groups, config
            for group in hooks.values():
                command = group["PreToolUse"][0]["hooks"][0]["command"]
                assert command.startswith("/"), f"{config}: hook must use an absolute path"

        # Denials are what the harness measures; the accounting must be exact.
        (ws / ".agent-state").mkdir(exist_ok=True)
        (ws / ".agent-state" / "guard-denials.jsonl").write_text(
            '{"ts":1,"path":"a.go","lines":400}\n{"ts":2,"path":"b.go","lines":250}\n'
        )
        assert bench.denials(ws) == (2, 650)


def test_guard_ceiling_reports_a_bound_without_calling_a_model() -> None:
    """The ceiling is arithmetic, so it must be instant and deterministic.

    Portal's ~90% is an artefact comparison -- file tokens versus summary tokens -- not a
    behavioural A/B, and the like-for-like version costs no model call at all. Measured on
    superstate-core: 96.3% ceiling against a -4.2% behavioural result, the gap being what the
    agent reads back in ranges.
    """
    binary = _binary()
    if binary is None:
        pytest.skip("no superstate binary available")
    repo = Path("/Users/danielfisher/repos/superstate/crates/superstate-core/src")
    if not repo.is_dir():
        pytest.skip("superstate source not available")

    proc = subprocess.run(
        [
            "python3", str(ROOT / "scripts" / "guard_ceiling.py"),
            "--repo", str(repo), "--binary", str(binary),
        ],
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    assert "CEILING SAVING" in proc.stdout, proc.stdout
    # A guard that cannot beat reading the file whole is not worth having.
    pct = float(proc.stdout.split("CEILING SAVING:")[1].split("%")[0].strip())
    assert pct > 50, f"outline is not materially smaller than the file: {pct}%"
