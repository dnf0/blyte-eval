# Evaluation Philosophy & Autonomous TDD Benchmark Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Choose an execution mode:
> 1. `superpowers:subagent-driven-development` (recommended for multi-agent reviews, backed by `SKILL.state` / `.agent-state/state.json`)
> 2. `agent-rules:stateful-execution` (SKILL.state) (recommended for deterministic single-agent linear execution)
> 3. `superpowers:executing-plans` (batch execution with manual checkpoints)
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Codify the non-cheating evaluation philosophy across `AGENTS.md`, `README.md`, and `docs/EVALUATION-PHILOSOPHY.md`, implement 2-node Autonomous TDD DAG milestone construction in `SuperstateDaemonAdapter`, register `superstate_daemon_dag`, and validate end-to-end execution on the Canary benchmark slice (EXP-065).

**Architecture:** 
1. Permanently codify the evaluation philosophy (held-out sealed grader integrity, deprecation of synthetic `GATE_FIXTURES`, and mechanical exit-code verification).
2. Extend `SuperstateDaemonAdapter` with `tdd_dag: bool`. When active, `_init_daemon_state` synthesizes a 2-node dependency graph: Node 1 authors the acceptance test in `tests/test_reproduce_issue.py` (gate: test exists, compiles, and asserts RED), and Node 2 implements the codebase fix (gate: `pytest tests/test_reproduce_issue.py && pytest tests/` exits 0, `depends_on: ["tdd-reproduction-test"]`).
3. Leverage existing AST Test Impact Slicing (`--impact-slicing`), Tool Output Shunting, and Scoped Git Rollback during Milestone 2 execution.

**Tech Stack:** Python 3.12, pytest, ruff, pyright, superstate (Rust CLI / MCP stdio JSON-RPC).

## Global Constraints
- Run all commands via `.venv/bin/python`, never bare `python3`.
- Strict input parity: verify with `tests/test_arm_input_parity.py`.
- No answer-key leaking: never expose `/tests/` maintainer test suites to the agent prior to grading.
- Zero prompt engineering: no behavioral persuasion or cajoling prompt contracts; execution guided mechanically by milestones, exit codes, and git rollbacks.
- Atomic conventional commits with `--no-gpg-sign`.

---

### Task 1: Author and Publish `docs/EVALUATION-PHILOSOPHY.md`

- **Depends on:** none

**Files:**
- Create: `docs/EVALUATION-PHILOSOPHY.md`

**Interfaces:**
- Consumes: Design spec `docs/superpowers/specs/2026-09-20-evaluation-philosophy-and-autonomous-tdd-design.md`, `FINDINGS.md`.
- Produces: Permanent architectural reference for evaluation principles, gate precision mathematics, and benchmark integrity.

- [ ] **Step 1: Write `docs/EVALUATION-PHILOSOPHY.md`**

Write the definitive manifesto containing:
1. The Core Problem: The collapse of synthetic gate fixtures (17% DataCurve precision) and why `httpx` failed on premature exit 0.
2. The Anti-Cheating Invariant: Why handing over reproduction tests up front is cheating in SWE benchmarks.
3. The Single Unified Track: Real repository engineering through Autonomous TDD (Milestone 1 RED $\to$ Milestone 2 GREEN).
4. Mechanical Control Plane vs. Conversational Prompt Vibes: How DAG milestones, process exit codes, AST test impact slicing, output shunting, and scoped rollback are measured.
5. The 5 Evaluation Metrics: Feedback Velocity, Token Efficiency, Autonomous Convergence, Fault Isolation/Rollback, and Held-Out Pass Rate.

- [ ] **Step 2: Commit document**

```bash
git add docs/EVALUATION-PHILOSOPHY.md
git commit --no-gpg-sign -m "docs: publish evaluation philosophy and benchmark integrity manifesto"
```

---

### Task 2: Codify Evaluation Philosophy and Invariants in `AGENTS.md` and `README.md`

- **Depends on:** Task 1

