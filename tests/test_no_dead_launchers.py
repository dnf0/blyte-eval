"""No launch script asks for an evaluation arm that no longer exists (eval #46, #47, #49).

Each such script failed with "Unknown evaluation arm" on its first run. The experiments are
recorded in EXPERIMENTS.md, FINDINGS.md and results/, and the scripts in git history."""

import os
import re
import subprocess
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"

# A removed arm name as a whole word: the MCP, agent-MCP, daemon, relay and state-engine arms.
REMOVED_ARM = re.compile(
    r"(?<![\w\[-])("
    r"superstate_mcp\w*|superstate_agent_mcp\w*|agent_mcp\w*|"
    r"superstate_daemon\w*|daemon_(review|sliced|rollback|full|stall|regression|cache|nocache)|"
    r"superstate_relay|superstate_python|superstate_rust\w*|superstate_solo"
    r")(?![\w\]])"
)


def test_no_launch_script_asks_for_a_removed_arm() -> None:
    offenders = {
        p.name: sorted({m.group(1) for m in REMOVED_ARM.finditer(p.read_text())})
        for p in SCRIPTS.glob("*.sh")
        if REMOVED_ARM.search(p.read_text())
    }
    assert offenders == {}


def test_the_canary_compares_harnesses() -> None:
    script = SCRIPTS / "run_canary.sh"
    assert script.is_file() and os.access(script, os.X_OK)
    text = script.read_text()
    assert "--harnesses" in text
    assert "--canary" in text
    assert "--arms" not in text
    assert "--driver" not in text, "--harnesses refuses to combine with --driver"
    assert re.search(r"\bagy\b", text) and "blyte[" in text
    subprocess.run(["bash", "-n", str(script)], check=True)


def test_the_analysis_scripts_are_kept() -> None:
    for name in ("effect.py", "analyse_exp080.py", "eval_routing_split.py",
                 "merge_frontier_results.py", "paired_run.py", "pilot_run.py"):
        assert (SCRIPTS / name).is_file(), name
