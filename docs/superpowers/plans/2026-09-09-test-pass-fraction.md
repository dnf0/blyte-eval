# Test Pass Fraction & Test Statistics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Choose an execution mode:
> 1. `superpowers:subagent-driven-development` (recommended for multi-agent reviews, backed by `SKILL.state` / `.agent-state/state.json`)
> 2. `agent-rules:stateful-execution` (SKILL.state) (recommended for deterministic single-agent linear execution)
> 3. `superpowers:executing-plans` (batch execution with manual checkpoints)
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Propagate granular test statistics (`f2p`, `p2p`, `total_passed`, `total_tests`) and calculate `test_pass_fraction` in `EvaluationResult`, `RunTelemetry.extra`, and CLI smoke reports.

**Architecture:** Extend `EvaluationResult` in `lab/engine/extractor.py` to retain `stats: dict[str, Any] | None`. Add `compute_test_metrics` to normalize fractions and test counts across benchmark verifiers. In `lab/engine/runner.py`, merge computed metrics into `RunTelemetry.extra`. Update `scripts/smoke_test_agy.py` to format and print test statistics.

**Tech Stack:** Python 3.12, pytest, dataclasses, Docker Python SDK.

## Global Constraints
- Python 3.12 style with explicit typing, small functions, and reproducible CLI steps.
- Maintain backward compatibility for tasks with binary exit codes or absent `reward.json`.
- All tests must pass with `uv run pytest -q`.
- Lint and static type checks must pass with `uv run ruff check lab tests scripts` and `uv run pyright lab tests scripts`.

---

### Task 1: Extend EvaluationResult and Implement compute_test_metrics

- **Depends on:** none

**Files:**
- Modify: `lab/engine/extractor.py`
- Test: `tests/test_extractor.py`

**Interfaces:**
- Produces:
  - `compute_test_metrics(stats: dict[str, Any] | None, passed: bool) -> dict[str, Any]`
  - `EvaluationResult.stats: dict[str, Any] | None = None`

- [ ] **Step 1: Write the failing tests**
Write unit tests in `tests/test_extractor.py` testing:
1. `compute_test_metrics` with full SWE-bench / CTRF `f2p` and `p2p` counts.
2. `compute_test_metrics` with zero total tests.
3. `compute_test_metrics` with `None` stats falling back to binary `passed`.
4. `extract_and_grade` returning `stats` from both held-out verifier and local fallback.

- [ ] **Step 2: Run tests to verify they fail**
Run: `uv run pytest tests/test_extractor.py -k "test_metrics" -v`
Expected: FAIL with `ImportError` or `AssertionError`.

- [ ] **Step 3: Write minimal implementation**
1. Add `stats: dict[str, Any] | None = None` to `EvaluationResult` in `lab/engine/extractor.py`.
2. Implement `compute_test_metrics(stats: dict[str, Any] | None, passed: bool) -> dict[str, Any]`.
3. In `extract_and_grade`:
   - Pass `outcome.stats` when held-out verifier runs.
   - When non-held-out fallback runs, parse `data` from `reward.json` as `stats`.
   - Include `stats=stats` in `EvaluationResult(...)`.

- [ ] **Step 4: Run tests to verify they pass**
Run: `uv run pytest tests/test_extractor.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
Run:
```bash
git add lab/engine/extractor.py tests/test_extractor.py
git commit -m "feat(extractor): extend EvaluationResult with stats and compute_test_metrics"
```

---

### Task 2: Integrate Test Metrics into Runner Telemetry and CLI Output

- **Depends on:** Task 1

**Files:**
- Modify: `lab/engine/runner.py`
- Modify: `scripts/smoke_test_agy.py`
- Test: `tests/test_runner.py`

**Interfaces:**
- Consumes: `compute_test_metrics`, `EvaluationResult.stats` from `lab/engine/extractor.py`
- Produces: `RunTelemetry.extra` populated with `test_stats`, `test_pass_fraction`, `f2p_fraction`, `p2p_fraction`, `tests_passed`, `tests_total`.

- [ ] **Step 1: Write the failing tests**
Write unit tests in `tests/test_runner.py` asserting that `AblationRunner.run_task` extracts `stats` from `grade_res`, computes test metrics, and includes `test_pass_fraction` in `telemetry.extra`.

- [ ] **Step 2: Run tests to verify they fail**
Run: `uv run pytest tests/test_runner.py -k "test_pass_fraction" -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**
1. In `lab/engine/runner.py`:
   - Import `compute_test_metrics` from `lab.engine.extractor`.
   - After `extract_and_grade`, compute metrics dictionary.
   - Merge metrics into `extra` dict.
2. In `scripts/smoke_test_agy.py`:
   - Extract `test_pass_fraction`, `f2p_fraction`, `p2p_fraction`, `tests_passed`, `tests_total` from `result.extra`.
   - Log them cleanly in the final report block.

- [ ] **Step 4: Run tests to verify they pass**
Run: `uv run pytest tests/test_runner.py tests/test_extractor.py -v`
Expected: PASS.

- [ ] **Step 5: Run full verification checklist**
Run: `uv run ruff check lab tests scripts && uv run pyright lab tests scripts && uv run pytest -q`
Expected: 0 errors, all tests pass.

- [ ] **Step 6: Commit**
Run:
```bash
git add lab/engine/runner.py scripts/smoke_test_agy.py tests/test_runner.py
git commit -m "feat(runner): populate test pass fractions in telemetry and smoke report"
```