**Files:**
- Modify: `AGENTS.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: Core principles from `docs/EVALUATION-PHILOSOPHY.md`.
- Produces: Updated operational guidance for human researchers and AI agents working in `superstate-eval`.

- [ ] **Step 1: Update `AGENTS.md`**
Add section `## Evaluation Philosophy: Autonomous TDD vs. Answer-Key Cheating`:
- Ban synthetic `GATE_FIXTURES`.
- Forbid pre-seeding held-out reproduction tests.
- Define the Autonomous TDD 2-node DAG as the canonical mechanism for issue resolution.
- Warn against vacuous Turn-0 gates.

- [ ] **Step 2: Update `README.md`**
- Update architectural workflow diagram to display the 2-Node TDD State DAG.
- Update "What is measured" section to explain mechanical control plane verification vs unmanaged baseline execution.

- [ ] **Step 3: Commit updates**

```bash
git add AGENTS.md README.md
git commit --no-gpg-sign -m "docs: codify evaluation philosophy and autonomous TDD rules in AGENTS.md and README.md"
```

---

### Task 3: Implement 2-Node Autonomous TDD DAG Construction in `SuperstateDaemonAdapter`

- **Depends on:** none

**Files:**
- Modify: `lab/engine/adapters/superstate_daemon.py`
- Modify: `tests/test_superstate_daemon_adapter.py`

**Interfaces:**
- Consumes: `TaskSpec`, `SuperstateMcpClient.superstate_handoff(milestones=...)`.
- Produces: `SuperstateDaemonAdapter.tdd_dag: bool`, `SuperstateDaemonAdapter._build_tdd_milestones(task: TaskSpec) -> list[dict[str, Any]]`.

- [ ] **Step 1: Write failing unit test in `tests/test_superstate_daemon_adapter.py`**

```python
def test_daemon_adapter_constructs_tdd_dag_milestones():
    adapter = SuperstateDaemonAdapter(tdd_dag=True)
    task = TaskSpec(
        id="test-task",
        name="test-task",
        instruction="Fix bug in parser",
        docker_image="python:3.12",
    )
    milestones = adapter._build_tdd_milestones(task)
    assert len(milestones) == 2
    assert milestones[0]["id"] == "tdd-reproduction-test"
    assert milestones[0]["depends_on"] == []
    assert "tests/test_reproduce_issue.py" in milestones[0]["files"]
    assert milestones[1]["id"] == "fix-implementation"
    assert milestones[1]["depends_on"] == ["tdd-reproduction-test"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_superstate_daemon_adapter.py -k test_daemon_adapter_constructs_tdd_dag_milestones`
Expected: FAIL with AttributeError: `tdd_dag` or `_build_tdd_milestones` not found.

- [ ] **Step 3: Implement `tdd_dag` and `_build_tdd_milestones` in `SuperstateDaemonAdapter`**
- Add `tdd_dag: bool = False` to `SuperstateDaemonAdapter.__init__`.
- Expose `tdd_dag` in `get_provenance()`.
- Implement `_build_tdd_milestones(self, task: TaskSpec) -> list[dict[str, Any]]`:
  - Milestone 1: ID `tdd-reproduction-test`, title `Author reproduction test in tests/test_reproduce_issue.py`, files `["tests/test_reproduce_issue.py"]`, verify_cmd: `test -s tests/test_reproduce_issue.py && ./run-in-container python3 -m py_compile tests/test_reproduce_issue.py`.
  - Milestone 2: ID `fix-implementation`, title `Implement fix until reproduction test and regression suite pass`, depends_on `["tdd-reproduction-test"]`, files `[]`, verify_cmd: `./run-in-container pytest tests/test_reproduce_issue.py && ./run-in-container pytest tests/`.
