# Concurrent Verifier Seal Resolution & 4-Worker Concurrency Plan

> **Goal:** Fix the race condition where `TaskSpec.has_verifier_dockerfile` returns `False` when `tests/` is sealed (`mode 000`) by a concurrent worker, preventing false-negative in-container grading fallbacks, and re-launch the benchmark suite with concurrency 4.

---

### Task 1: TaskSpec `has_verifier_dockerfile` Seal Resilience & Test
- **File to modify:** `lab/benchmarks/task_loader.py`
- **File to modify:** `tests/test_task_loader.py`
- **Changes:**
  - Cache `_has_verifier_dockerfile` on `TaskSpec` during `__post_init__` when unsealed.
  - In `has_verifier_dockerfile` property:
    - If cached value is not None, return it immediately.
    - If `(td / "Dockerfile").is_file()` raises `OSError` (e.g. `PermissionError` when sealed `000`), fall back to checking `AnswerKeyGuard.staged_copy(td) / "Dockerfile"` or the staging cache directory.
  - Add test in `tests/test_task_loader.py`:
    - Create a temporary task directory with `tests/Dockerfile`.
    - Construct `TaskSpec`.
    - `chmod 000` the `tests` directory.
    - Verify `task.has_verifier_dockerfile` still returns `True`.
- **Verification:** `uv run pytest tests/test_task_loader.py`

---

### Task 2: Concurrency 4 Configuration
- **File to modify:** `scripts/run_weekend_benchmark.sh`
- **Changes:**
  - Update `--concurrency 2` to `--concurrency 4`.
  - Update header comments and echo statements to reflect concurrency: 4 workers.
- **Verification:** Inspect script and verify syntax with `bash -n scripts/run_weekend_benchmark.sh`.

---

### Task 3: Full Verification Suite
- Run `uv run ruff check .`
- Run `uv run pyright lab`
- Run `uv run pytest tests/`
- Verify clean status.

---

### Task 4: Commit & Merge
- Commit changes with conventional commit: `fix(benchmarks): resolve concurrent verifier seal check and upgrade benchmark to 4 workers`.
- Merge branch `fix/concurrent-verifier-seal-resolution` into `main`.
- Update knowledge graph via `uvx --from graphifyy graphify update .`.

---

### Task 5: Launch Benchmark Suite at Concurrency 4
- Run `./scripts/run_weekend_benchmark.sh` in background with OS completion notification.
- Verify 4 workers spawned and logging properly.
