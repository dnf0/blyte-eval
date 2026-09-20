# Repository-First Software Engineering Benchmarks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Choose an execution mode:
> 1. `superpowers:subagent-driven-development` (recommended for multi-agent reviews, backed by `SKILL.state` / `.agent-state/state.json`)
> 2. `agent-rules:stateful-execution` (SKILL.state) (recommended for deterministic single-agent linear execution)
> 3. `superpowers:executing-plans` (batch execution with manual checkpoints)
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a repository-first benchmark suite (`SWE-Canary` and `SWE-Core`) that purges synthetic command-line puzzles and evaluates Superstate exclusively on real open-source software engineering repositories across Go, TypeScript, and Python.

**Architecture:** Update task classification in `lab/benchmarks/task_sets.py` to define a tri-language 3-task `SWE-Canary` and a canonical 9-repository `SWE-Core` suite while formally excluding toy command-line puzzles. Update unit tests, doc standards (`docs/EVALUATION-PHILOSOPHY.md`, `AGENTS.md`), and execute canary verification comparing `superstate_daemon_dag` against `superstate_mcp`.

**Tech Stack:** Python 3.12, Pytest, Ruff, Pyright, Docker, Superstate CLI/Daemon.

## Global Constraints
- Target architecture: Python 3.12, strict typing with `ruff` and `pyright`.
- Always run tests and scripts using `.venv/bin/python`, never bare `python3`.
- Commit using conventional commit format with `--no-gpg-sign`.
- Strict anti-cheating invariant: held-out tests at container-root `/tests/` must remain sealed during agent phase.
- Anti-puzzle invariant: zero single-file toy puzzles (e.g. chess, regex log, cert generation) in canary or core suites.

---

### Task 1: Redefine Task Sets and Exclusion Rules in `lab/benchmarks/task_sets.py`

- **Depends on:** none

**Files:**
- Modify: `lab/benchmarks/task_sets.py`
- Modify: `tests/test_task_sets.py`
- Modify: `tests/test_canary_task_set.py`

**Interfaces:**
- Produces:
  - `CANARY_TASKS = ("build-cython-ext", "scc-bounded-memory-spilling", "katex-multicolumn-array-spans")`
  - `SWE_CORE_TASKS: tuple[str, ...]` (8 DataCurve repos + `build-cython-ext`)
  - Updated `EXCLUDED_TASKS` classifying command-line script puzzles with explicit reasons (`"toy: command-line puzzle / not a repository software engineering task"`).

**Steps:**
- [ ] Step 1.1: Update `tests/test_canary_task_set.py` to assert the tri-language canary (`build-cython-ext`, `scc-bounded-memory-spilling`, `katex-multicolumn-array-spans`).
- [ ] Step 1.2: Update `tests/test_task_sets.py` line 53 to allow `"toy"` or `"not a repository"` in addition to `"ceiling"` and `"floor"`.
- [ ] Step 1.3: Update `lab/benchmarks/task_sets.py` to define the new `CANARY_TASKS` and exclude toy puzzles (`chess-best-move`, `regex-log`, `vulnerable-secret`, `extract-elf`, `dna-insert`).
- [ ] Step 1.4: Run `.venv/bin/python -m pytest tests/test_task_sets.py tests/test_canary_task_set.py -v` to ensure all tests pass cleanly.
- [ ] Step 1.5: Commit with message `feat(eval): define tri-language SWE-Canary and exclude toy script puzzles`.

---

### Task 2: Codify Repository-First Invariant in Documentation

- **Depends on:** Task 1

**Files:**
- Modify: `docs/EVALUATION-PHILOSOPHY.md`
- Modify: `AGENTS.md`
- Modify: `README.md`

**Steps:**
- [ ] Step 2.1: Add the "Repository-First Invariant" section to `docs/EVALUATION-PHILOSOPHY.md`, explaining why toy puzzles (like chess) fail to evaluate control plane mechanisms and are banned.
- [ ] Step 2.2: Update `AGENTS.md` with the new `SWE-Canary` definition and the explicit distinction between software repository tasks vs toy puzzles.
- [ ] Step 2.3: Update `README.md` to reference `SWE-Canary` and `SWE-Core`.
- [ ] Step 2.4: Commit with message `docs(eval): codify repository-first invariant and ban on command-line puzzles`.

---

### Task 3: Update Canary Scripts and Experiment Ledger (EXP-065)

- **Depends on:** Task 1, Task 2

**Files:**
- Modify: `scripts/run_canary.sh`
- Modify: `scripts/run_exp065_canary.sh`
- Modify: `EXPERIMENTS.md`

**Steps:**
- [ ] Step 3.1: Update `scripts/run_canary.sh` and `scripts/run_exp065_canary.sh` to explicitly run `--tasks build-cython-ext,scc-bounded-memory-spilling,katex-multicolumn-array-spans`.
- [ ] Step 3.2: Update `EXPERIMENTS.md` entry for `EXP-065` to declare the tri-language repository canary.
- [ ] Step 3.3: Run `.venv/bin/python scripts/experiments.py check` to ensure ledger integrity.
- [ ] Step 3.4: Commit with message `chore(eval): update canary scripts and ledger for tri-language repository canary`.

---

### Task 4: Execute Tri-Language SWE-Canary Benchmark (EXP-065)

- **Depends on:** Task 3

**Files:**
- Output: `results/canary_dag_tdd_v_mcp_exp065.json`
- Modify: `EXPERIMENTS.md`

**Steps:**
- [ ] Step 4.1: Launch `scripts/run_exp065_canary.sh` in the background.
- [ ] Step 4.2: Monitor progress reactively until all 3 tri-language repository tasks complete on both arms.
- [ ] Step 4.3: Verify results via `.venv/bin/python scripts/experiments.py scan`.
- [ ] Step 4.4: Record results in `EXPERIMENTS.md`, transitioning `EXP-065` from `PLANNED` to `STANDS`.
- [ ] Step 4.5: Commit with message `feat(eval): record EXP-065 tri-language repository canary results`.

---

### Task 5: Complete Verification and Finish Feature Branch

- **Depends on:** Task 4

**Files:**
- All modified repository files

**Steps:**
- [ ] Step 5.1: Run `.venv/bin/python -m pytest tests/ -q` to verify entire 300+ test suite passes.
- [ ] Step 5.2: Run `.venv/bin/ruff check lab/ tests/` and fix any lint issues.
- [ ] Step 5.3: Run `pyright lab/ tests/` for type validation.
- [ ] Step 5.4: Execute `verification-before-completion` protocol.
- [ ] Step 5.5: Integrate feature branch into `main` following `finishing-a-development-branch`.
