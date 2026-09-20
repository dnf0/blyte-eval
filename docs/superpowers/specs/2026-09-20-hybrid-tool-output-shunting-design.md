# Hybrid Tool Output Shunting & Distillation Design Spec

**Date:** 2026-09-20  
**Status:** Approved by User (Ready for Planning)  
**Authors:** Daniel Fisher & Antigravity  
**Target Repositories:** `dnfcx/superstate-eval` and `repos/superstate`

---

## 1. Problem Statement & Context

In SWE-bench, Terminal-Bench, and real-world software engineering tasks, language models spend the majority of their token budgets absorbing verbose, low-signal tool execution outputs. During EXP-065 Task 1 (`build-cython-ext`), both arms (`superstate_mcp` and `superstate_daemon_full`) passed 11/11 tests on the held-out sealed grader, but consumed over 730,000 input tokens each ($0.79 vs $0.80), because raw Cython compilation flags, gcc build logs, and test suites dumped thousands of lines into the LLM context window.

Superstate has an engineered tool output distillation engine ("Spotify Portal" pattern) in `crates/superstate-core/src/shunt.rs` and `superstate shunt`, configured to truncate outputs exceeding 50 lines / 4 KB, store raw logs to `.agent-state/logs/`, and return a 10-line high-signal summary to the agent.

However, in containerized benchmarks:
1. The driver (`agy` / Antigravity) executes on macOS (`arm64-darwin`).
2. The code builds inside Docker (`amd64-linux`).
3. The bridge script `./run-in-container` executed raw `docker exec -i -w /app {container} "$@"` without routing through the shunting layer.
4. Furthermore, foreign containers did not have `superstate` installed internally for in-container subshells.

## 2. Core Architectural Objectives

1. **Context Window Protection:** Prevent verbose build logs, package installations, and test runners from blowing out LLM context, reducing token consumption by up to 80–90% on build-heavy milestones.
2. **Dual-Path Execution (Hybrid Architecture):**
   - **Path A (Host-Bridge Interception):** `./run-in-container` automatically pipes container execution through host-side `superstate shunt`. Works immediately across all benchmark images regardless of base OS, glibc, or CPU architecture.
   - **Path B (In-Container Native Mounting):** Bind-mount a statically-linked Linux binary (`x86_64-unknown-linux-musl`) into `/usr/local/bin/superstate` inside sandbox containers, enabling in-container drivers (`InContainerClaudeDriver`) and local subshells to call `superstate` directly.
3. **Fidelity & Signal Preservation:**
   - Preserve exact process exit codes (e.g. exit code 1, 127, 137).
   - Preserve stdin streaming (for `cat <<'EOF' | ./run-in-container sh -s`).
   - Extract critical failure excerpts (tracebacks, assertion failures, compilation errors) when exit codes are non-zero.
4. **Referee Rule & Arm Parity:**
   - Superstate arms (`superstate_daemon`, `superstate_mcp`) leverage Superstate's shunting layer.
   - Baseline arms (`vanilla`) remain unguided without shunting, strictly adhering to the referee rule.

---

## 3. System Architecture & Data Flow

```
[ LLM Driver (e.g. agy / Claude) ]
               │
               ▼
   [ run_command tool call ]
               │
               ▼
    ./run-in-container <cmd>
               │
       ┌───────┴────────────────────────┐
       ▼                                ▼
[Path A: Host Bridge]       [Path B: In-Container Native]
docker exec -i ... <cmd>    docker exec -i ... superstate shunt -- <cmd>
       │                                │
       ▼                                ▼
superstate shunt (Host)      superstate shunt (Container)
       │                                │
       └───────┬────────────────────────┘
               ▼
 [ evaluate_and_distill ]
   ├── >50 lines or >4KB?
   │     ├─ YES ──> Persist full log to .agent-state/logs/<cmd_hash>.log
   │     │          Return 10-line summary (head, tail, error lines, exit code)
   │     └─ NO  ──> Return raw stdout/stderr unchanged
   ▼
[ LLM Context Window: Bounded Token Footprint ]
```

---

## 4. Component Specifications

### 4.1 Container Bridge Shunting (`lab/engine/drivers/agy_cli.py`)

In `_setup_container_bridge(workspace_path: Path, container: Any)`:
The generated `./run-in-container` script in the workspace will check for shunting capability and route execution through `superstate shunt`:

```bash
#!/usr/bin/env bash
set -o pipefail

# Route through superstate shunt if available and enabled
if [ "${SUPERSTATE_SHUNT_ENABLED:-1}" = "1" ] && command -v superstate >/dev/null 2>&1; then
    exec superstate shunt --threshold-lines 50 -- docker exec -i -w /app {container_id} "$@"
else
    exec docker exec -i -w /app {container_id} "$@"
fi
```

### 4.2 Shunt CLI Command Hardening (`crates/superstate-cli/src/commands/shunt.rs`)

`superstate shunt -- <cmd> <args...>` must satisfy:
1. **Stdin Inheritance & Streaming:** Pass stdin directly to the child process without buffering or blocking interactive/piped inputs.
2. **Concurrent Stream Draining:** Drain child stdout and stderr concurrently on background threads to prevent OS pipe deadlocks (>64 KB buffer limits).
3. **Exit Code Propagation:** Return the exact exit code of the spawned command (`i32`), ensuring test assertions and gate verification exit statuses are 100% accurate.
4. **Log Retention:** Store full execution logs in `.agent-state/logs/cmd_<timestamp>_<hash>.log` with automatic `.gitignore` protection and FIFO pruning (max 1,000 files, 200 MB).

### 4.3 In-Container Native Binary Mounting (`lab/sandbox/docker_manager.py`)

In `DockerManager.spawn_sandbox()`:
When spawning a sandbox container:
1. Check if a pre-compiled static Linux binary exists (e.g. `bin/superstate-linux-x86_64` or env-configured path).
2. If present, add a read-only volume bind-mount:
   ```python
   combined_volumes[str(linux_bin_path)] = {
       "bind": "/usr/local/bin/superstate",
       "mode": "ro"
   }
   ```
3. If absent, log an informative debug message and continue normally.

### 4.4 Linux Static Build Pipeline (`repos/superstate`)

Add support for building static Linux binaries:
```bash
cargo build --release --target x86_64-unknown-linux-musl -p superstate-cli
```
This binary has zero dynamic dependencies and runs on any Linux distribution (Alpine, Ubuntu, Debian, CentOS, etc.).

---

## 5. Thresholds & Distillation Semantics

| Condition | Action | Output to Driver / LLM | Disk Action |
|---|---|---|---|
| Combined stdout/stderr $\le 50$ lines AND $\le 4\text{ KB}$ | Pass-through | Exact raw stdout and stderr | No disk write |
| Exit 0 AND ($>50$ lines OR $>4\text{ KB}$) | Distill | `[superstate-shunt] Command succeeded (exit 0). N lines omitted.\nFull log: <path>` | Full log written to `.agent-state/logs/` |
| Exit $\ne 0$ AND ($>50$ lines OR $>4\text{ KB}$) | Distill | `[superstate-shunt] Command failed with exit code X (N lines omitted).\nFull log: <path>\n\n--- Failure Excerpt ---\n<traceback>\n--- End Failure Excerpt ---` | Full log written to `.agent-state/logs/` |
| Binary output detected (null bytes) | Distill | `[superstate-shunt] Command produced binary output (N bytes).\nFull log: <path>` | Full log written to `.agent-state/logs/` |

---

## 6. Verification & Test Plan

### 6.1 Unit & Integration Tests (TDD)
1. **`tests/test_container_bridge.py` (`superstate-eval`):**
   - Test bridge generation with `SUPERSTATE_SHUNT_ENABLED=1`.
   - Test bridge exit code preservation (non-zero exits match child process).
   - Test bridge stdin handling with piped multiline scripts.
2. **`tests/test_docker_manager.py` (`superstate-eval`):**
   - Test optional bind-mount of static binary when file exists.
   - Test graceful fallback when static binary does not exist.
3. **`tests/test_arm_input_parity.py` (`superstate-eval`):**
   - Ensure arm input parity rules are respected and no synthetic scaffolding is introduced into prompts.
4. **`crates/superstate-cli/tests/test_cli_shunt.rs` (`superstate`):**
   - Test shunting large command outputs (>50 lines) vs small outputs (<=50 lines).
   - Test exit code return accuracy.

### 6.2 Empirical Benchmark Verification
- Rerun `build-cython-ext` with shunting enabled.
- Verify that input token consumption drops significantly below the 733k tokens recorded in EXP-065, while maintaining 11/11 tests passing on the sealed grader.
