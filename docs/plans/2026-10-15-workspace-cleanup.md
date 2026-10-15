# Plan: delete run workspaces once graded

A 28-run benchmark on 2026-10-15 filled the disk: every run leaves its whole workspace under
`/tmp/blyte_eval_runs/<timestamp>/eval-<task>-<arm>-<id>/workspace` (the repository plus build
output such as `target/`, `.venv`, `node_modules`; 100 MB to over 1.5 GB a run), and nothing
deletes it. The run's `logs/` (reports, events, `model.patch`, `reward.json`, test output; a few
MB) is what later scripts read, so it stays.

E5 and E6 touch different files and can run in parallel.

### Task E5

**Goal:** after a run is graded, its `workspace/` directory is deleted unless the operator asks to
keep it. `logs/` and `mcp/` stay.

**Where:**
- `lab/engine/runner.py`: `AblationRunner.__init__` (around lines 82-99) and `run_task` (starts
  line 118). Grading (`extract_and_grade`, around line 324) and `write_run_manifest` (around line
  409) both finish before the `finally:` block (around line 406), which already prunes Docker
  resources. `workspace_path = run_dir / "workspace"` and `logs_dir = run_dir / "logs"` are set
  around lines 216-225.
- `scripts/paired_run.py`: `build_parser()` (around lines 69-137) and where it builds
  `AblationRunner` (around line 350).
- `scripts/guard_activity.py` (line 34) and `scripts/read_budget.py` (line 70) read
  `<workspace>/.agent-state/guard-activity.jsonl`.

**Change:**
1. `AblationRunner.__init__` takes `keep_workspaces: bool = False`.
2. At the end of `run_task`, once grading and the manifest are written and the sandbox container
   is gone, when `keep_workspaces` is false and `workspace_path` exists:
   - copy `workspace_path / ".agent-state" / "guard-activity.jsonl"`, if present, to
     `logs_dir / "artifacts" / "guard-activity.jsonl"` (create the directory);
   - `shutil.rmtree(workspace_path, ignore_errors=True)`.
   A failure to copy or delete is logged as a warning and never changes the run's result. Do it
   for passed, failed and errored runs alike. Do not delete anything else under `run_dir`.
3. `paired_run.py` gets `--keep-workspaces` (`store_true`, help: "keep each run's workspace
   directory after grading; by default it is deleted and only logs/ is kept") and passes it to
   `AblationRunner`.
4. `guard_activity.py` and `read_budget.py` accept either a workspace or a run's `logs/`
   directory: look for `.agent-state/guard-activity.jsonl` first, then
   `artifacts/guard-activity.jsonl`, and say in the error which paths were tried. Update their
   help text to match.

**Tests** (no Docker; follow the mocks in `tests/test_ablation_runner.py`):
- By default, after `run_task` the workspace directory is gone, while `logs/run.json` and an
  archived `logs/artifacts/guard-activity.jsonl` (seeded in the fake workspace) remain.
- With `keep_workspaces=True` the workspace remains.
- A run whose driver raises still has its workspace deleted, and its telemetry is unchanged.
  Existing tests that inspect the workspace after `run_task` pass `keep_workspaces=True`.
- `paired_run`'s parser defaults `--keep-workspaces` to false and passes it through.
- `guard_activity.py`/`read_budget.py` find the log under `logs/artifacts/`.

### Task E6

**Dropped (2026-10-15):** the premise was wrong. `_merge_back` already removes the copy after a
clean merge (`rm -rf {copy}`) and keeps it on a conflict for inspection, so only the error paths
were left, and the rewrite this produced wasn't worth merging.

**Goal:** a dispatch's working copy inside the task container is removed once its changes are
merged back, so copies don't pile up in the container or in the snapshot image the grader commits
from it.

**Where:** `lab/engine/drivers/container_exec_mcp.py`, `ContainerExec.dispatch`. The copy is
`f"{self.copy_root}/blyte-dispatch-{n}"` (around line 350, `copy_root` defaults to `/tmp`). Its
changes are merged back by `self._merge_back(copy)` (around lines 379 and 391), and nothing
deletes the copy afterwards.

**Change:** after every `_merge_back(copy)` call, on success and error paths alike, remove the copy
with `self._sh(f"rm -rf {shlex.quote(copy)}")`, so put it in one place (for example a `finally:`
around the code after the copy is made, or a small helper both paths call). A failed `rm` is
logged and ignored. Never remove it before the merge has run. Keep the existing `rm -rf {copy}`
before `cp -a`.

**Tests** (`tests/test_container_exec_mcp.py`, with `_sh` and the blyte call monkeypatched as the
existing tests do):
- A successful dispatch issues an `rm -rf` of its copy dir after the merge-back command.
- A dispatch whose report is missing (the error path) also removes its copy after merging back.
- Two dispatches remove their own copy dirs and not each other's.
