# Graph Report - superstate-eval  (2026-09-18)

## Corpus Check
- 206 files · ~741,974 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 58 file(s) not represented in the graph (top: .log 52, (none) 5, .lock 1)

## Summary
- 1850 nodes · 4297 edges · 119 communities (94 shown, 25 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 334 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c2741fbd`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- .run_task
- DriverTelemetry
- AgyCliDriver
- ClaudeCliDriver
- handle
- reporter.py
- AnswerKeyGuard
- .run
- pilot.py
- .execute
- extract_and_grade
- RunRecorder
- test_docker_integration.py
- BaseCliDriver
- SuperstateMcpAdapter
- test_differential.py
- EvaluationResult
- SuperstateDaemonAdapter
- test_superstate_daemon_adapter.py
- ProgressTracker
- runner.py
- VanillaAdapter
- test_in_container_driver.py
- eval_offline_review.py
- Feature Implementation Plan
- BudgetPolicy
- superstate-eval
- benchmarks/__init__.py
- dag_plan.md
- superstate-eval
- SuperstateAgentMcpAdapter
- Design Specification: Agent-Driven Worktrees & Full-Context Turnkey Execution
- DockerManager
- load_benchmark_tasks
- test_superstate_mcp_client.py
- Control-Plane Evaluation — Plan
- test_state_engine_loop.py
- SuperpowersAdapter
- resolve_next_turn_prompt
- AgentImageBuilder
- Superstate Resilience, Diagnostic Retry Loops, and Git Native State Tracking Design
- ImageBuildError
- TaskRunResult
- Global Constraints
- .execute
- test_superstate_resilience.py
- ConcurrencyGovernor
- SuperstateMcpClient
- SuperstateAdapter
- test_agent_failure_is_diagnosed_before_the_grading_symptom
- HeldOutVerifier
- .run_sandbox
- Design Spec: Dynamic Container Workspace Switching for Worktree Isolation
- McpProcessError
- TaskSpec
- Global Constraints
- Superstate Massive Adoption & Founder Prestige Roadmap
- 3. Detailed Component Design
- run_weekend_benchmark.sh
- resolve_superstate_binary
- Frontier Triad Benchmark: Final Evaluation Report
- .clean_workspace
- ._perform_handshake
- Global Constraints
- FakePipe
- MCP Evaluation Dual Architecture Implementation Plan
- .__exit__
- test_superstate_agent_mcp.py
- pathlib
- test_superstate_adapter_gate_failure_stateless_retry
- launch_frontier_claude_haiku.sh
- launch_frontier_condition_b.sh
- launch_frontier_mcp_rerun.sh
- launch_frontier_triad_benchmark.sh
- launch_weekend_run.sh
- experiments.py
- is_transient_stream_interruption
- agent_gate_for
- test_canary_task_set.py
- Working in superstate-eval
- Working in superstate-eval
- What the evaluation establishes
- effect.py
- MockDriver
- conversation_id_for
- RunTelemetry
- StubDriver
- test_task_sets.py
- test_ablation_runner.py
- AblationRunner
- test_arm_input_parity.py
- is_unmeasurable
- pytest
- test_worktree_cleanup_on_completion
- Experiment ledger
- test_runner.py
- MockDriver
- Experiment provenance: what the 2026-09-13 benchmark actually ran
- harvest_run_diffs.py
- gate_derivation_enabled
- ignore_gate_fixtures
- launch_derived_gates.sh
- _extract_collect_commands
- derivation_on
- estimate_cost_usd
- .is_running
- launch_datacurve_3arm.sh
- launch_datacurve_clean.sh
- launch_datacurve_planned.sh
- launch_frontier_handoff_pilot.sh
- launch_gates_v2.sh
- run_canary.sh
- run_exp056.sh
- run_exp057.sh
- .__init__

## God Nodes (most connected - your core abstractions)
1. `TaskSpec` - 120 edges
2. `DriverTelemetry` - 86 edges
3. `SuperstateAdapter` - 83 edges
4. `SuperstateMcpClient` - 68 edges
5. `SuperstateDaemonAdapter` - 63 edges
6. `AgentDriver` - 55 edges
7. `AblationRunner` - 50 edges
8. `SuperstateMcpAdapter` - 47 edges
9. `AgyCliDriver` - 42 edges
10. `ClaudeCliDriver` - 40 edges

## Surprising Connections (you probably didn't know these)
- `Stream 2 — Rust parity — COMPLETE (2026-09-09)` --references--> `TaskSpec`  [INFERRED]
  docs/superpowers/plans/2026-09-09-control-plane-evaluation-plan.md → lab/benchmarks/task_loader.py
- `Task 3: Universal Zero-Turn Planning in Adapter (`superstate-eval`)` --references--> `SuperstateAdapter`  [INFERRED]
  docs/superpowers/plans/2026-09-12-agent-driven-worktrees-and-full-context.md → lab/engine/adapters/superstate.py
- `5. Verification & Test Plan` --references--> `SuperstateAdapter`  [INFERRED]
  docs/superpowers/specs/2026-09-12-agent-driven-worktrees-and-full-context-fidelity-design.md → lab/engine/adapters/superstate.py
- `Evaluation Arms Under Test` --references--> `SuperstateAdapter`  [INFERRED]
  docs/superpowers/specs/2026-09-14-cross-agent-handoff-and-daemon-benchmark-design.md → lab/engine/adapters/superstate.py
- `3.5 Runner Arms Configuration (`lab/engine/runner.py`)` --references--> `SuperstateAgentMcpAdapter`  [INFERRED]
  docs/superpowers/specs/2026-09-12-mcp-eval-dual-architecture-design.md → lab/engine/adapters/superstate_agent_mcp.py

## Import Cycles
- None detected.

## Communities (119 total, 25 thin omitted)

### Community 0 - ".run_task"
Cohesion: 0.12
Nodes (11): Model the harness was configured with, when the driver knows it., Isolated only with container_exec on: that is what removes host Bash., NoDriverConfiguredError, Any, RuntimeError, Execute a single task under the specified arm and budget policy. Guarantees: 1.…, Resolve a cohort entry into (task_id, image, base_budget_sec, task_spec)., Execute a matrix of tasks x arms concurrently using the dynamic governor. (+3 more)

### Community 1 - "DriverTelemetry"
Cohesion: 0.13
Nodes (45): DriverTelemetry, Outcome and telemetry metrics from a single driver invocation turn., _make_dummy_task(), MockDriver, Any, parametrize, Path, Tests for Evaluation Arm Adapters: Vanilla, Superpowers, and Superstate. (+37 more)

### Community 2 - "AgyCliDriver"
Cohesion: 0.07
Nodes (53): Antigravity CLI Driver (`AgyCliDriver`) Implementation Plan, Global Constraints, Task 1: Implement `AgyCliDriver` Core and Container Execution Bridge, Task 2: Verify Baseline and System Integration, Task 3: Execute Live Single-Task Smoke Run, 1. Executive Summary & Context, 3.1 Class Definition (`lab/engine/drivers/agy_cli.py`), 3.2 CLI Binary Resolution (+45 more)

### Community 3 - "ClaudeCliDriver"
Cohesion: 0.12
Nodes (38): ClaudeCliDriver, ClaudeCliDriverError, estimate_cost_usd(), find_superstate_binary(), _first(), Any, Path, RuntimeError (+30 more)

### Community 4 - "handle"
Cohesion: 0.13
Nodes (25): ContainerExec, _error(), handle(), log(), main(), Any, A minimal stdio MCP server exposing exactly one tool: exec in ONE container.…, Handle one JSON-RPC message. Returns a response, or None for notifications. (+17 more)

### Community 5 - "reporter.py"
Cohesion: 0.17
Nodes (16): generate_comparison_summary(), _harness_of(), Evaluation reporter generating cost-efficiency frontier comparisons., Group run telemetry by paradigm arm and calculate core efficiency metrics., Render control-plane lift, with the caveat that small n cannot support it., Render summary as a formatted text table for reports., Render Total Cost of Ownership (TCO) incorporating human remediation penalties., render_economic_tco_table() (+8 more)

### Community 6 - "AnswerKeyGuard"
Cohesion: 0.10
Nodes (32): 1. Overview & Objective, 2. Benchmark Task Suite: 5-Task Representative Pilot, 4. Quantitative Metrics & Reporting, 5. Security & Isolation Invariants, Design Specification: Cross-Agent Relay & Autonomous Detached Daemon Evaluation, Evaluation Arms Under Test, AnswerKeyGuard, is_readable() (+24 more)

### Community 7 - ".run"
Cohesion: 0.21
Nodes (10): Any, Path, Build the verifier image for `task` and return its tag., Run the held-out verifier against the collected patch. `logs_dir` must already…, Delete the verifier image so the hidden tests do not linger on the host., Run the built verifier image against the collected patch., Docker tags allow a restricted character set; task ids do not., Read reward.json, falling back to the reward.txt crash sentinel. Returns… (+2 more)

### Community 8 - "pilot.py"
Cohesion: 0.12
Nodes (15): MockContainer, PilotMockDriver, PilotShowdownRunner, Any, Path, Pilot showdown runner executing end-to-end task runs across Vanilla,…, Executes a single benchmark task across evaluation arms with isolated…, Execute task across arms and return structured benchmark outcomes. With… (+7 more)

### Community 9 - ".execute"
Cohesion: 0.22
Nodes (8): Any, BudgetHook, Path, Run an agent session or turn within the target workspace., Execute a task in the given workspace using the provided driver., Configure or sanitize workspace prior to agent invocation., Report arm-specific facts about how this run was actually configured., Execute task across sequential turns with bounded caps and autonomous approval.

### Community 10 - "extract_and_grade"
Cohesion: 0.07
Nodes (54): Global Constraints, Task 1: Extend EvaluationResult and Implement compute_test_metrics, Task 2: Integrate Test Metrics into Runner Telemetry and CLI Output, Test Pass Fraction & Test Statistics Implementation Plan, 1. Context & Motivation, 2.1 EvaluationResult Dataclass Extension, 2.2 Metric Extraction Helper, 2.3 AblationRunner Telemetry Integration (+46 more)

### Community 11 - "RunRecorder"
Cohesion: 0.15
Nodes (12): _clip(), Any, Path, Capture one driver turn, including the prompt that produced it., Capture a milestone attempt and its gate verdict., Persist the full held-out verifier output, untruncated., Write the headline run record. Returns the path written, if any., Truncate a captured field, saying so explicitly rather than silently. (+4 more)

### Community 12 - "test_docker_integration.py"
Cohesion: 0.15
Nodes (18): collections_abc, requires_docker, fixture, Path, Integration tests exercising a real Docker daemon. The unit suite mocks…, End-to-end: build the verifier image and have it write reward.json. Mirrors the…, reward.txt == -1 is an infrastructure failure, not a legitimate 0., End-to-end proof the exec lands inside the sandbox. The probe image carries a… (+10 more)

### Community 13 - "BaseCliDriver"
Cohesion: 0.15
Nodes (13): BaseCliDriver, CliDriverError, first(), Any, Path, RuntimeError, Turn the CLI's JSON result into telemetry., Raised when the agent CLI cannot be located or invoked. (+5 more)

### Community 14 - "SuperstateMcpAdapter"
Cohesion: 0.05
Nodes (53): Gate precision — read it after every run, Any, BudgetHook, Path, Keep harness files from dirtying the tree that git verification gates inspect., Sanitize workspace by stripping legacy guidance and excluding harness artifacts., Resolve active worktree path from state.json if provisioned., Strip a host-side bridge wrapper when the gate already runs in the sandbox. (+45 more)

### Community 15 - "test_differential.py"
Cohesion: 0.16
Nodes (19): deepdiff, tempfile, check_binaries(), normalize_state(), fixture, Path, Differential parity testing between superstate (Rust) and agent-rules (Python).…, Resolve a binary from env, then PATH (only if a name is given), then fallbacks.… (+11 more)

### Community 16 - "EvaluationResult"
Cohesion: 0.24
Nodes (15): EvaluationResult, Outcome of blind verification and patch extraction., Path, Verify fallback to 1.0 pass fraction when verifier stats are None and task…, Verify fallback to 0.0 pass fraction when verifier stats are None and task…, Helper to initialize git repo in workspace seed for simulated runner tests., Instantiate an AblationRunner configured with mocked docker and governor.…, Verify that granular verifier statistics populate test metrics in telemetry… (+7 more)

### Community 17 - "SuperstateDaemonAdapter"
Cohesion: 0.07
Nodes (33): advisory_review_enabled(), is_pid_alive(), Any, BudgetHook, Path, Whether code review blocks advancement when Critical/High issues are found., Check if process with given PID is alive., Adapter executing tasks autonomously via the detached Superstate DaemonRunner. (+25 more)

### Community 18 - "test_superstate_daemon_adapter.py"
Cohesion: 0.07
Nodes (46): SimpleNamespace, Path, Driver stub returning a canned gate proposal., A gate that passes before any work cannot discriminate, so it must be refused.…, The driver must never gate on /tests/ -- that is the answer key., The daemon expands the bare `agy` preset without --model or JSON output.…, The daemon's worker must be told where the project environment actually is. The…, Driver stub returning a different response per successive turn. (+38 more)

### Community 19 - "ProgressTracker"
Cohesion: 0.16
Nodes (12): Task 3: Universal Progress-Earned Budget Tracker, Record completed milestone and grant progress lease extension if within max…, ProgressTracker, Path, Monitors workspace state and awards progress-earned lease extensions to any arm., Query current HEAD commit hash from workspace git repository., Parse completed task count from .agent-state/state.json if present., Check for forward progress signals and trigger lease extension on advancement. (+4 more)

### Community 20 - "runner.py"
Cohesion: 0.09
Nodes (30): argparse, concurrent_futures, contextlib, dataclasses, docker, docker_models_containers, hashlib, io (+22 more)

### Community 21 - "VanillaAdapter"
Cohesion: 0.07
Nodes (33): Base template adapter managing bounded turn execution and mechanical approval., Provide initial instruction prompt for the task. Baseline arms (vanilla,…, TurnBasedAdapter, Arm A: Vanilla (Control) Adapter. Runs unguided SWE-bench baseline execution…, Unguided baseline adapter enforcing complete isolation from rules or skills., VanillaAdapter, apply_contract(), apply_generic_rules() (+25 more)

### Community 22 - "test_in_container_driver.py"
Cohesion: 0.15
Nodes (22): base64, _first(), InContainerClaudeDriver, InContainerDriverError, Any, Path, RuntimeError, Raised when the in-container agent cannot be invoked. (+14 more)

### Community 23 - "eval_offline_review.py"
Cohesion: 0.11
Nodes (29): clean_json_response(), compute_review_metrics(), get_task_instruction(), main(), Any, Offline code review evaluation against harvested false-pass and true-pass runs.…, Compute aggregate precision, recall, and false alarm rate from review results., Retrieve the task instruction markdown. (+21 more)

### Community 24 - "Feature Implementation Plan"
Cohesion: 0.40
Nodes (4): Feature Implementation Plan, Task 1: Setup database schema, Task 2: Implement repository methods, Task 3: Expose REST endpoint

### Community 25 - "BudgetPolicy"
Cohesion: 0.17
Nodes (11): superstate-eval Local Assessment Repository Implementation Plan, Tasks, Verification & Completion Gates, BudgetPolicy, Progress-earned budget policy and execution telemetry accounting. Allows…, Manages progress-earned execution timeouts., Tests for Progress-Earned Budget Policy and Telemetry Accounting., test_budget_policy_earn_extension_on_progress() (+3 more)

### Community 26 - "superstate-eval"
Cohesion: 0.20
Nodes (9): A note on what this harness has taught us, Differential parity, How a run works, Layout, Quick start, superstate-eval, Tasks, What is measured (+1 more)

### Community 34 - "SuperstateAgentMcpAdapter"
Cohesion: 0.11
Nodes (19): Any, BudgetHook, Path, Report state engine, transport, and autonomous tooling provenance. Returns:…, Keep harness files from dirtying the git working tree. Appends harness-internal…, Sanitize workspace by stripping legacy guidance and excluding harness…, Strip host-side bridge scripts when running verification inside the container.…, Execute a verification command either inside a container sandbox or on the… (+11 more)

### Community 35 - "Design Specification: Agent-Driven Worktrees & Full-Context Turnkey Execution"
Cohesion: 0.12
Nodes (15): 1.1 `ExecutionState` Model (`crates/superstate-core/src/models.rs`), 1.2 Full-Context Turnkey Prompt (`crates/superstate-core/src/prompt.rs`), 1. Problem Statement & Motivation, 2.1 Default In-Place Execution in `state init`, 2.2 Dedicated Agent Worktree Commands, 2. Core Architectural Principles, 3.1 Universal Zero-Turn Direct Initialization, 3.2 Dynamic Turn & Milestone Execution (+7 more)

### Community 36 - "DockerManager"
Cohesion: 0.16
Nodes (14): DockerClient, DiskSpaceError, DockerManager, Raised when host disk space falls below the critical emergency threshold., Prune dangling images, stopped containers, and unreferenced volumes., Manages Docker containers and host disk resource reclamation., Tests for Docker Lifecycle and Disk Space Watchdog., test_check_disk_space_healthy() (+6 more)

### Community 37 - "load_benchmark_tasks"
Cohesion: 0.22
Nodes (13): load_benchmark_tasks(), load_task_from_dir(), Path, Parse task.toml and instruction.md from task_dir into a TaskSpec., Scan directory tree for benchmark task directories containing task.toml., Directory holding the held-out verifier (Dockerfile, test.sh, grader.py)., main(), Path (+5 more)

### Community 38 - "test_superstate_mcp_client.py"
Cohesion: 0.09
Nodes (26): FakeMcpServerProcess, MonkeyPatch, Path, Tests for SuperstateMcpClient. Verifies stdio JSON-RPC MCP protocol handshake,…, Verify initialize, initialized notification, tools/list, and caching 25 tools., Verify call_tool parses text and nested json in result.content., Verify call_tool raises McpRpcError on JSON-RPC error payload., Verify context manager automatically starts and terminates child process. (+18 more)

### Community 39 - "Control-Plane Evaluation — Plan"
Cohesion: 0.13
Nodes (14): Control-Plane Evaluation — Plan, Harness defects found by running (all fixed), Parked, with reasons, Standing lesson from today, Stream 1 — Produce a credible measurement, Stream 2 — Rust parity — COMPLETE (2026-09-09), Task 1: Pin the engine explicitly and record it — DONE, Task 2: Drive the real state-engine loop — DONE (+6 more)

### Community 40 - "test_state_engine_loop.py"
Cohesion: 0.30
Nodes (12): requires_engine, _engines(), parametrize, Path, The superstate adapter driving a real state engine through a full loop. Every…, Succeeds every turn, recording the prompts it was given., ScriptedDriver, test_a_failing_gate_stops_the_run_and_is_reported() (+4 more)

### Community 41 - "SuperpowersAdapter"
Cohesion: 0.20
Nodes (7): Any, Path, Adapter configuring markdown rules and vendored superpowers skills., Install markdown guidance and copy superpowers skills into workspace., Configure workspace with Superpowers guidance before execution begins., Record whether the vendored skills library was actually installed., SuperpowersAdapter

### Community 42 - "resolve_next_turn_prompt"
Cohesion: 0.27
Nodes (11): is_waiting_for_user_input(), Inspect agent output and return automated approval prompt if waiting, or None…, Analyze agent response text to detect if the agent paused for human approval or…, resolve_next_turn_prompt(), Tests for Mechanical User and Autonomous Human-in-the-Loop Elimination., test_is_waiting_for_user_input_detects_ask_question_tool(), test_is_waiting_for_user_input_detects_standard_approval_prompts(), test_is_waiting_for_user_input_detects_superpowers_state_gates() (+3 more)

### Community 43 - "AgentImageBuilder"
Cohesion: 0.24
Nodes (6): AgentImageBuilder, Docker tags allow a restricted character set; image refs do not., Builds and caches per-task agent images., A deterministic tag: this image holds no secrets, so caching is safe. Unlike…, Build (or reuse) an image with the Claude Code CLI on top of `base_image`., _slug()

### Community 44 - "Superstate Resilience, Diagnostic Retry Loops, and Git Native State Tracking Design"
Cohesion: 0.20
Nodes (9): 1. Context & Motivation, 2. Goals & Non-Goals, 3.1 Diagnostic Retry Loop in `lab/engine/adapters/superstate.py`, 3.2 Greenfield Git Resilience, 3. Architecture & Mechanics, 4. Verification & Testing, Goals, Non-Goals (+1 more)

### Community 45 - "ImageBuildError"
Cohesion: 0.14
Nodes (11): ImageBuildError, Path, RuntimeError, Copy the task repository out of `image` into the host directory `dest`. A bind…, Build an image from `context_dir` and return its tag. Used for the held-out…, Build an image from an inline Dockerfile with no build context., Stop docker-py invoking every configured credential helper on build. docker-py…, Check available disk space. Prune docker if below min_free_gb; raise if below… (+3 more)

### Community 46 - "TaskRunResult"
Cohesion: 0.14
Nodes (19): Cross-Agent Relay & Autonomous Detached Daemon Evaluation Implementation Plan, Global Constraints, Task 1: Implement `SuperstateRelayAdapter`, Task 2: Implement `SuperstateDaemonAdapter`, Task 3: Wire Adapters into Runner and Add End-to-End Harness Tests, Task 4: Automated Pilot Script & 5-Task Benchmark Execution, 3.1 `SuperstateRelayAdapter` (`lab/engine/adapters/superstate_relay.py`), 3.2 `SuperstateDaemonAdapter` (`lab/engine/adapters/superstate_daemon.py`) (+11 more)

### Community 47 - "Global Constraints"
Cohesion: 0.25
Nodes (7): Global Constraints, Superstate Resilience and Diagnostic Retry Loop Implementation Plan, Task 1: Implement Greenfield Git Handling in `lab/engine/adapters/superstate.py`, Task 2: Implement Milestone Diagnostic Retry Loop in `lab/engine/adapters/superstate.py`, Task 3: Unit Tests for Retry Loop & Greenfield Handling, Task 4: Native Git Initialization in Rust `superstate`, Task 5: Verification & Checkpoint

### Community 48 - ".execute"
Cohesion: 0.07
Nodes (28): _extract_plan_milestones(), flush(), find_superstate_binary(), Milestone, Any, BudgetHook, Path, Resolve the state-engine binary for a named implementation. Resolution is… (+20 more)

### Community 49 - "test_superstate_resilience.py"
Cohesion: 0.27
Nodes (7): FlakyGateDriver, Path, Tests for Superstate milestone retry loops and greenfield resilience., Verify that a greenfield workspace without .git does not crash when advancing…, Fails on turn 1 by not creating marker.txt, then creates it on turn 2 after…, test_greenfield_workspace_advances_without_git(), test_milestone_retry_loop_on_failed_gate()

### Community 50 - "ConcurrencyGovernor"
Cohesion: 0.07
Nodes (35): Concurrent Evaluation Isolation & Universal Progress Budgeting Implementation Plan, Proposed File Changes, Task 1: Dynamic Machine-Aware Concurrency Governor, Task 4: Blind Extraction & Verification Pipeline, Task 5: End-to-End Concurrent Runner & Integration, 1. Executive Summary & Goals, 2. Dynamic Concurrency Governor, 3. Strict Docker Sandbox Quotas & Volume Isolation (+27 more)

### Community 51 - "SuperstateMcpClient"
Cohesion: 0.12
Nodes (26): Task 1: `SuperstateMcpClient` Implementation & Protocol Handshake, Task 2: Harness-Level Adapter (`SuperstateMcpAdapter`), Execution Flow:, Ledger, Any, Path, Client for communicating with the superstate MCP server over stdio JSON-RPC.…, Return cached map of discovered tools keyed by name. (+18 more)

### Community 52 - "SuperstateAdapter"
Cohesion: 0.13
Nodes (20): 2. Core Objectives, Adapter executing tasks under the deterministic Superstate engine., Extract a clean, concise finding from the turn's response to keep prompts…, SuperstateAdapter, Path, test_switch_container_workspace_handles_exec_nonzero_exit(), test_switch_container_workspace_handles_none_container(), test_switch_container_workspace_no_worktree_mode() (+12 more)

### Community 53 - "test_agent_failure_is_diagnosed_before_the_grading_symptom"
Cohesion: 0.25
Nodes (5): A result from a driver with a host shell carries a weaker guarantee. It must…, An agent that times out leaves a bad patch; the timeout is the cause. Reporting…, test_agent_failure_is_diagnosed_before_the_grading_symptom(), test_run_telemetry_records_whether_execution_was_isolated(), fake_sandbox()

### Community 54 - "HeldOutVerifier"
Cohesion: 0.33
Nodes (11): Path, HeldOutVerifier, Builds and runs the task's own verifier image., _manager(), Path, The verifier image is the held-out answer key; it must not linger on the host., _Task, test_keep_image_is_opt_in_for_debugging() (+3 more)

### Community 55 - ".run_sandbox"
Cohesion: 0.20
Nodes (8): Container, Task 2: Container Resource Constraints & Volume Isolation, Dynamic Container Workspace Switching Implementation Plan, Global Constraints, Task 1: Runner Mount Decoupling & Container Symlink Setup, Task 2: Worktree Turn Repointing in Superstate Adapter, Task 3: Live Verification on `db-wal-recovery`, Run a container with guaranteed teardown upon context exit. Guarantees that the…

### Community 56 - "Design Spec: Dynamic Container Workspace Switching for Worktree Isolation"
Cohesion: 0.33
Nodes (5): 1. Problem Statement, 2. Proposed Architecture, 3. Benefits & Performance, Design Spec: Dynamic Container Workspace Switching for Worktree Isolation, Dynamic `/app` Symlink via `/workspace_root` Mount

### Community 57 - "McpProcessError"
Cohesion: 0.14
Nodes (17): 3.1 `SuperstateMcpClient` (`lab/engine/mcp/client.py`), Responsibilities:, Exception, McpError, McpProcessError, McpRpcError, McpTimeoutError, Send a JSON-RPC request and wait for the corresponding response. Parameters:… (+9 more)

### Community 58 - "TaskSpec"
Cohesion: 0.14
Nodes (16): Concurrent Verifier Seal Resolution & 4-Worker Concurrency Plan, Task 1: TaskSpec `has_verifier_dockerfile` Seal Resilience & Test, Task 2: Concurrency 4 Configuration, Task 3: Full Verification Suite, Task 4: Commit & Merge, Task 5: Launch Benchmark Suite at Concurrency 4, Specification of an evaluation benchmark task., Whether the task has a Dockerfile in its tests/ directory. (+8 more)

### Community 59 - "Global Constraints"
Cohesion: 0.29
Nodes (6): Agent-Driven Worktrees & Full-Context Turnkey Execution Implementation Plan, Global Constraints, Task 1: Model & Prompt Context Fidelity (`superstate-core`), Task 2: In-Place Default & Agent Worktree CLI (`superstate-cli`), Task 3: Universal Zero-Turn Planning in Adapter (`superstate-eval`), Task 4: Targeted Benchmark Verification on Target Subset

### Community 60 - "Superstate Massive Adoption & Founder Prestige Roadmap"
Cohesion: 0.13
Nodes (14): 1. Executive Summary & Core Mission, 2. Core Positioning & Intellectual Anchors, 3. Four-Phase Execution Roadmap, 4. Key Metrics & Success Criteria, 5. Spec Self-Review Checklist, Phase 1: Packaging & Developer Ergonomics (Week 1), Phase 2: The Technical Manifesto & Empirical Paper (Week 2), Phase 3: The Viral Launch Campaign (Week 3) (+6 more)

### Community 61 - "3. Detailed Component Design"
Cohesion: 0.18
Nodes (10): 1. Executive Summary & Objective, 2. Architecture & Components, 3.2 Harness-Level Adapter: `SuperstateMcpAdapter` (`lab/engine/adapters/superstate_mcp.py`), 3.3 Agent-Level Autonomous Adapter: `SuperstateAgentMcpAdapter` (`lab/engine/adapters/superstate_agent_mcp.py`), 3.4 Driver Integration (`lab/engine/drivers/claude_cli.py`), 3.5 Runner Arms Configuration (`lab/engine/runner.py`), 3. Detailed Component Design, 4. Verification & Testing Strategy (+2 more)

### Community 63 - "resolve_superstate_binary"
Cohesion: 0.40
Nodes (3): Initialize the MCP client configuration. Parameters: superstate_bin: Path to…, Resolve the executable path to the superstate binary. Parameters:…, resolve_superstate_binary()

### Community 64 - "Frontier Triad Benchmark: Final Evaluation Report"
Cohesion: 0.20
Nodes (9): 1. Executive Summary, 2. Comparative Scorecard & Economics, 3. Granular Test Breakdown: Moving Past Binary Metrics, 4. Full Per-Task Results (All 30 Tasks), 5. Architectural Findings, Frontier Triad Benchmark: Final Evaluation Report, Standard Benchmark Metrics, SWE-Bench Test Completion Comparison (+1 more)

### Community 65 - ".clean_workspace"
Cohesion: 0.50
Nodes (3): Path, Sanitize workspace by removing all guidance, rule files, and skills., Ensure pristine unguided workspace before execution.

### Community 66 - "._perform_handshake"
Cohesion: 0.22
Nodes (5): Start the MCP server when entering the context block., Generate a monotonically increasing request ID., Spawn the superstate mcp process and execute protocol handshake. Raises:…, Execute standard MCP initialization handshake and populate tool cache., Send a JSON-RPC notification message without awaiting reply.

### Community 67 - "Global Constraints"
Cohesion: 0.22
Nodes (8): Global Constraints, Superstate Massive Adoption & Founder Prestige Implementation Plan, Task 1: Prebuilt Multi-Platform Binary Releases & Homebrew Tap Setup, Task 2: Interactive `superstate init` Repository Wizard, Task 3: MCP Registry & Smithery Integration Metadata, Task 4: Empirical Technical Whitepaper & Academic Preprint, Task 5: Launch Campaign Package (Show HN, Viral X Thread, Video Script), Task 6: Turnkey GitHub Action (`superstate/action@v1`)

### Community 68 - "FakePipe"
Cohesion: 0.22
Nodes (3): FakePipe, Any, Mock file-like pipe supporting write and readline.

### Community 69 - "MCP Evaluation Dual Architecture Implementation Plan"
Cohesion: 0.40
Nodes (4): Global Constraints, MCP Evaluation Dual Architecture Implementation Plan, Task 3: Driver MCP Support & Agent-Level Autonomous Adapter, Task 4: Runner Integration & Benchmark Parity Verification

### Community 70 - ".__exit__"
Cohesion: 0.40
Nodes (3): BaseException, Terminate the server process cleanly upon exiting context., Cleanly terminate the superstate child process and close pipes.

### Community 71 - "test_superstate_agent_mcp.py"
Cohesion: 0.16
Nodes (23): _init_git_repo(), _make_dummy_task(), MockDriver, Path, Tests for SuperstateAgentMcpAdapter. Tests the agent-level autonomous MCP…, Verify setup_workspace strips legacy files and excludes harness artifacts., Verify driver prompt is seeded with autonomous contract and…, The contract is preserved, not deleted: historical runs remain reproducible. (+15 more)

### Community 72 - "pathlib"
Cohesion: 0.14
Nodes (28): abc, json, AgentDriver, Base interfaces and data structures for execution adapters and agent drivers., Remove guidance files the task repo ships. Returns what was removed., Abstract driver interface communicating with an underlying agent runtime.…, strip_preexisting_guidance(), Arm adapters for Vanilla, Superpowers, and Superstate execution. (+20 more)

### Community 79 - "experiments.py"
Cohesion: 0.14
Nodes (17): collections, random, classify_arm(), evaluate(), load_runs(), Any, Evaluate Section 10's routing claims with a reproducible split-half validation.…, cmd_check() (+9 more)

### Community 80 - "is_transient_stream_interruption"
Cohesion: 0.50
Nodes (4): is_transient_stream_interruption(), Classify whether an error string represents a transient API transport…, Verify is_transient_stream_interruption correctly classifies transport vs…, test_is_transient_stream_interruption_detection()

### Community 81 - "agent_gate_for"
Cohesion: 0.13
Nodes (17): agent_gate_for(), Hand-authored agent-facing verification gates, one per benchmark task. WHY…, Whether a command reads the sealed held-out grader at the container root., Return the hand-authored agent-facing gate for a task, if one exists. This is…, references_sealed_grader(), image_present(), main(), The gate fixtures are the contract of record, so their shape is worth pinning. (+9 more)

### Community 82 - "test_canary_task_set.py"
Cohesion: 0.12
Nodes (17): ArgumentParser, is_canary(), Whether a task belongs to the fast 3-task Canary slice., build_parser(), Unit tests for the Canary 3 task set and runner configuration., Canary set must contain exactly the 3 designated fast discriminating tasks., is_canary must identify canary tasks and reject others., Every canary task must belong to DISCRIMINATING_TASKS to provide valid signal. (+9 more)

### Community 83 - "Working in superstate-eval"
Cohesion: 0.11
Nodes (18): A bad gate is worse than no gate, Arm input parity — the single most common source of false findings, Arms — check the name before comparing anything, Before running anything: check the ledger, Do not run `vanilla` by default, Drivers, Gated vs ungated — why it decides what a run measures, Python environment (+10 more)

### Community 84 - "Working in superstate-eval"
Cohesion: 0.11
Nodes (18): A bad gate is worse than no gate, Arm input parity — the single most common source of false findings, Arms — check the name before comparing anything, Before running anything: check the ledger, Do not run `vanilla` by default, Drivers, Gated vs ungated — why it decides what a run measures, Python environment (+10 more)

### Community 85 - "What the evaluation establishes"
Cohesion: 0.12
Nodes (17): 10. The +20pp routing lift was an in-sample artifact, 1. The effect is real, and its size is +19pp, 2. The mechanism is the handoff prompt, not the control loop, 3. The daemon is a legitimate default, 4. The loop does fire — on hard enough tasks, 5. The benchmark corpus is a third the size it appears, 6. Nothing in superstate builds the gate, 7. The gate is not an eval convention — it is ours (+9 more)

### Community 86 - "effect.py"
Cohesion: 0.17
Nodes (15): itertools, bootstrap_ci(), collect(), _infra_failure(), main(), permutation_p(), Path, One row per task: (name, vanilla rate, superstate rate, n_vanilla,… (+7 more)

### Community 87 - "MockDriver"
Cohesion: 0.13
Nodes (14): auto_rollback_enabled(), Whether automatic rollback on milestone failure is enabled for the daemon., MockDriver, Any, MonkeyPatch, Mock agent driver for testing., When auto_rollback is True, --auto-rollback is appended to the daemon spawn…, When auto_rollback is False, --auto-rollback is not in the daemon spawn command. (+6 more)

### Community 88 - "conversation_id_for"
Cohesion: 0.22
Nodes (12): carries_conversation(), conversation_id_for(), The Condition B execution contract, written down so it stops drifting. WHY THIS…, Whether this arm may thread a conversation id across turns. Condition B arms…, The conversation id to use for the next turn of `arm`. Returns None for…, Condition B is defined by stateless turns; guard against that drifting again., Zero-turn injection is the mechanism the 76% result was built on. Threading a…, Condition A is the in-loop paradigm under test; making it stateless would erase… (+4 more)

### Community 89 - "RunTelemetry"
Cohesion: 0.19
Nodes (12): Any, Auditable execution telemetry across an evaluation unit., RunTelemetry, _failure_signature(), Any, Collapse a failure reason to a comparable class, stripping run-specific detail., Cluster failures per arm so recurring defects are visible. A pass rate says an…, Render clustered failures as text, most frequent first. (+4 more)

### Community 90 - "StubDriver"
Cohesion: 0.15
Nodes (11): _fake_sandbox_factory(), Build a run_sandbox stand-in that writes a passing verifier artifact., test_ablation_runner_default_execution_mounts_workspace_into_container(), run(), Path, test_agy_cli_driver_run_in_container_sets_workdir(), test_runner_mounts_workspace_root_and_inits_symlink(), fake_run_sandbox() (+3 more)

### Community 91 - "test_task_sets.py"
Cohesion: 0.23
Nodes (9): excluded_reason(), is_discriminating(), Which tasks a comparison should actually run. The 30-task corpus does not…, Whether a task can contribute signal to an arm-vs-arm comparison., Why a gradeable task is kept out of the core set, or None if it is in., The core set must account for every task, and never include an ungradeable one., A task is in the core set, excluded with a reason, or ungradeable -- never lost., test_every_exclusion_states_a_reason() (+1 more)

### Community 92 - "test_ablation_runner.py"
Cohesion: 0.29
Nodes (11): compute_control_plane_lift(), Measure what each layer adds to a given harness, task by task. This evaluation…, InsufficientResourcesError, Raised when the host cannot safely run even a single concurrent evaluation., _paired(), Tests for Ablation Runner and Reporter., test_lift_is_measured_per_harness_and_task_pair(), test_lift_never_compares_across_different_harnesses() (+3 more)

### Community 93 - "AblationRunner"
Cohesion: 0.18
Nodes (10): AblationRunner, Executes benchmark tasks across evaluation arms with resource and lease…, A cohort of 8 GB tasks must not be dispatched at the 4 GB default width., test_ablation_runner_execution_and_cleanup(), test_ablation_runner_live_path_requires_explicit_driver(), test_run_cohort_forwards_task_specs_and_driver(), test_run_cohort_sizes_concurrency_on_declared_task_memory(), test_ablation_runner_universal_lease_extension() (+2 more)

### Community 94 - "test_arm_input_parity.py"
Cohesion: 0.17
Nodes (11): Every arm must receive the same inputs, or a comparison measures the harness.…, All arms must consult GATE_FIXTURES before falling back. superstate_mcp.py was…, The `true` fallback must come AFTER the fixture lookup, not instead of it., The daemon spawns its own worker, bypassing AgyCliDriver. Each flag…, `turns` must count worker invocations in every arm, or arms cannot be compared.…, Two configurations must never report the same name, or results pool them…, test_daemon_reports_driver_turns_not_state_steps(), test_daemon_worker_invocation_matches_the_shared_driver() (+3 more)

### Community 95 - "is_unmeasurable"
Cohesion: 0.20
Nodes (10): A task with no sealed grader cannot be scored, is_unmeasurable(), Reason a task cannot be scored, or None if it can., A task whose grader cannot run scores every arm zero and shrinks the…, A task with no held-out tests/ cannot be scored, so it must be listed. The…, test_tasks_without_a_sealed_grader_are_marked_unmeasurable(), test_unmeasurable_tasks_are_documented_with_a_reason(), A task with no held-out grader cannot contribute signal, only self-grading.… (+2 more)

### Community 96 - "pytest"
Cohesion: 0.22
Nodes (8): pytest, A worker must be sized from what the tasks declare, not from a constant., Sizing depends on memory_mb being present; without it the fix silently reverts., The flat 1.5 GB assumption advertised a ceiling the machine could not honour.…, Over-subscription must fail loudly, not silently record starved workers as…, test_heavier_tasks_lower_the_concurrency_ceiling(), test_paired_run_refuses_to_oversubscribe(), test_tasks_declare_their_memory_requirement()

### Community 97 - "test_worktree_cleanup_on_completion"
Cohesion: 0.22
Nodes (6): MonkeyPatch, When agent forgets state_next but verification gate passes, adapter marks…, Verify client.worktree_clean is called upon finish., driver_action(), test_fallback_to_verification_gate_when_state_not_advanced(), test_worktree_cleanup_on_completion()

### Community 98 - "Experiment ledger"
Cohesion: 0.25
Nodes (4): Cross-cutting findings, Experiment ledger, Rules, Status values

### Community 99 - "test_runner.py"
Cohesion: 0.43
Nodes (6): parametrize, Tests for AblationRunner telemetry and metrics integration. Validates that…, test_runner_resolves_superstate_agent_mcp_arms(), test_runner_resolves_superstate_mcp_default_arms(), test_runner_resolves_superstate_mcp_planned_arms(), test_runner_resolves_superstate_mcp_worktree_arms()

### Community 100 - "MockDriver"
Cohesion: 0.33
Nodes (4): MockDriver, Any, Predictable mock driver recording calls and returning successful telemetry., Simulate agent execution by writing a stub solution file. Parameters: task:…

### Community 101 - "Experiment provenance: what the 2026-09-13 benchmark actually ran"
Cohesion: 0.33
Nodes (5): Constant gates, not moving ones, Experiment provenance: what the 2026-09-13 benchmark actually ran, Stateless solo, not conversational, The confound that is real, The valid comparison

### Community 102 - "harvest_run_diffs.py"
Cohesion: 0.40
Nodes (5): get_git_diff_and_untracked(), harvest(), Path, Harvest labelled diffs and execution telemetry from /tmp/superstate_eval_runs.…, Extract git diff from initial baseline commit to current state, including…

### Community 103 - "gate_derivation_enabled"
Cohesion: 0.50
Nodes (4): gate_derivation_enabled(), Whether the daemon may author its own verification contract when none is…, Retained behind a flag so the 2026-09-15 runs that used it stay reproducible., test_gate_derivation_can_be_re_enabled_for_reproduction()

### Community 104 - "ignore_gate_fixtures"
Cohesion: 0.50
Nodes (4): ignore_gate_fixtures(), Whether to skip the hand-authored fixture so the driver must author the gate.…, Gate authorship cannot be measured while a fixture exists for every task.…, test_fixture_short_circuits_derivation_unless_explicitly_ignored()

### Community 105 - "launch_derived_gates.sh"
Cohesion: 0.50
Nodes (3): launch_derived_gates.sh script, SUPERSTATE_EVAL_DERIVE_GATES, SUPERSTATE_EVAL_IGNORE_GATE_FIXTURES

### Community 106 - "_extract_collect_commands"
Cohesion: 0.67
Nodes (3): _extract_collect_commands(), Any, Ingest collector command sequences used to extract test or run artifacts.

### Community 107 - "derivation_on"
Cohesion: 0.67
Nodes (3): derivation_on(), fixture, Gate derivation is opt-in: the daemon does not author its own contract by…

## Knowledge Gaps
- **152 isolated node(s):** `superstate-eval`, `launch_datacurve_3arm.sh script`, `launch_datacurve_clean.sh script`, `launch_datacurve_planned.sh script`, `launch_derived_gates.sh script` (+147 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 806 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **25 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TaskSpec` connect `TaskSpec` to `.run_task`, `DriverTelemetry`, `AgyCliDriver`, `ClaudeCliDriver`, `AnswerKeyGuard`, `pilot.py`, `.execute`, `extract_and_grade`, `BaseCliDriver`, `SuperstateMcpAdapter`, `EvaluationResult`, `SuperstateDaemonAdapter`, `test_superstate_daemon_adapter.py`, `runner.py`, `VanillaAdapter`, `test_in_container_driver.py`, `SuperstateAgentMcpAdapter`, `load_benchmark_tasks`, `Control-Plane Evaluation — Plan`, `test_state_engine_loop.py`, `TaskRunResult`, `.execute`, `test_superstate_resilience.py`, `SuperstateAdapter`, `test_agent_failure_is_diagnosed_before_the_grading_symptom`, `test_superstate_agent_mcp.py`, `pathlib`, `MockDriver`, `StubDriver`, `test_ablation_runner.py`, `AblationRunner`, `test_runner.py`, `MockDriver`?**
  _High betweenness centrality (0.186) - this node is a cross-community bridge._
- **Why does `SuperstateMcpClient` connect `SuperstateMcpClient` to `test_worktree_cleanup_on_completion`, `SuperstateAgentMcpAdapter`, `._perform_handshake`, `MCP Evaluation Dual Architecture Implementation Plan`, `.__exit__`, `test_superstate_agent_mcp.py`, `pathlib`, `test_superstate_mcp_client.py`, `.is_running`, `SuperstateMcpAdapter`, `SuperstateDaemonAdapter`, `McpProcessError`, `3. Detailed Component Design`, `resolve_superstate_binary`?**
  _High betweenness centrality (0.124) - this node is a cross-community bridge._
- **Why does `SuperstateDaemonAdapter` connect `SuperstateDaemonAdapter` to `DriverTelemetry`, `pathlib`, `TaskRunResult`, `SuperstateMcpAdapter`, `test_superstate_daemon_adapter.py`, `SuperstateMcpClient`, `runner.py`, `MockDriver`, `TaskSpec`?**
  _High betweenness centrality (0.085) - this node is a cross-community bridge._
- **Are the 31 inferred relationships involving `TaskSpec` (e.g. with `Stream 2 — Rust parity — COMPLETE (2026-09-09)` and `Task 1: TaskSpec `has_verifier_dockerfile` Seal Resilience & Test`) actually correct?**
  _`TaskSpec` has 31 INFERRED edges - model-reasoned connections that need verification._
- **Are the 16 inferred relationships involving `DriverTelemetry` (e.g. with `Task 1: Implement `SuperstateRelayAdapter`` and `2. Core Objectives`) actually correct?**
  _`DriverTelemetry` has 16 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `SuperstateAdapter` (e.g. with `Task 3: Universal Zero-Turn Planning in Adapter (`superstate-eval`)` and `2. Core Objectives`) actually correct?**
  _`SuperstateAdapter` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `SuperstateMcpClient` (e.g. with `MCP Evaluation Dual Architecture Implementation Plan` and `Task 1: `SuperstateMcpClient` Implementation & Protocol Handshake`) actually correct?**
  _`SuperstateMcpClient` has 14 INFERRED edges - model-reasoned connections that need verification._