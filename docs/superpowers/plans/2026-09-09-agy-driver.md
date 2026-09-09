# Antigravity CLI Driver (`AgyCliDriver`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Choose an execution mode:
> 1. `superpowers:subagent-driven-development` (recommended for multi-agent reviews, backed by `SKILL.state` / `.agent-state/state.json`)
> 2. `agent-rules:stateful-execution` (SKILL.state) (recommended for deterministic single-agent linear execution)
> 3. `superpowers:executing-plans` (batch execution with manual checkpoints)
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `AgyCliDriver` to evaluate `agy` with `gemini-3.8-flash-high` against benchmark tasks using a workspace-scoped `./run-in-container` bridge.

**Architecture:** Create `AgyCliDriver(AgentDriver)` that builds CLI arguments for `agy.real`, captures structured JSON telemetry, and automatically equips the task workspace with an executable `./run-in-container` script for sandboxed build/test execution.

**Tech Stack:** Python 3.12, Docker SDK, Pytest, Subprocess, UV.

## Global Constraints

- Python 3.12 with explicit typing, small functions, and docstrings explaining WHY/WHAT.
- Strict type checks with `pyright` and linting with `ruff`.
- Do not mutate operator configuration in `~/.gemini/config/mcp_config.json`.
- All tests must pass via `uv run pytest -q`.

---

### Task 1: Implement `AgyCliDriver` Core and Container Execution Bridge

- **Depends on:** None

**Files:**
- Create: `lab/engine/drivers/agy_cli.py`
- Create: `tests/test_agy_cli_driver.py`
- Modify: `lab/engine/drivers/__init__.py`

**Interfaces:**
- Produces: `AgyCliDriver(AgentDriver)`, `AgyCliDriverError(RuntimeError)`
  - `AgyCliDriver.__init__(model="gemini-3.8-flash-high", cli_path=None, extra_args=None, env=None, container_exec=True)`
  - `AgyCliDriver.run(task, workspace_path, prompt_override=None, conversation_id=None, timeout_sec=3600.0, container=None) -> DriverTelemetry`

- [ ] **Step 1: Write comprehensive unit tests in `tests/test_agy_cli_driver.py`**
  - Test binary resolution (`cli_path`, fallback to `agy.real`, error if not found or not executable).
  - Test argument construction (`--model`, `--output-format json`, `--dangerously-skip-permissions`, `--print`, `--conversation`).
  - Test telemetry parsing from structured JSON (`conversation_id`, tokens, cost, duration).
  - Test failure parsing (non-zero exit code, bad JSON, timeout).
  - Test container bridge script creation (`./run-in-container` with permissions `0o755`).

- [ ] **Step 2: Run test suite to verify tests fail**
  - Run: `uv run pytest tests/test_agy_cli_driver.py -v`
  - Expected: FAIL with import or module not found.

- [ ] **Step 3: Implement `lab/engine/drivers/agy_cli.py` and export in `lab/engine/drivers/__init__.py`**
  - Write `AgyCliDriver` and `AgyCliDriverError`.
  - Include pricing constants for Gemini 3.8 Flash.
  - Implement container execution bridge writing `./run-in-container` and formatting steering prompt.

- [ ] **Step 4: Run test suite to verify tests pass**
  - Run: `uv run pytest tests/test_agy_cli_driver.py -v`
  - Expected: PASS.

- [ ] **Step 5: Commit**
  - `git add lab/engine/drivers/agy_cli.py lab/engine/drivers/__init__.py tests/test_agy_cli_driver.py`
  - `git commit -m "feat(driver): implement AgyCliDriver with container execution bridge"`

---

### Task 2: Verify Baseline and System Integration

- **Depends on:** Task 1

**Files:**
- Existing test suite

- [ ] **Step 1: Run full verification suite**
  - Run `uv run ruff check lab tests`
  - Run `uv run pyright lab tests`
  - Run `uv run pytest -q`
  - Expected: All tests pass with 0 errors, 0 warnings.

- [ ] **Step 2: Commit any cleanups**
  - If any lint or typing fixes were needed, commit atomically.

---

### Task 3: Execute Live Single-Task Smoke Run

- **Depends on:** Task 2

- [ ] **Step 1: Execute single task using `AblationRunner` with `AgyCliDriver`**
  - Target task: `fastapi-deprecation-response-headers`
  - Arm: `vanilla`
  - Verify container spin-up, agent interaction, patch collection, and grading.