- In `_init_daemon_state`, when `self.tdd_dag` is True, pass `milestones=self._build_tdd_milestones(task)` to `client.superstate_handoff`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_superstate_daemon_adapter.py`
Expected: PASS (all 33+ tests pass).

- [ ] **Step 5: Run linter and type checker**

Run: `.venv/bin/ruff check lab/engine/adapters/superstate_daemon.py tests/test_superstate_daemon_adapter.py`
Run: `.venv/bin/pyright lab/engine/adapters/superstate_daemon.py`
Expected: 0 errors.

- [ ] **Step 6: Commit changes**

```bash
git add lab/engine/adapters/superstate_daemon.py tests/test_superstate_daemon_adapter.py
git commit --no-gpg-sign -m "feat(eval): add 2-node autonomous TDD DAG milestone construction to daemon adapter"
```

---

### Task 4: Register `superstate_daemon_dag` Arm and Enforce Input Parity

- **Depends on:** Task 3

**Files:**
- Modify: `lab/engine/runner.py`
- Modify: `tests/test_arm_input_parity.py`

**Interfaces:**
- Consumes: `SuperstateDaemonAdapter(tdd_dag=True, impact_slicing=True, auto_rollback=True, advisory_review=True, name="superstate_daemon_dag")`.
- Produces: Runner arm mapping for `"superstate_daemon_dag"`.

- [ ] **Step 1: Register arm in `lab/engine/runner.py`**
Add arm alias `"superstate_daemon_dag"` configured with:
```python
SuperstateDaemonAdapter(
    tdd_dag=True,
    impact_slicing=True,
    auto_rollback=True,
    advisory_review=True,
    name="superstate_daemon_dag",
)
```

- [ ] **Step 2: Update `tests/test_arm_input_parity.py`**
Ensure `"superstate_daemon_dag"` is included in arm parity suites (verifying model, `--output-format json`, container guidance, and `--print-timeout`).

- [ ] **Step 3: Run parity and runner tests**

Run: `.venv/bin/python -m pytest tests/test_arm_input_parity.py`
Expected: PASS (100% parity verified).

- [ ] **Step 4: Commit changes**

```bash
git add lab/engine/runner.py tests/test_arm_input_parity.py
git commit --no-gpg-sign -m "feat(eval): register superstate_daemon_dag arm with input parity enforcement"
```

---

### Task 5: Register and Execute Canary Benchmark (EXP-065)

- **Depends on:** Task 2, Task 4

**Files:**
- Modify: `EXPERIMENTS.md`
- Create: `scripts/run_exp065_canary.sh`
- Create: `results/canary_dag_tdd_v_mcp_exp065.json`

**Interfaces:**
- Consumes: `scripts/paired_run.py`, Canary slice (`build-cython-ext`, `chess-best-move`, `httpx-multipart-response-parsing`).
- Produces: `results/canary_dag_tdd_v_mcp_exp065.json`, verified `EXPERIMENTS.md` entry.

- [ ] **Step 1: Register EXP-065 in `EXPERIMENTS.md` as PLANNED**
Register the experiment row prior to execution:
```markdown
| EXP-065 | 2026-09-20 | Autonomous TDD DAG vs MCP Canary | superstate_daemon_dag, superstate_mcp | --impact-slicing --tdd-dag | results/canary_dag_tdd_v_mcp_exp065.json | PLANNED |
```

- [ ] **Step 2: Create execution script `scripts/run_exp065_canary.sh`**

```bash
#!/bin/bash
set -euo pipefail
TASKS="build-cython-ext chess-best-move httpx-multipart-response-parsing"
.venv/bin/python scripts/paired_run.py \
  --tasks $TASKS \
  --arms superstate_daemon_dag superstate_mcp \
  --driver agy \
  --model gemini-3.8-flash-high \
  --concurrency 2 \
  --output results/canary_dag_tdd_v_mcp_exp065.json
```

- [ ] **Step 3: Execute Canary run and verify results**
Run: `chmod +x scripts/run_exp065_canary.sh && ./scripts/run_exp065_canary.sh`
- Run `scripts/experiments.py check` to verify row alignment.
- Run `scripts/gate_precision.py` on telemetry.
- Update `EXPERIMENTS.md` status to `STANDS`.

- [ ] **Step 4: Commit experiment results**

```bash
git add EXPERIMENTS.md scripts/run_exp065_canary.sh results/canary_dag_tdd_v_mcp_exp065.json
git commit --no-gpg-sign -m "feat(exp): evaluate autonomous TDD DAG execution on canary slice (EXP-065)"
```
