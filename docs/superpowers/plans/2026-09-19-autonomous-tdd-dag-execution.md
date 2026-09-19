# Autonomous TDD DAG Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Choose an execution mode:
> 1. `superpowers:subagent-driven-development` (recommended for multi-agent reviews, backed by `SKILL.state` / `.agent-state/state.json`)
> 2. `agent-rules:stateful-execution` (SKILL.state) (recommended for deterministic single-agent linear execution)
> 3. `superpowers:executing-plans` (batch execution with manual checkpoints)
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement autonomous 2-node TDD DAG execution in `superstate-eval`'s daemon adapter to eliminate hand-authored gate fixture reliance and evaluate multi-milestone DAG performance on the 3-task Canary slice with zero prompt engineering.

**Architecture:** Extend `SuperstateDaemonAdapter` to support `tdd_dag: bool`. When active, `_init_daemon_state` dynamically synthesizes a 2-node dependency graph: Node 1 authors the acceptance test in `tests/test_task_spec.py` (gate: test exists and compiles), and Node 2 implements the codebase fix (gate: `pytest tests/test_task_spec.py` exits 0, `depends_on: ["tdd-acceptance-test"]`). State is initialized via `--milestones` / MCP `superstate_handoff(milestones=...)`.

**Tech Stack:** Python 3.12, pytest, ruff, superstate (Rust CLI / MCP stdio JSON-RPC).

## Global Constraints
- Run all commands via `.venv/bin/python`, never bare `python3`.
- Pass all unit tests in `tests/test_superstate_daemon_adapter.py` and input parity in `tests/test_arm_input_parity.py`.
- Zero prompt engineering: do not introduce prompt persuasion, cajoling, or behavioral contracts to manage agents.
- Atomic conventional commits with `--no-gpg-sign`.

---

### Task 1: Add `tdd_dag` Configuration and 2-Node DAG Construction in `SuperstateDaemonAdapter`

- **Depends on:** none

**Files:**
- Modify: `lab/engine/adapters/superstate_daemon.py`
- Modify: `tests/test_superstate_daemon_adapter.py`

**Interfaces:**
- Consumes: `SuperstateMcpClient.superstate_handoff(milestones=...)`, `MilestoneSpec` schema.
- Produces: `SuperstateDaemonAdapter.tdd_dag: bool`, `SuperstateDaemonAdapter._build_tdd_milestones(task: TaskSpec) -> list[dict[str, Any]]`.

**Steps:**
- [ ] Write failing unit test in `tests/test_superstate_daemon_adapter.py` verifying `tdd_dag=True` constructs a 2-node milestone array with correct `id`, `depends_on`, `files`, and `verify_cmd`.
- [ ] Run `.venv/bin/python -m pytest tests/test_superstate_daemon_adapter.py -k tdd_dag` and verify failure.
- [ ] Add `tdd_dag: bool = False` to `SuperstateDaemonAdapter.__init__`.
- [ ] Implement `_build_tdd_milestones(self, task: TaskSpec) -> list[dict[str, Any]]` in `SuperstateDaemonAdapter`.
- [ ] In `_init_daemon_state`, if `self.tdd_dag` is enabled, pass `milestones=self._build_tdd_milestones(task)` to `client.superstate_handoff` (and `--milestones` JSON to CLI fallback).
- [ ] Run `.venv/bin/python -m pytest tests/test_superstate_daemon_adapter.py` and verify all tests pass.
- [ ] Run `.venv/bin/ruff check lab tests` to verify lint cleanliness.
- [ ] Commit with message `feat(eval): add 2-node TDD DAG milestone construction to daemon adapter`.

---

### Task 2: Register `superstate_daemon_dag` Arm and Verify Parity

- **Depends on:** Task 1

**Files:**
- Modify: `lab/engine/runner.py`
- Modify: `tests/test_arm_input_parity.py`

**Interfaces:**
- Consumes: `SuperstateDaemonAdapter(tdd_dag=True, auto_rollback=True, advisory_review=True, name="superstate_daemon_dag")`.
- Produces: Runner arm resolution for `"superstate_daemon_dag"`.

**Steps:**
- [ ] In `lab/engine/runner.py`, add arm alias `"superstate_daemon_dag"` resolving to `SuperstateDaemonAdapter(tdd_dag=True, auto_rollback=True, advisory_review=True, name="superstate_daemon_dag")`.
- [ ] In `tests/test_arm_input_parity.py`, ensure `"superstate_daemon_dag"` is included in arm parity tests.
- [ ] Run `.venv/bin/python -m pytest tests/test_arm_input_parity.py` and verify all tests pass.
- [ ] Run `.venv/bin/ruff check lab tests`.
- [ ] Commit with message `feat(eval): register superstate_daemon_dag arm with input parity enforcement`.

---

### Task 3: Register and Execute EXP-064 Canary Benchmark

- **Depends on:** Task 2

**Files:**
- Modify: `EXPERIMENTS.md`
- Create: `scripts/run_exp064_canary.sh`
- Create: `results/canary_dag_tdd_v_mcp_exp064.json`

**Interfaces:**
- Consumes: `scripts/paired_run.py`, Canary task set (`build-cython-ext`, `chess-best-move`, `httpx-multipart-response-parsing`).
- Produces: `results/canary_dag_tdd_v_mcp_exp064.json`, updated `EXPERIMENTS.md` entry.

**Steps:**
- [ ] Register row for EXP-064 in `EXPERIMENTS.md` as `PLANNED`.
- [ ] Create `scripts/run_exp064_canary.sh` targeting the 3 canary tasks: `superstate_daemon_dag` vs `superstate_mcp`.
- [ ] Make executable (`chmod +x scripts/run_exp064_canary.sh`) and execute the canary run.
- [ ] Run `scripts/gate_precision.py` and `scripts/experiments.py check` on the result.
- [ ] Update `EXPERIMENTS.md` with final metrics and mark status `STANDS`.
- [ ] Commit results and script with message `feat(exp): evaluate autonomous TDD DAG execution on canary slice (EXP-064)`.
