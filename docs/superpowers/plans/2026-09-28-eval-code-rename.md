# Rename the Eval Code to blyte — Plan

> **For agentic workers:** Implement exactly one task. Do NOT `git push`, open PRs, start any benchmark or paid run, or call any model API; commit locally only. Do not edit `FINDINGS.md`, `EXPERIMENTS.md`, `CLAUDE.md`/`AGENTS.md`, `results/`, `traces/` or `data/`. This plan is shadow-run: agy and blyte each implement it independently.

**Why (2026-09-28):** the harness repository is now `climate-x-org/blyte` and this one
`dnfcx/blyte-eval` (both renamed, private); the checkouts are `~/repos/blyte` and
`~/repos/blyte-eval` (the old paths are temporary symlinks). The code here still says
`superstate` in about 479 places across 74 files. This is phase 2, step 2 of blyte's
`docs/superpowers/plans/2026-09-27-rename-repos-to-blyte.md`.

## Global Constraints

- Work only in your own worktree. Existing tests pass; a test may change **only** where it names
  something this task renames (a module path, a class, an env var, a logger name), and the change
  is that rename and nothing else.
- Checks: `make lint && make test`.
- Commit with `--no-gpg-sign` and the exact message below.

### Task 1: rename `superstate` to `blyte` in the eval code

**In scope:** `lab/`, `tests/`, `scripts/`, `Makefile`, `pyproject.toml`.

**Rename:**
- the package name in `pyproject.toml`: `superstate-eval` → `blyte-eval`;
- `lab/engine/drivers/superstate_native.py` → `blyte_native.py` (`git mv`), `SuperstateNativeDriver`
  → `BlyteNativeDriver`, and every import of them;
- the binary env var `SUPERSTATE_BIN` → `BLYTE_BIN`, still reading `SUPERSTATE_BIN` when `BLYTE_BIN`
  is unset (a deprecated fallback, with a comment saying so);
- default binary paths `~/repos/superstate/target/{release,debug}/blyte` →
  `~/repos/blyte/target/{release,debug}/blyte`;
- logger names `superstate_eval.*` → `blyte_eval.*`;
- the container env var between the Claude driver and its MCP server,
  `SUPERSTATE_EVAL_CONTAINER` → `BLYTE_EVAL_CONTAINER` (both sides; no fallback needed);
- prose, docstrings and log messages that name the harness or this repository as superstate.

**Keep (do not rename):**
- the `superstate[...]` harness-name alias in `lab/engine/harnesses.py` (old results use it) and
  its test;
- tests whose purpose is to check that the old `superstate_mcp` / `superstate_daemon` /
  `superstate_agent_mcp` arms stay removed (they must keep naming them);
- keys written to or read from result JSON files (renaming one would make old results unreadable);
- dated historical notes (for example "named superstate until 2026-09-24").

**Dead scripts:** a script under `scripts/` that runs the removed `superstate` binary
(`target/release/superstate`) or the removed `superstate-core` crate, and that no test, `Makefile`
target or other script uses, is dead: delete it (`git rm`). Otherwise, rename its references.

**Done when:** `git grep -n -i superstate -- lab tests scripts Makefile pyproject.toml` lists only
the kept cases above, and the full checks pass.

- [ ] Steps: rename, run the checks, confirm the grep, commit:

```bash
git add -A lab tests scripts Makefile pyproject.toml
git commit --no-gpg-sign -m "refactor(eval): rename superstate to blyte in the eval code"
```
