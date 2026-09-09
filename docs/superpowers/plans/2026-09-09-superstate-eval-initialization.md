# superstate-eval Local Assessment Repository Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Choose an execution mode:
> 1. `superpowers:subagent-driven-development` (recommended for multi-agent reviews, backed by `SKILL.state` / `.agent-state/state.json`)
> 2. `agent-rules:stateful-execution` (SKILL.state) (recommended for deterministic single-agent linear execution)
> 3. `superpowers:executing-plans` (batch execution with manual checkpoints)
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a clean, local-only assessment and differential testing lab in `/Users/danielfisher/repos/superstate-eval` to assess whether `superstate` and the state-engine architecture provide measurable utility over unguided and skill-guided baselines, prove functional parity between Rust and Python state engines, and permanently eliminate Docker disk saturation.

**Architecture:** A standalone Python 3.12 project managed by `uv` containing:
1. `lab.sandbox.docker_manager`: Guaranteed container teardown, volume pruning, and pre-flight host disk space watchdog.
2. `lab.engine.budget_policy`: Progress-earned lease extension tracking and transparent cost/token/wall-clock telemetry.
3. `lab.parity`: Zero-LLM-cost differential test suite running `agent-rules state` and `superstate state` side-by-side on plan fixtures.
4. `lab.engine.runner`: 3-way ablation benchmark runner (Vanilla vs Superpowers vs Superstate).

**Tech Stack:** Python 3.12, `uv`, `pytest`, `deepdiff`, `docker`, `rich`, `pydantic`.

---

## Tasks

- [ ] **Task 1: Repository Scaffolding & Tooling Setup**
  - **Files:** `pyproject.toml`, `README.md`, `.gitignore`, `Makefile`
  - **Action:**
    - Initialize local git repo in `/Users/danielfisher/repos/superstate-eval`.
    - Create `pyproject.toml` with `pytest`, `deepdiff`, `docker`, `rich`, `pydantic`.
    - Create `.gitignore` ignoring `.agent-state/`, `.venv/`, `.pytest_cache/`, `runs/`.
    - Setup `uv venv` and install dependencies.
    - Add `Makefile` with targets: `test`, `parity`, `clean-docker`.

- [ ] **Task 2: Docker Lifecycle & Disk Space Watchdog**
  - **Files:** `lab/sandbox/docker_manager.py`, `tests/test_docker_manager.py`
  - **Action:**
    - Implement `DockerManager` with context manager for safe container lifecycles.
    - Implement automatic `docker rm -f` on exit (even on exception/signal).
    - Implement `prune_ephemeral_resources()` (pruning anonymous volumes and dangling images).
    - Implement `check_disk_space_or_prune(min_free_gb=20.0, emergency_halt_gb=10.0)`.
    - Write unit tests using mocked docker and disk usage.

- [ ] **Task 3: Progress-Earned Budget Policy & Accounting Telemetry**
  - **Files:** `lab/engine/budget_policy.py`, `tests/test_budget_policy.py`
  - **Action:**
    - Implement `BudgetPolicy` supporting task declared opening allowance (`agent_timeout_sec`).
    - Implement milestone progress lease extensions (`+1200s` per verified milestone advance).
    - Implement `RunTelemetry` dataclass recording `wall_clock_sec`, `cost_usd`, `input_tokens`, `milestones_completed`, `lease_extensions_earned_sec`, `total_granted_budget_sec`.
    - Write unit tests verifying lease calculations and telemetry serialization.

- [ ] **Task 4: Zero-Cost Differential Parity Harness**
  - **Files:** `lab/parity/test_differential.py`, `lab/parity/fixtures/`
  - **Action:**
    - Create fixtures of markdown plans: simple linear plan, DAG dependency plan, code-fence edge case plan.
    - Implement differential runner executing both `agent-rules state` and `superstate state` subcommands (`init`, `next`, `note`, `status`, `prompt`).
    - Assert DeepDiff on resulting `.agent-state/state.json` produces zero discrepancies.
    - Assert exit code and error message parity on failing verification gates (`--verify-cmd`).

- [ ] **Task 5: Controlled Utility & Ablation Benchmark Runner**
  - **Files:** `lab/engine/runner.py`, `lab/engine/reporter.py`, `tests/test_ablation_runner.py`
  - **Action:**
    - Implement 3-arm execution harness: Arm 1 (Vanilla), Arm 2 (Superpowers), Arm 3 (Superstate).
    - Wire `DockerManager` and `BudgetPolicy` into task execution loop.
    - Implement markdown/console cost-efficiency report (Pass Rate vs Cost vs Wall-Clock).
    - Run smoke test on a local mock task.

---

## Verification & Completion Gates

1. `uv run pytest -q` passes 100% in `/Users/danielfisher/repos/superstate-eval`.
2. `make parity` runs the differential suite and proves `superstate` and `agent-rules` agree on state transitions.
3. Disk space watchdog successfully reports free space and confirms Docker pruning hooks work.
