# Remove the Dead Launch Scripts — Implementation Plan

> **For agentic workers:** Implement exactly one task. Do NOT `git push`, open PRs, start any benchmark or paid run, or call any model API; commit locally only. Do NOT execute any of the launch scripts. This plan is shadow-run: agy and blyte each implement it independently.

**Goal:** Delete every `scripts/*.sh` launcher that can only run evaluation arms which no longer exist, and turn `scripts/run_canary.sh` into a harness-mode canary (agy against blyte), so that nothing left in `scripts/` asks for a removed arm.

**Why:** eval #46, #47 and #49 removed the MCP, agent-MCP, daemon, relay and state-engine arms. About 34 launch scripts still pass those arm names to `paired_run.py`, so each one now fails with "Unknown evaluation arm" the moment it is run. The experiments they launched are recorded in `EXPERIMENTS.md`, `FINDINGS.md` and `results/`, and the scripts stay in git history.

**Tech Stack:** bash, Python 3, pytest, ruff, pyright, `uv`.

## Global Constraints

- Work only in your own worktree (already on its own branch). Run `uv sync` first.
- Do NOT edit `FINDINGS.md`, `EXPERIMENTS.md`, `CLAUDE.md`/`AGENTS.md` or anything under `results/`.
- **Keep the Python analysis scripts** (`scripts/effect.py`, `scripts/analyse_exp080.py`, `scripts/eval_routing_split.py`, `scripts/merge_frontier_results.py` and any other `scripts/*.py`). They read historical results files, where the old arm names are data, so they still work.
- **Keep every `.sh` script that does not ask for a removed arm** (for example `guard_smoke.sh`, `read_budget_sweep.sh`, `pin_superstate_binary.sh`). A script is dead only if it passes a removed arm to `paired_run.py`/`pilot_run.py` (via `--arms`, an `ARMS=` list or similar); read each one before deleting it.
- The removed arm families are: `superstate_mcp*`, `superstate_agent_mcp*`/`agent_mcp*`, `superstate_daemon*`/`daemon_*`, `superstate_relay`, and the state-engine arms `superstate`, `superstate_python`, `superstate_rust*`, `superstate_solo`. `vanilla` and `superpowers` still exist; harness mode (`--harnesses agy blyte[...]`) is the current way to compare harnesses.
- Commit with `--no-gpg-sign` and the exact message below.

---

### Task 1: Remove the dead launchers

- [ ] **Step 1: Write the acceptance test.** Create `tests/test_no_dead_launchers.py`:

```python
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
```

- [ ] **Step 2: Run to confirm it fails.** Run: `uv run pytest -q tests/test_no_dead_launchers.py`. Expected: the first two tests fail (about 34 offending scripts; the canary still asks for daemon and MCP arms); the third passes.

- [ ] **Step 3: Implement.**
  1. Delete each dead launcher (see Global Constraints for what counts as dead).
  2. Rewrite `scripts/run_canary.sh` to run the same three canary tasks as a harness comparison: by default `--harnesses agy "blyte[folded]"`, with the harness list overridable from the command line the way the arms were. Keep `--canary`, `--model gemini-3.8-flash-high`, `--concurrency 2` and the timestamped `--out results/canary_<stamp>.json`. Drop `--driver` (harness mode refuses it). Update its echo lines to match.
  3. If anything else refers to a deleted script by path (a test, the Makefile, a live `.py`), update or remove that reference; ignore mentions in the historical documents listed in Global Constraints.

- [ ] **Step 4: Verify.** Run `uv run pytest -q tests/test_no_dead_launchers.py tests/test_canary_task_set.py` (all pass), then `make lint`.

- [ ] **Step 5: Commit.**

```bash
git add -A scripts tests
git commit --no-gpg-sign -m "chore(eval): remove launch scripts for arms that no longer exist; the canary compares harnesses"
```
