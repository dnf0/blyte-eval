# Superstate Resilience and Diagnostic Retry Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Choose an execution mode:
> 1. `superpowers:subagent-driven-development` (recommended for multi-agent reviews, backed by `SKILL.state` / `.agent-state/state.json`)
> 2. `agent-rules:stateful-execution` (SKILL.state) (recommended for deterministic single-agent linear execution)
> 3. `superpowers:executing-plans` (batch execution with manual checkpoints)
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide diagnostic feedback retries on failed milestone verification gates and eliminate greenfield git crashes so Superstate runs reliably across all benchmark tasks.

**Architecture:** Update `lab/engine/adapters/superstate.py` to intercept failed verification gates, construct diagnostic feedback prompts with gate outputs, record failure signatures in the epistemic ledger, and continue to the next turn up to `max_turns_per_milestone`. Update `superstate state init` in the Rust binary to auto-initialize git baselines on non-git workspaces.

**Tech Stack:** Python 3.12, Rust 2024 edition, pytest, ruff, pyright.

## Global Constraints
- Python 3.12 syntax with strict type annotations.
- Conventional commits.
- Pass `pytest tests/`.

---

### Task 1: Implement Greenfield Git Handling in `lab/engine/adapters/superstate.py`

- **Depends on:** none

**Files:**
- Modify: `lab/engine/adapters/superstate.py:440-475`
- Test: `tests/test_superstate_resilience.py`

**Steps:**
- [ ] Add check in `_advance_state`: if not `(workspace_path / ".git").is_dir()`, do not pass `--verify-git-clean` to `superstate state next`.
- [ ] In `setup_workspace`: if not `(workspace_path / ".git").is_dir()`, initialize a baseline git repository (`git init -b main && git commit --allow-empty -m "chore: initial baseline"`).

---

### Task 2: Implement Milestone Diagnostic Retry Loop in `lab/engine/adapters/superstate.py`

- **Depends on:** Task 1

**Files:**
- Modify: `lab/engine/adapters/superstate.py:760-800`
- Test: `tests/test_superstate_resilience.py`

**Steps:**
- [ ] In `_run_milestone_loop` / `run`: when `self._advance_state(...)` returns `False`:
  - Check if `milestone_turns < self.max_turns_per_milestone` and budget remains.
  - If retries remain:
    - Construct diagnostic retry prompt with gate command, exit code, and captured stderr/stdout.
    - Record failure note to epistemic ledger via `self.record_note`.
    - Update `current_prompt` and `continue` instead of breaking.
  - If no retries remain: set `milestone_failed` and break.

---

### Task 3: Unit Tests for Retry Loop & Greenfield Handling

- **Depends on:** Task 1, Task 2

**Files:**
- Create: `tests/test_superstate_resilience.py`

**Steps:**
- [ ] Write test verifying retry prompt generation when verification gate fails on turn 1 and passes on turn 2.
- [ ] Write test verifying greenfield workspace without `.git` executes `_advance_state` without crashing.
- [ ] Run `uv run pytest tests/test_superstate_resilience.py`.

---

### Task 4: Native Git Initialization in Rust `superstate`

- **Depends on:** none

**Files:**
- Modify: `/Users/danielfisher/repos/superstate/crates/superstate-cli/src/commands/state.rs`
- Test: `cargo test` in `/Users/danielfisher/repos/superstate`

**Steps:**
- [ ] In `cmd_init`: if no `.git` exists in `repo_root` or its ancestors, run `git init` and create initial empty commit.
- [ ] Run `cargo test -p superstate-cli`.
- [ ] Rebuild `cargo build` in `/Users/danielfisher/repos/superstate`.

---

### Task 5: Verification & Checkpoint

- **Depends on:** Task 1, Task 2, Task 3, Task 4

**Steps:**
- [ ] Run `uv run ruff check lab tests`.
- [ ] Run `uv run pytest tests/`.
- [ ] Commit changes with conventional commit messages.
