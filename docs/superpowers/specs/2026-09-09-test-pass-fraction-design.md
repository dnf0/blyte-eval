# Design Specification: Test Pass Fraction & Test Statistics Propagation

Date: 2026-09-09
Author: Antigravity & User

## 1. Context & Motivation

SWE-bench and frontier evaluation benchmarks (such as `datacurve/fastapi-deprecation-response-headers`) execute multi-test verification suites containing:
1. **Fail-to-Pass (F2P)**: Specific regression/feature tests that failed on the base commit and must pass with the agent's patch.
2. **Pass-to-Pass (P2P)**: Broad regression test suites that must remain green.
3. Total test counts often numbering in the thousands (e.g. 3,271 tests for FastAPI).

The held-out verifier generates `verifier/reward.json` with granular statistics:
```json
{
  "reward": 1,
  "f2p_total": 137,
  "f2p_passed": 137,
  "p2p_total": 3134,
  "p2p_passed": 3134,
  "f2p": 1.0,
  "p2p": 1.0,
  "partial": 1.0
}
```
Currently, `HeldOutVerifier` reads this dictionary into `VerifierOutcome.stats`, but `extract_and_grade` drops `stats`, returning only binary `passed` and top-level float `reward`. As a result, telemetry files (`run.json`), cohort analyzers, and CLI scripts lose the underlying test counts and test pass fraction.

## 2. Architectural Design

### 2.1 EvaluationResult Dataclass Extension
In `lab/engine/extractor.py`:
- Add `stats: dict[str, Any] | None = None` to `EvaluationResult`.
- When `verifier.run(...)` executes, assign `stats = outcome.stats`.
- In the fallback non-held-out path, parse `reward.json` if available and assign `stats = data`.

### 2.2 Metric Extraction Helper
Add `compute_test_metrics(stats: dict[str, Any] | None, passed: bool) -> dict[str, Any]` in `lab/engine/extractor.py`:
- Extracts `f2p_total`, `f2p_passed`, `p2p_total`, `p2p_passed`.
- Calculates:
  - `f2p_fraction`: `f2p_passed / f2p_total` if `f2p_total > 0` else None.
  - `p2p_fraction`: `p2p_passed / p2p_total` if `p2p_total > 0` else None.
  - `tests_passed`: `f2p_passed + p2p_passed` (or fallback).
  - `tests_total`: `f2p_total + p2p_total` (or fallback).
  - `test_pass_fraction`: `tests_passed / tests_total` if `tests_total > 0` else (1.0 if passed else 0.0).
- If `stats` is None or lacks `f2p`/`p2p` keys:
  - `test_pass_fraction`: 1.0 if `passed` else 0.0.
  - `f2p_fraction`: None
  - `p2p_fraction`: None

### 2.3 AblationRunner Telemetry Integration
In `lab/engine/runner.py`:
- Call `compute_test_metrics(grade_res.stats, grade_res.passed)` after `extract_and_grade`.
- Merge into `RunTelemetry.extra`:
  - `extra["test_stats"]`: `grade_res.stats`
  - `extra["test_pass_fraction"]`: float
  - `extra["f2p_fraction"]`: float | None
  - `extra["p2p_fraction"]`: float | None
  - `extra["tests_passed"]`: int | None
  - `extra["tests_total"]`: int | None
- These fields automatically serialize into `run.json`.

### 2.4 CLI Output Formatting
In `scripts/smoke_test_agy.py` (and runner log messages):
- Log `Test Pass Frac: XX.XX% (X/Y)` when available.
- Log `F2P: XX.XX%` and `P2P: XX.XX%` when available.

## 3. Testing & Verification

1. Unit tests in `tests/test_extractor.py`:
   - Verify `extract_and_grade` propagates `stats` from both held-out verifier and local `reward.json`.
   - Verify `compute_test_metrics` handles full stats, zero totals, partial stats, and None.
2. Unit tests in `tests/test_runner.py`:
   - Verify `AblationRunner.run_task` populates `telemetry.extra` with `test_pass_fraction` and `test_stats`.
3. Verify full test suite passes with `uv run pytest -q`.
