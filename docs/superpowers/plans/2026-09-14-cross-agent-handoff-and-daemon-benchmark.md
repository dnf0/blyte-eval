# Cross-Agent Relay & Autonomous Detached Daemon Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Choose an execution mode:
> 1. `superpowers:subagent-driven-development` (recommended for multi-agent reviews, backed by `SKILL.state` / `.agent-state/state.json`)
> 2. `agent-rules:stateful-execution` (SKILL.state) (recommended for deterministic single-agent linear execution)
> 3. `superpowers:executing-plans` (batch execution with manual checkpoints)
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, test, and execute the benchmark evaluation for Cross-Agent Relay (`superstate_relay`) and Autonomous Detached Daemon (`superstate_daemon`) against the Solo Baseline (`superstate_solo`) on the 5-task Frontier Software Engineering pilot suite.

**Architecture:** Implement two first-class adapters (`SuperstateRelayAdapter` and `SuperstateDaemonAdapter`) extending `AgentAdapter`, wire them into `AblationRunner`, add unit and mock integration test suites, and provide an automated pilot execution script with full reporting.

**Tech Stack:** Python 3.12, Pytest, Docker, Superstate CLI/Core, Claude CLI, Agy CLI.

## Global Constraints
- Target workspace: `/Users/danielfisher/repos/superstate-eval` on branch `main` (isolated via worktree for execution).
- Python 3.12 type hints and dataclasses throughout.
- Follow strict TDD: failing test first, minimal implementation, passing test, atomic conventional commit.
- Zero ruff lint errors (`uv run ruff check`).
- Zero pyright type errors (`uv run pyright`).
- Maintain 100% backward compatibility for existing arms (`vanilla`, `superpowers`, `superstate`, `superstate_agent_mcp`).

---

### Task 1: Implement `SuperstateRelayAdapter`

- **Depends on:** none

**Files:**
- Create: `lab/engine/adapters/superstate_relay.py`
- Test: `tests/test_superstate_relay_adapter.py`
- Modify: `lab/engine/adapters/__init__.py`

**Interfaces:**
- Consumes:
  - `TaskSpec` from `lab.benchmarks.task_loader`
  - `AgentAdapter`, `TaskRunResult`, `DriverTelemetry` from `lab.engine.adapters.base`
  - `ClaudeCliDriver` from `lab.engine.drivers.claude_cli`
  - `AgyCliDriver` from `lab.engine.drivers.agy_cli`
- Produces:
  - `class SuperstateRelayAdapter(AgentAdapter)`
  - `run_task(self, task: TaskSpec, workspace_path: Path, driver: Any, budget_sec: float, budget_hook: Optional[BudgetHook] = None) -> TaskRunResult`

- [ ] **Step 1: Write failing unit test for `SuperstateRelayAdapter`**

Create `tests/test_superstate_relay_adapter.py`:
```python
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.superstate_relay import SuperstateRelayAdapter
from lab.engine.adapters.base import DriverTelemetry


def test_relay_adapter_initialization():
    adapter = SuperstateRelayAdapter()
    assert adapter.name == "superstate_relay"
    assert adapter.max_retries == 2


def test_relay_adapter_run_task_mocked(tmp_path: Path):
    adapter = SuperstateRelayAdapter()
    task = TaskSpec(
        task_id="test-task",
        task_name="Test Task",
        instruction="Fix the bug",
        repo_dir="repo",
        held_out_verifier="true",
        eval_image="test:latest",
    )

    mock_claude = MagicMock()
    mock_claude.run_turn.return_value = DriverTelemetry(
        success=True, raw_response="Done stage 1", duration_seconds=10.0, input_tokens=500, output_tokens=100, cost_usd=0.01
    )
    mock_agy = MagicMock()
    mock_agy.run_turn.return_value = DriverTelemetry(
        success=True, raw_response="Done stage 2", duration_seconds=15.0, input_tokens=800, output_tokens=150, cost_usd=0.005
    )

    # Pre-create handoff.md so stage 1 verification passes
    state_dir = tmp_path / ".agent-state"
    state_dir.mkdir(parents=True, exist_ok=True)
    handoff_file = state_dir / "handoff.md"
    handoff_file.write_text("# Handoff\n- Active Task: task-1\n", encoding="utf-8")

    with patch.object(adapter, "_run_gate_command", return_value=(True, 0, "pass")):
        result = adapter.run_task(
            task=task,
            workspace_path=tmp_path,
            driver=mock_agy,
            budget_sec=120.0,
            claude_driver=mock_claude,
        )

    assert result.success is True
    assert result.task_id == "test-task"
    assert result.harness_name == "superstate_relay"
    assert result.total_input_tokens == 1300
    assert result.total_output_tokens == 250
    assert result.total_cost_usd == pytest.approx(0.015)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_superstate_relay_adapter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lab.engine.adapters.superstate_relay'`

