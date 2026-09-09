# Architecture Specification: Concurrent Evaluation Isolation & Universal Progress-Earned Budgeting

**Date:** 2026-09-09  
**Repository:** `superstate-eval`  
**Status:** Approved for Implementation  

---

## 1. Executive Summary & Goals

This specification formalizes the architecture for executing concurrent, strictly isolated evaluations in `superstate-eval` across three experimental arms:
- **Arm A (Vanilla):** Unguided model with bash and file tools.
- **Arm B (Superpowers):** Model guided by the Superpowers software engineering skills library.
- **Arm C (Superstate):** Model guided by the deterministic state engine (`superstate` binary) with milestone DAGs and verification gates.

### Core Objectives
1. **Dynamic Machine-Aware Concurrency Governor:** Automatically calculate safe worker concurrency from real-time host hardware specs (CPU cores, RAM, free disk space) to prevent host thrashing.
2. **Strict Docker Container Isolation:** Every single evaluation runs in its own pristine container with explicit CPU and memory quotas, isolated volume mounts, and guaranteed teardown.
3. **Universal Progress-Earned Budgeting:** Eliminate arbitrary flat time clamping. All arms start with the same configurable base timeout and earn additional runtime runway (`+1200s`) upon demonstrating verifiable progress.
4. **Arm-Agnostic Blind Extraction & Verification:** Symmetric, held-out grading based strictly on `/logs/verifier/reward.json` and `git diff` patch collection.

---

## 2. Dynamic Concurrency Governor

The `ConcurrencyGovernor` dynamically checks hardware specs on startup and prior to dispatching each task:

$$\text{max\_concurrency} = \min\left( \max\left(1, \left\lfloor\frac{\text{logical\_cpus}}{2.5}\right\rfloor\right), \max\left(1, \left\lfloor\frac{\text{usable\_ram\_gb}}{4.0}\right\rfloor\right), \max\left(1, \left\lfloor\frac{\text{free\_disk\_gb} - 20}{10.0}\right\rfloor\right) \right)$$

- **Host Specs Calibration (e.g. 12 CPUs, 24 GB RAM, 130 GB Free Disk):**
  - $\lfloor 12 / 2.5 \rfloor = 4$ workers
  - $\lfloor 24 / 4 \rfloor = 6$ workers
  - $\lfloor (130 - 20) / 10 \rfloor = 11$ workers
  - **Result:** Automatically limits concurrency to **4 parallel containers**, leaving 2 cores and 8 GB RAM headroom for the host OS.
- **User Override:** `--max-workers <N>` can manually clamp concurrency when running during active desktop use.

---

## 3. Strict Docker Sandbox Quotas & Volume Isolation

Every evaluation task executes in a unique, isolated Docker container:
- **Container Name:** `eval-{arm}-{task_id}-{run_id[:8]}`
- **CPU Quota:** `nano_cpus = int(2.5 * 1e9)` (prevents any single compiler or runaway loop from dominating host CPUs).
- **Memory Limit:** `mem_limit = "4g"` with swap disabled (prevents host OOM).
- **Mounts:**
  - Dedicated host workspace: `/tmp/eval_runs/{run_id}/workspace` $\to$ `/app` (rw).
  - Dedicated host logs directory: `/tmp/eval_runs/{run_id}/logs` $\to$ `/logs` (rw).
- **Lifecycle Guarantees:**
  - Managed via Python `contextmanager` with guaranteed cleanup in `finally:`.
  - Ephemeral containers and volumes pruned automatically on completion.

---

## 4. Universal Progress-Earned Budget Policy

Eliminating artificial time clamping requires clear, objective criteria for when an arm earns additional execution runway (`+1200s`, bounded by a maximum of 5 extensions):

| Arm | How Progress is Signaled | Verification Gate |
| :--- | :--- | :--- |
| **Arm C: Superstate** | Explicit CLI gate | `superstate state next --verify-cmd <cmd>` returns exit code 0. |
| **Arm B: Superpowers** | Git commits & test advancement | Agent creates a new valid git commit in `/app` containing modified/new test or source files. |
| **Arm A: Vanilla** | Git commits & productive tool calls | Agent creates a new valid git commit in `/app` showing forward implementation momentum. |

All arms receive an identical base timeout (e.g., 1800s). A run halts only if:
1. The agent signals task completion.
2. The agent exceeds its granted budget without earning further progress extensions.
3. The agent enters an unrecoverable infinite loop or crash state.

---

## 5. Blind Extraction and Grading Pipeline

Grading is 100% blind to which arm produced the solution:
1. **Patch Extraction:** Auto-commit uncommitted changes in `/app` and extract `git diff <base_commit> HEAD > /logs/artifacts/model.patch`.
2. **Held-out Test Injection:** Inject held-out verification tests into the container **only after** the agent has finished.
3. **Verifier Execution:** Run the task's verification command inside the container.
4. **Reward Assessment:** Parse `/logs/verifier/reward.json`.
5. **Grading Gate:**
   - **PASS:** `exit_code == 0` AND `reward == 1.0`.
   - **FAIL:** `exit_code != 0` OR `reward != 1.0` OR missing `reward.json`.
6. **Telemetry Archival:** Move `model.patch`, `reward.json`, execution transcripts, and (for Superstate) `state.json` into `runs/{task_id}/{arm}/`.

---

## 6. Verification and Efficacy Frontiers

Results will be aggregated and rendered as a cost-efficiency frontier:
- **Strict Pass Rate (%)**
- **Cost-Per-Verified-Solve (\$)**
- **Wall-Clock Duration & Lease Extensions Earned**
- **Token Efficiency (Input/Output tokens per solve)**
