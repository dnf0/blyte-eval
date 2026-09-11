# Design Spec: Dynamic Container Workspace Switching for Worktree Isolation

Date: 2026-09-11
Status: Approved

## 1. Problem Statement
In containerized benchmarks (e.g. Terminal Bench, SWE-bench), benchmark tasks hardcode container root paths such as `/app/<file>`.
When `superstate` isolates an agent into a Git worktree (`.wt/task-N`), files written by the agent live at `/app/.wt/task-N/<file>`.
If the Docker container mounts the host workspace directly onto `/app`, `/app` becomes an immutable bind mount. This causes:
1. Benchmark commands checking `/app/<file>` fail during the turn because the file is in `.wt/task-N`.
2. The agent runs self-checks via `./run-in-container`, observes failure, and enters 15+ tool call diagnostic loops.
3. Post-hoc regex rewriting of verification commands is fragile and leaves the agent confused during execution.

## 2. Proposed Architecture

### Dynamic `/app` Symlink via `/workspace_root` Mount
1. **Container Bind Mount Setup** (`lab/engine/runner.py`):
   Instead of mounting `workspace_dir` to `/app`, mount it to `/workspace_root`:
   ```python
   CONTAINER_MOUNT_ROOT = "/workspace_root"
   CONTAINER_APP_SYMLINK = "/app"
   ```
   At container launch, initialize `/app` as a symlink pointing to `/workspace_root`:
   ```bash
   rm -rf /app && ln -s /workspace_root /app
   ```
   This ensures backwards compatibility for all non-worktree arms (`vanilla`, `superpowers`, `superstate_rust_inplace`). To all containers, `/app` points directly to the workspace root.

2. **Dynamic Worktree Repointing** (`lab/engine/adapters/superstate.py`):
   When executing a milestone turn in worktree mode:
   - At turn start, resolve the relative worktree path (e.g. `.wt/task-1`).
   - Run a sub-millisecond container command to repoint `/app`:
     ```bash
     ln -sfn /workspace_root/.wt/task-1 /app
     ```
   - All tools, scripts, and commands referencing `/app` (e.g. `sqlite3 /app/main.db`, `open('/app/recovered.json')`) now seamlessly and transparently read and write directly to `.wt/task-1`.
   - When the milestone passes verification and is merged by `superstate state next`, repoint `/app` back to `/workspace_root` (or to the next worktree `.wt/task-2`).
   - At the conclusion of all milestones, ensure `/app` points to `/workspace_root` so that the final held-out grader tests the merged root.

3. **Worktree-Aware Bridge Script** (`lab/engine/drivers/agy_cli.py`):
   Ensure `./run-in-container` defaults to `-w /app` so commands execute in the active worktree context.

## 3. Benefits & Performance
- **Zero Test Lag**: Updating a symlink via `ln -sfn` executes in <1ms without restarting containers or copying files.
- **Zero Prompt Hacks**: No regex rewriting of task specifications, prompts, or test scripts.
- **True Worktree Isolation**: Files are created strictly in `.wt/task-N`, tracked on Git branch `wt/task-N`, and merged by `superstate`.
- **Fair Benchmark**: Measures the real speed and accuracy of worktrees without harness friction.
