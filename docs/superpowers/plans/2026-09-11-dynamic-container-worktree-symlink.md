# Dynamic Container Workspace Switching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Choose an execution mode:
> 1. `superpowers:subagent-driven-development` (recommended for multi-agent reviews, backed by `SKILL.state` / `.agent-state/state.json`)
> 2. `agent-rules:stateful-execution` (SKILL.state) (recommended for deterministic single-agent linear execution)
> 3. `superpowers:executing-plans` (batch execution with manual checkpoints)
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate container worktree path impedance in `superstate-eval` by mounting the host workspace to `/workspace_root` and using dynamic `/app` symlink repointing to active worktrees.

**Architecture:**
1. `runner.py` mounts the host workspace directory to `/workspace_root` and initializes `/app` as a symlink pointing to `/workspace_root`.
2. `superstate.py` adapter repoints `/app` to `/workspace_root/.wt/<slug>` when a worktree milestone turn begins, and restores it to `/workspace_root` after merge.
3. `agy_cli.py` container bridge executes commands with `-w /app`.

**Tech Stack:** Python 3.12, Docker SDK for Python, Pytest.

## Global Constraints
- Do NOT break non-worktree arms (`vanilla`, `superpowers`, `superstate_rust_inplace`).
- Repointing `/app` must use `ln -sfn`, executing in <1ms without container restarts.
- Full compatibility with held-out grading verifiers at `/app`.

---

### Task 1: Runner Mount Decoupling & Container Symlink Setup

- **Depends on:** none

**Files:**
- Modify: `lab/engine/runner.py:225-245`
- Modify: `lab/engine/drivers/agy_cli.py:143-155`
- Test: `tests/test_container_symlink_setup.py`

**Interfaces:**
- Consumes: `DockerManager.run_sandbox`, `Container.exec_run`
- Produces: Sandbox containers where host workspace is at `/workspace_root` and `/app` is a symlink to `/workspace_root`.

**Steps:**
- [ ] Write failing test in `tests/test_container_symlink_setup.py` verifying `/workspace_root` mount and initial `/app` symlink.
- [ ] Update `runner.py` to bind-mount workspace to `/workspace_root` and execute `sh -c "rm -rf /app && ln -s /workspace_root /app"`.
- [ ] Update `agy_cli.py` bridge script to include `-w /app`.
- [ ] Run `uv run pytest tests/test_container_symlink_setup.py` to ensure tests pass.
- [ ] Commit: `feat(eval): mount workspace at /workspace_root with dynamic /app symlink`.

---

### Task 2: Worktree Turn Repointing in Superstate Adapter

- **Depends on:** Task 1

**Files:**
- Modify: `lab/engine/adapters/superstate.py:470-520, 970-1010`
- Test: `tests/test_adapter_worktree_symlink.py`

**Interfaces:**
- Consumes: `container.exec_run`, active worktree path from `superstate`
- Produces: Dynamic repointing `ln -sfn /workspace_root/{rel} /app` at turn start, and `ln -sfn /workspace_root /app` upon turn completion and cleanup.

**Steps:**
- [ ] Write failing test in `tests/test_adapter_worktree_symlink.py` verifying container exec calls `ln -sfn` for active worktree and restores to `/workspace_root`.
- [ ] Update `adapters/superstate.py` to execute symlink switch on container when `wt` is present and not `no_worktree`.
- [ ] Remove obsolete prompt regex rewriting shims.
- [ ] Run `uv run pytest tests/test_adapter_worktree_symlink.py` and workspace tests.
- [ ] Commit: `feat(adapter): dynamically repoint /app to active worktree during milestone turns`.

---

### Task 3: Live Verification on `db-wal-recovery`

- **Depends on:** Task 1, Task 2

**Steps:**
- [ ] Run `uv run python scripts/paired_run.py --tasks db-wal-recovery --arms superstate_rust --out results/db_wal_rust_symlink.json`.
- [ ] Inspect agent transcript to confirm 0 diagnostic loops on container paths.
- [ ] Verify test results: 7/7 tests passed, wall-clock time < 3.5 minutes.
