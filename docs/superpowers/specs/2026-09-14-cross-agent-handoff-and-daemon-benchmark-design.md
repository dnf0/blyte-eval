# Design Specification: Cross-Agent Relay & Autonomous Detached Daemon Evaluation

- **Author**: Antigravity & Dan Fisher
- **Date**: 2026-09-14
- **Status**: Approved
- **Target Repository**: `superstate-eval`

---

## 1. Overview & Objective

Superstate recently merged native cross-agent handoff protocols (`superstate state handoff`, `.agent-state/handoff.md`), headless driver presets (`claude`, `agy`), and autonomous background daemon runners (`superstate state daemon --detach`).

The objective of this design is to establish a rigorous, empirical benchmark evaluating the real-world performance, solve rate, latency, token consumption, and cost-of-ownership of these new capabilities against single-agent baselines on representative Frontier Software Engineering tasks.

### Evaluation Arms Under Test
1. **Arm 1: Solo Baseline (`superstate_solo`)**
   - Single agent (`agy` or `claude`) using Superstate's deterministic CLI state engine (`SuperstateAdapter`).
2. **Arm 2: Cross-Agent Relay (`superstate_relay`)**
   - 2-stage multi-agent collaboration:
     - **Stage 1 (Claude Code)**: Explores task requirements, authors targeted reproduction test suite, initializes Superstate state, and executes `superstate state handoff --from claude --to agy --verify-cmd <cmd>`.
     - **Stage 2 (Antigravity `agy`)**: Resumes from `.agent-state/handoff.md` via `superstate state resume`, implements the solution, and advances state via `superstate state next --verify-cmd <cmd> --verify-git-clean`.
3. **Arm 3: Autonomous Detached Daemon (`superstate_daemon`)**
   - Headless background runner launched via `superstate state daemon --driver agy --detach` (or `--driver claude`).
   - Executes autonomous milestone steps in an isolated worktree until task completion or retry exhaustion.

---

## 2. Benchmark Task Suite: 5-Task Representative Pilot

A representative 5-task pilot suite chosen from the Tier-1 Frontier Software Engineering benchmark set:

| # | Task ID | Domain / Language | Core Challenge | Held-Out Grader |
| :- | :--- | :--- | :--- | :--- |
| 1 | `fastapi-deprecation-response-headers` | Python / Web Framework | Inject HTTP deprecation headers without altering response body contracts | `pytest` checking headers & status |
| 2 | `build-cython-ext` | C / Python FFI | Repair Cython extension compilation flags and C header inclusions | Python script invoking compiled C functions |
| 3 | `sqlite-db-truncate` | Database / Storage Systems | Atomic table truncation and schema state maintenance | SQLite transaction & integrity assertions |
| 4 | `db-wal-recovery` | Binary / Systems Recovery | Parse binary WAL log frames and recover crash state | Algorithmic state hash verification |
| 5 | `openssl-selfsigned-cert` | Cryptography / CLI Tooling | Generate X.509 cert with Subject Alternative Names (SAN) | OpenSSL certificate parser & validity checks |

---

## 3. Architecture & Adapter Specifications

### 3.1 `SuperstateRelayAdapter` (`lab/engine/adapters/superstate_relay.py`)
- **Inheritance:** Extends `AgentAdapter` (`lab/engine/adapters/base.py`).
- **Drivers:**
  - Stage 1: `ClaudeCliDriver` (`claude`).
  - Stage 2: `AgyCliDriver` (`agy`).
- **Execution Flow:**
  1. `strip_preexisting_guidance(workspace_path)`.
  2. Setup container workspace with Docker mount.
  3. **Stage 1 (Claude):**
     - Prompt includes task spec, codebase layout, and the explicit command to author reproduction tests, run `superstate state init`, record ledger notes, and issue `superstate state handoff --from claude --to agy --verify-cmd <cmd>`.
     - Output is parsed for duration, tokens, and cost.
     - Fallback: If Claude exits without writing `.agent-state/handoff.md`, the adapter automatically synthesizes the handoff package via host `superstate state handoff`.
  4. **Stage 2 (Agy):**
     - Prompt instructs Agy to inspect `.agent-state/handoff.md`, run `superstate state resume`, implement the solution, and execute `superstate state next --verify-cmd <cmd> --verify-git-clean`.
     - If verification fails, adapter injects failure output and permits up to 2 retry turns.
  5. Runs blind held-out verification (`HeldOutVerifier`).
  6. Aggregates combined telemetry (sum of Claude + Agy tokens and cost).

### 3.2 `SuperstateDaemonAdapter` (`lab/engine/adapters/superstate_daemon.py`)
- **Inheritance:** Extends `AgentAdapter` (`lab/engine/adapters/base.py`).
- **Execution Flow:**
  1. Formulates initial state file `.agent-state/state.json` via `superstate state init --goal <goal> --verify-cmd <cmd>`.
  2. Spawns `superstate state daemon --state .agent-state/state.json --driver <driver> --detach`.
  3. Resolves daemon paths using `superstate_core::daemon::daemon_paths_for_state`.
  4. Polls the PID in `.agent-state/daemons/<slug>.pid` every 2 seconds until process exit or task budget timeout.
  5. On timeout: issues `cmd_cancel` / kills the daemon process tree.
  6. Inspects `.agent-state/logs/<slug>.log` and `state.json` to verify completion and capture retry counts.
  7. Runs blind held-out verification (`HeldOutVerifier`).

---

## 4. Quantitative Metrics & Reporting

Results will be aggregated and formatted into:
- **Solve Rate (%):** Tasks passing blind held-out verification divided by total tasks.
- **Wall-Clock Latency (s):** Mean and median time-to-solve per task.
- **Turn Efficiency:** Total agent turns consumed per task.
- **Combined Token Volume:** Total input + output tokens across all models.
- **TCO (USD):** Total spend calculated using official model API rates:
  - Gemini 3.8 Flash High: $0.15/1M input, $0.60/1M output.
  - Claude 3.5 Sonnet: $3.00/1M input, $15.00/1M output (or Claude 3.5 Haiku: $0.80/$4.00).
- **Marginal Cost per Win ($/win):** Total cost divided by solve rate.
- **Handoff Fidelity:** Audit log verifying zero manual intervention was required between Claude and Agy.

---

## 5. Security & Isolation Invariants

1. **Docker Resource Caps:** Containers limited to 2.5 CPUs and 4GB RAM.
2. **Answer Key Protection:** `AnswerKeyGuard` active during all turns to prevent inspection of ground truth solutions.
3. **No Network Leakage:** For offline tasks, Docker network mode is set to `none`.
4. **Hermetic State Cleanup:** Each task run operates in an isolated temporary directory under `/tmp/superstate_eval_runs/<timestamp>/<task_id>/<arm>`.