- [ ] **Step 3: Implement `SuperstateRelayAdapter`**

Create `lab/engine/adapters/superstate_relay.py` implementing the two-stage execution loop:
- Stage 1: Invoke Claude driver with task instruction, requesting reproduction test authoring and `superstate state handoff --from claude --to agy`.
- Stage 2: Resume with Agy driver, inspect `.agent-state/handoff.md`, run implementation, verify gate.
- Track combined telemetry.
Export in `lab/engine/adapters/__init__.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_superstate_relay_adapter.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add lab/engine/adapters/superstate_relay.py lab/engine/adapters/__init__.py tests/test_superstate_relay_adapter.py
git commit -m "feat(adapter): implement SuperstateRelayAdapter for cross-agent collaboration"
```

---

### Task 2: Implement `SuperstateDaemonAdapter`

- **Depends on:** none

**Files:**
- Create: `lab/engine/adapters/superstate_daemon.py`
- Test: `tests/test_superstate_daemon_adapter.py`
- Modify: `lab/engine/adapters/__init__.py`

**Interfaces:**
- Consumes:
  - `TaskSpec` from `lab.benchmarks.task_loader`
  - `AgentAdapter`, `TaskRunResult` from `lab.engine.adapters.base`
- Produces:
  - `class SuperstateDaemonAdapter(AgentAdapter)`
  - `run_task(self, task: TaskSpec, workspace_path: Path, driver: Any, budget_sec: float, budget_hook: Optional[BudgetHook] = None) -> TaskRunResult`

- [ ] **Step 1: Write failing unit test for `SuperstateDaemonAdapter`**

Create `tests/test_superstate_daemon_adapter.py`:
```python
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.superstate_daemon import SuperstateDaemonAdapter


def test_daemon_adapter_initialization():
    adapter = SuperstateDaemonAdapter(driver_preset="agy")
    assert adapter.name == "superstate_daemon"
    assert adapter.driver_preset == "agy"


def test_daemon_adapter_run_mocked(tmp_path: Path):
    adapter = SuperstateDaemonAdapter(driver_preset="agy", poll_interval_sec=0.01)
    task = TaskSpec(
        task_id="daemon-test",
        task_name="Daemon Test",
        instruction="Complete task autonomously",
        repo_dir="repo",
        held_out_verifier="true",
        eval_image="test:latest",
    )

    state_dir = tmp_path / ".agent-state"
    daemons_dir = state_dir / "daemons"
    daemons_dir.mkdir(parents=True, exist_ok=True)
    pid_file = daemons_dir / "default.pid"
    pid_file.write_text("999999\n", encoding="utf-8")

    state_file = state_dir / "state.json"
    state_file.write_text('{"status": "completed", "step": 1, "completed_tasks": [{"id": "task-1"}]}', encoding="utf-8")

    with patch("lab.engine.adapters.superstate_daemon.is_pid_alive", side_effect=[True, False]), \
         patch.object(adapter, "_init_daemon_state", return_value=True), \
         patch.object(adapter, "_spawn_daemon", return_value=True), \
         patch.object(adapter, "_run_gate_command", return_value=(True, 0, "pass")):
        result = adapter.run_task(
            task=task,
            workspace_path=tmp_path,
            driver=None,
            budget_sec=60.0,
        )

    assert result.success is True
    assert result.harness_name == "superstate_daemon"
    assert result.task_id == "daemon-test"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_superstate_daemon_adapter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lab.engine.adapters.superstate_daemon'`

- [ ] **Step 3: Implement `SuperstateDaemonAdapter`**

