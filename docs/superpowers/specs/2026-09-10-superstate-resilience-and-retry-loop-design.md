# Superstate Resilience, Diagnostic Retry Loops, and Git Native State Tracking Design

**Date:** 2026-09-10  
**Status:** Approved  
**Author:** Pair Programming Agent & Daniel Fisher  

---

## 1. Context & Motivation

In recent benchmark evaluations across Terminal-Bench tasks, Superstate achieved dramatic speed and efficiency wins on multi-step server and git configuration tasks (e.g. 64% faster than Superpowers on `configure-git-webserver`). However, on greenfield and compilation tasks (`build-cython-ext`, `multi-source-data-merger`), Superstate suffered from two severe harness-level regressions:

1. **Fatal Abort on Failed Gates**:
   When an agent planned a verification command (e.g. `python setup.py build_ext --inplace`), if that command failed on an early milestone before all compiler fixes were in place, the adapter in `superstate-eval` immediately aborted the entire task without providing diagnostic feedback or allowing another turn.
2. **Missing Git in Greenfield Workspaces**:
   Tasks that begin with an empty `/app` have no `.git` repository. When `--verify-git-clean` was checked, `git status` crashed with `fatal: not a git repository`, immediately failing the task.

In addition, Git operations should be an intrinsic capability of `superstate` rather than an artificial harness injection.

---

## 2. Goals & Non-Goals

### Goals
- **Milestone Diagnostic Retry Loop**: If a milestone verification gate fails, provide the exit code, command, and captured stdout/stderr back to the agent in a structured retry prompt for turn $N+1$ (up to `max_turns_per_milestone`).
- **Epistemic Failure Ledgering**: Record failed verification gate output into the state ledger via `record_note` (`superstate note`) so that even bounded context turns know the exact compiler/test errors.
- **Greenfield Git Resilience**:
  - In `superstate-eval`: Check if `.git` exists before passing `--verify-git-clean`, or auto-init git at workspace setup.
  - In `superstate` (Rust): Ensure `superstate state init` creates a root git baseline if no repository exists, enabling native diffs, checkpoints, and clean checks anywhere.

### Non-Goals
- Full rewrite of `worktrunk` crate integration in this PR (tracked as Phase 2 architectural enhancement).

---

## 3. Architecture & Mechanics

### 3.1 Diagnostic Retry Loop in `lab/engine/adapters/superstate.py`

When `_advance_state(...)` returns `False`:
- Check if `_turn + 1 < self.max_turns_per_milestone` and time remains in budget.
- If turns remain:
  - Format a diagnostic retry prompt:
    ```markdown
    ## VERIFICATION GATE FAILED (Attempt {milestone_turns} of {self.max_turns_per_milestone})
    The verification command `{milestone.verify_cmd}` failed with exit code {gate_exit_code}.

    ### Gate Output:
    ```
    {gate_output}
    ```

    Please diagnose this failure, apply the necessary code or configuration changes, and ensure the verification passes.
    ```
  - Set `current_prompt` to this retry prompt.
  - Record failure note to the ledger: `self.record_note(workspace_path, f"[Gate Failed] {milestone.verify_cmd}: {gate_output[:1000]}")`.
  - `continue` to next turn instead of `break`.
- If no turns remain or budget is exhausted:
  - Mark milestone failed and terminate.

### 3.2 Greenfield Git Resilience

In `lab/engine/adapters/superstate.py`:
- In `_advance_state`:
  - Check `(workspace_path / ".git").is_dir()`.
  - If `.git` does not exist: omit `--verify-git-clean` from `superstate state next` call so greenfield tasks do not crash.
  - In `setup_workspace`: if `.git` does not exist, initialize `git init -b main` and `git commit --allow-empty -m "chore: baseline"`.

---

## 4. Verification & Testing

- Unit tests in `tests/test_adapters_superstate.py`:
  - Verify that a failing gate triggers a retry prompt with diagnostics in the next turn.
  - Verify that a greenfield workspace without `.git` does not fail state advancement.
