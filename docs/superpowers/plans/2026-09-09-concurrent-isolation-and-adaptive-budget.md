# Concurrent Evaluation Isolation & Universal Progress Budgeting Implementation Plan

> **Note:** Implementation plan following TDD for `superstate-eval`.

## Proposed File Changes
- Create: `lab/engine/governor.py`
- Create: `tests/test_governor.py`
- Modify: `lab/sandbox/docker_manager.py`
- Modify: `tests/test_docker_manager.py`
- Create: `lab/engine/progress_tracker.py`
- Create: `tests/test_progress_tracker.py`
- Create: `lab/engine/extractor.py`
- Create: `tests/test_extractor.py`
- Modify: `lab/engine/runner.py`
- Create: `tests/test_concurrent_runner.py`

---

### Task 1: Dynamic Machine-Aware Concurrency Governor
- **Files:** `lab/engine/governor.py`, `tests/test_governor.py`
- **Interfaces:**
  - `SystemSpecs`: dataclass capturing `cpu_count: int`, `total_ram_gb: float`, `available_ram_gb: float`, `free_disk_gb: float`.
  - `ConcurrencyGovernor`:
    - `get_system_specs() -> SystemSpecs`
    - `calculate_max_concurrency(specs: SystemSpecs, user_max: int | None = None) -> int`
    - `async acquire_slot()` / `contextmanager slot()`
- **TDD Steps:**
  1. Write failing tests in `tests/test_governor.py` asserting concurrency formula against various synthetic specs (12 CPU/24GB RAM $\to$ 4 workers, 4 CPU/8GB $\to$ 1 worker, disk constrained $\to$ throttled).
  2. Implement `lab/engine/governor.py`.
  3. Verify tests pass.

### Task 2: Container Resource Constraints & Volume Isolation
- **Files:** `lab/sandbox/docker_manager.py`, `tests/test_docker_manager.py`
- **Interfaces:**
  - Update `DockerManager.run_sandbox`:
    - Accept `nano_cpus: int | None = None` and `mem_limit: str | None = "4g"`.
    - Accept `logs_dir: Path | None = None` and auto-mount to `/logs:rw`.
    - Pass container name with run ID: `eval-{arm}-{task_id}-{run_id}`.
- **TDD Steps:**
  1. Add tests in `tests/test_docker_manager.py` verifying `nano_cpus`, `mem_limit`, and `/logs` mount are passed to `client.containers.run`.
  2. Implement the changes in `lab/sandbox/docker_manager.py`.
  3. Verify all tests pass.

### Task 3: Universal Progress-Earned Budget Tracker
- **Files:** `lab/engine/progress_tracker.py`, `tests/test_progress_tracker.py`
- **Interfaces:**
  - `ProgressTracker`:
    - `check_progress(arm: str, workspace_path: Path, last_commit: str | None, current_milestone: int) -> tuple[bool, str]`
    - Signals `BudgetPolicy.record_milestone_progress()` when a new git commit appears or a state milestone advances.
- **TDD Steps:**
  1. Write tests in `tests/test_progress_tracker.py` verifying commit detection on mock repos.
  2. Implement `lab/engine/progress_tracker.py`.
  3. Verify tests pass.

### Task 4: Blind Extraction & Verification Pipeline
- **Files:** `lab/engine/extractor.py`, `tests/test_extractor.py`
- **Interfaces:**
  - `EvaluationResult`: dataclass with `passed: bool`, `reward: float | None`, `exit_code: int`, `patch_path: Path | None`, `failure_reason: str | None`.
  - `extract_and_grade(sandbox, task, output_dir: Path) -> EvaluationResult`:
    - Generates `model.patch` via `git diff`.
    - Injects tests and runs verification command.
    - Reads `/logs/verifier/reward.json`.
- **TDD Steps:**
  1. Write tests in `tests/test_extractor.py` with mock sandbox returning reward 1.0 vs 0.0 vs error.
  2. Implement `lab/engine/extractor.py`.
  3. Verify tests pass.

### Task 5: End-to-End Concurrent Runner & Integration
- **Files:** `lab/engine/runner.py`, `tests/test_concurrent_runner.py`
- **Interfaces:**
  - Update `AblationRunner.run_cohort(tasks, arms, max_workers: int | None)`:
    - Queries `ConcurrencyGovernor` for worker count.
    - Uses `ThreadPoolExecutor(max_workers=concurrency)`.
    - Emits live progress and generates final frontier summary table.
- **TDD Steps:**
  1. Write integration test in `tests/test_concurrent_runner.py` with mock task cohort.
  2. Implement `run_cohort` in `lab/engine/runner.py`.
  3. Verify full test suite passes.