Create `lab/engine/adapters/superstate_daemon.py`:
- Initializes `.agent-state/state.json` with task goal and verification invariant.
- Launches `superstate state daemon --state .agent-state/state.json --driver <preset> --detach`.
- Polls PID file until completion or budget timeout.
- Extracts telemetry and step counts.
Export in `lab/engine/adapters/__init__.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_superstate_daemon_adapter.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add lab/engine/adapters/superstate_daemon.py lab/engine/adapters/__init__.py tests/test_superstate_daemon_adapter.py
git commit -m "feat(adapter): implement SuperstateDaemonAdapter for autonomous headless execution"
```

---

### Task 3: Wire Adapters into Runner and Add End-to-End Harness Tests

- **Depends on:** Task 1, Task 2

**Files:**
- Modify: `lab/engine/runner.py:100-135`
- Test: `tests/test_runner_relay_and_daemon.py`

**Interfaces:**
- Consumes:
  - `SuperstateRelayAdapter` from `lab.engine.adapters`
  - `SuperstateDaemonAdapter` from `lab.engine.adapters`
- Produces:
  - `AblationRunner._get_adapter` resolution for `superstate_relay`, `superstate_daemon`, and `superstate_solo`.

- [ ] **Step 1: Write failing runner test**

Create `tests/test_runner_relay_and_daemon.py`:
```python
import pytest
from lab.engine.runner import AblationRunner
from lab.engine.adapters.superstate_relay import SuperstateRelayAdapter
from lab.engine.adapters.superstate_daemon import SuperstateDaemonAdapter
from lab.engine.adapters.superstate import SuperstateAdapter


def test_runner_resolves_relay_and_daemon_arms():
    runner = AblationRunner(budget_policy=None)
    
    relay_adapter = runner._get_adapter("superstate_relay")
    assert isinstance(relay_adapter, SuperstateRelayAdapter)

    daemon_adapter = runner._get_adapter("superstate_daemon")
    assert isinstance(daemon_adapter, SuperstateDaemonAdapter)

    solo_adapter = runner._get_adapter("superstate_solo")
    assert isinstance(solo_adapter, SuperstateAdapter)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_runner_relay_and_daemon.py -v`
Expected: FAIL with `ValueError: Unknown evaluation arm: superstate_relay`

- [ ] **Step 3: Update `AblationRunner._get_adapter`**

Update `lab/engine/runner.py` to recognize:
- `"superstate_relay"`, `"relay"` -> `SuperstateRelayAdapter()`
- `"superstate_daemon"`, `"daemon"` -> `SuperstateDaemonAdapter()`
- `"superstate_solo"`, `"solo"` -> `SuperstateAdapter(engine=ENGINE_RUST, no_worktree=True, zero_turn_planning=True)`

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_runner_relay_and_daemon.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite & linters**

Run:
```bash
uv run ruff check lab tests
uv run pyright lab tests
uv run pytest -q
```
Expected: All checks pass with 0 errors.

- [ ] **Step 6: Commit**

```bash
git add lab/engine/runner.py tests/test_runner_relay_and_daemon.py
git commit -m "feat(runner): wire superstate_relay and superstate_daemon into AblationRunner"
```

---

### Task 4: Automated Pilot Script & 5-Task Benchmark Execution

- **Depends on:** Task 3

**Files:**
- Create: `scripts/launch_frontier_handoff_pilot.sh`
- Create: `results/frontier_handoff_pilot_5tasks.json` (runtime artifact)

- [ ] **Step 1: Create `scripts/launch_frontier_handoff_pilot.sh`**

Script configuring the 5 tasks:
- `fastapi-deprecation-response-headers`
- `build-cython-ext`
- `sqlite-db-truncate`
- `db-wal-recovery`
- `openssl-selfsigned-cert`
Running across arms: `--arms superstate_solo superstate_relay superstate_daemon`.
Writing to `results/frontier_handoff_pilot_5tasks.json`.

- [ ] **Step 2: Test script execution on a single smoke task**

Run smoke verification with `--tasks fastapi-deprecation-response-headers`.

- [ ] **Step 3: Execute full 5-task pilot suite**

Run `bash scripts/launch_frontier_handoff_pilot.sh`.
Monitor progress and record telemetry.

- [ ] **Step 4: Commit benchmark script and results report**

```bash
git add scripts/launch_frontier_handoff_pilot.sh results/frontier_handoff_pilot_5tasks.json
git commit -m "chore(eval): add pilot script and record 5-task handoff benchmark results"
```
