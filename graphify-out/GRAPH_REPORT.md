# Graph Report - superstate-eval  (2026-09-19)

## Corpus Check
- 221 files · ~757,724 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 58 file(s) not represented in the graph (top: .log 52, (none) 5, .lock 1)

## Summary
- 1901 nodes · 4365 edges · 121 communities (91 shown, 30 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 343 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `de21b42f`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_superstate_mcp_adapter.py
- DriverTelemetry
- AgyCliDriver
- ClaudeCliDriver
- handle
- test_ablation_runner.py
- AnswerKeyGuard
- .run
- .run_pilot
- AgentDriver
- extract_and_grade
- RunRecorder
- test_docker_integration.py
- BaseCliDriver
- SuperstateMcpAdapter
- test_differential.py
- test_runner.py
- SuperstateDaemonAdapter
- test_superstate_daemon_adapter.py
- BudgetPolicy
- pathlib
- test_generic_rules.py
- test_in_container_driver.py
- eval_offline_review.py
- Feature Implementation Plan
- Design Specification: Autonomous TDD DAG Execution & Hand-Authored Fixture Elimination
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
- pytest
- pilot.py
- test_approval.py
- AgentImageBuilder
- Superstate Resilience, Diagnostic Retry Loops, and Git Native State Tracking Design
- WorkspaceSeedError
- TaskSpec
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
- McpRpcError
- .__init__
- Global Constraints
- Superstate Massive Adoption & Founder Prestige Roadmap
- 3. Detailed Component Design
- run_weekend_benchmark.sh
- resolve_superstate_binary
- Frontier Triad Benchmark: Final Evaluation Report
- VanillaAdapter
- McpProcessError
- Global Constraints
- FakePipe
- Global Constraints
- .__exit__
- test_superstate_agent_mcp.py
- _ScriptedDriver
- test_superstate_adapter_gate_failure_stateless_retry
- launch_frontier_claude_haiku.sh
- launch_frontier_condition_b.sh
- launch_frontier_mcp_rerun.sh
- launch_frontier_triad_benchmark.sh
- launch_weekend_run.sh
- effect.py
- test_adapters.py
- agent_gate_for
- test_canary_task_set.py
- Working in superstate-eval
- Working in superstate-eval
- What the evaluation establishes
- ._init_daemon_state
- MockDriver
- superstate.py
- apply_contract
- test_runner_mounts_workspace_root_and_inits_symlink
- ImageBuildError
- unittest_mock
- AblationRunner
- compute_review_metrics
- is_unmeasurable
- test_governor_sizing.py
- run_exp060.sh
- Experiment ledger
- test_ablation_runner_default_execution_mounts_workspace_into_container
- .get_provenance
- Experiment provenance: what the 2026-09-13 benchmark actually ran
- harvest_run_diffs.py
- gate_derivation_enabled
- ignore_gate_fixtures
- launch_derived_gates.sh
- run_exp058_canary.sh
- run_exp059_canary.sh
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
- run_exp062_core.sh
- run_exp063_canary.sh
- run_exp064_canary.sh

## God Nodes (most connected - your core abstractions)
1. `TaskSpec` - 123 edges
2. `DriverTelemetry` - 86 edges
3. `SuperstateAdapter` - 83 edges
4. `SuperstateDaemonAdapter` - 70 edges
5. `SuperstateMcpClient` - 68 edges
6. `AgentDriver` - 55 edges
7. `AblationRunner` - 53 edges
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

## Communities (121 total, 30 thin omitted)

### Community 0 - "test_superstate_mcp_adapter.py"
Cohesion: 0.13
Nodes (26): _init_git_repo(), _make_dummy_task(), MockDriver, Any, MonkeyPatch, Path, Tests for SuperstateMcpAdapter. Tests the harness-level MCP adapter for state…, Verify setup_workspace strips legacy files and excludes harness artifacts. (+18 more)

### Community 1 - "DriverTelemetry"
Cohesion: 0.12
Nodes (40): 2. Core Objectives, DriverTelemetry, Outcome and telemetry metrics from a single driver invocation turn., _make_dummy_task(), MockDriver, Any, parametrize, Path (+32 more)

### Community 2 - "AgyCliDriver"
Cohesion: 0.07
Nodes (53): Antigravity CLI Driver (`AgyCliDriver`) Implementation Plan, Global Constraints, Task 1: Implement `AgyCliDriver` Core and Container Execution Bridge, Task 2: Verify Baseline and System Integration, Task 3: Execute Live Single-Task Smoke Run, 1. Executive Summary & Context, 3.1 Class Definition (`lab/engine/drivers/agy_cli.py`), 3.2 CLI Binary Resolution (+45 more)

### Community 3 - "ClaudeCliDriver"
Cohesion: 0.11
Nodes (39): ClaudeCliDriver, ClaudeCliDriverError, estimate_cost_usd(), find_superstate_binary(), _first(), Any, Path, RuntimeError (+31 more)

### Community 4 - "handle"
Cohesion: 0.13
Nodes (25): ContainerExec, _error(), handle(), log(), main(), Any, A minimal stdio MCP server exposing exactly one tool: exec in ONE container.…, Handle one JSON-RPC message. Returns a response, or None for notifications. (+17 more)

### Community 5 - "test_ablation_runner.py"
Cohesion: 0.12
Nodes (35): Any, Auditable execution telemetry across an evaluation unit., RunTelemetry, compute_control_plane_lift(), _failure_signature(), generate_comparison_summary(), _harness_of(), Any (+27 more)

### Community 6 - "AnswerKeyGuard"
Cohesion: 0.07
Nodes (39): Concurrent Verifier Seal Resolution & 4-Worker Concurrency Plan, Task 1: TaskSpec `has_verifier_dockerfile` Seal Resilience & Test, Task 2: Concurrency 4 Configuration, Task 3: Full Verification Suite, Task 4: Commit & Merge, Task 5: Launch Benchmark Suite at Concurrency 4, 1. Overview & Objective, 2. Benchmark Task Suite: 5-Task Representative Pilot (+31 more)

### Community 7 - ".run"
Cohesion: 0.21
Nodes (10): Any, Path, Build the verifier image for `task` and return its tag., Run the held-out verifier against the collected patch. `logs_dir` must already…, Delete the verifier image so the hidden tests do not linger on the host., Run the built verifier image against the collected patch., Docker tags allow a restricted character set; task ids do not., Read reward.json, falling back to the reward.txt crash sentinel. Returns… (+2 more)

### Community 8 - ".run_pilot"
Cohesion: 0.20
Nodes (7): MockContainer, PilotMockDriver, Any, Path, Execute task across arms and return structured benchmark outcomes. With…, Predictable mock driver simulating agent behavior for pilot verification., Mock container for testing evaluation extractors without live Docker.

### Community 9 - "AgentDriver"
Cohesion: 0.10
Nodes (22): abc, AgentDriver, is_transient_stream_interruption(), Any, BudgetHook, Path, Base interfaces and data structures for execution adapters and agent drivers., Run an agent session or turn within the target workspace. (+14 more)

### Community 10 - "extract_and_grade"
Cohesion: 0.05
Nodes (61): Global Constraints, Task 1: Extend EvaluationResult and Implement compute_test_metrics, Task 2: Integrate Test Metrics into Runner Telemetry and CLI Output, Test Pass Fraction & Test Statistics Implementation Plan, 1. Context & Motivation, 2.1 EvaluationResult Dataclass Extension, 2.2 Metric Extraction Helper, 2.3 AblationRunner Telemetry Integration (+53 more)

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
Cohesion: 0.10
Nodes (22): Any, BudgetHook, Path, Keep harness files from dirtying the tree that git verification gates inspect., Sanitize workspace by stripping legacy guidance and excluding harness artifacts., Resolve active worktree path from state.json if provisioned., Strip a host-side bridge wrapper when the gate already runs in the sandbox., Execute a milestone verification command on the host or inside a container. (+14 more)

### Community 15 - "test_differential.py"
Cohesion: 0.16
Nodes (19): deepdiff, tempfile, check_binaries(), normalize_state(), fixture, Path, Differential parity testing between superstate (Rust) and agent-rules (Python).…, Resolve a binary from env, then PATH (only if a name is given), then fallbacks.… (+11 more)

### Community 16 - "test_runner.py"
Cohesion: 0.15
Nodes (22): EvaluationResult, Outcome of blind verification and patch extraction., MockDriver, Any, Path, Tests for AblationRunner telemetry and metrics integration. Validates that…, Verify fallback to 1.0 pass fraction when verifier stats are None and task…, Verify fallback to 0.0 pass fraction when verifier stats are None and task… (+14 more)

### Community 17 - "SuperstateDaemonAdapter"
Cohesion: 0.10
Nodes (25): is_pid_alive(), Any, BudgetHook, Path, Alias method to execute for cross-agent benchmark harness runner., Check if process with given PID is alive., Adapter executing tasks autonomously via the detached Superstate DaemonRunner., Name of the evaluation arm. (+17 more)

### Community 18 - "test_superstate_daemon_adapter.py"
Cohesion: 0.09
Nodes (39): Path, Driver stub returning a canned gate proposal., A gate that passes before any work cannot discriminate, so it must be refused.…, The driver must never gate on /tests/ -- that is the answer key., The daemon expands the bare `agy` preset without --model or JSON output.…, The daemon's worker must be told where the project environment actually is. The…, Gate authoring must not be capped so tightly that it silently degrades to no-…, A gate that cannot be derived must be visible in the log, not silent. (+31 more)

### Community 19 - "BudgetPolicy"
Cohesion: 0.09
Nodes (23): Task 3: Universal Progress-Earned Budget Tracker, superstate-eval Local Assessment Repository Implementation Plan, Tasks, Verification & Completion Gates, BudgetPolicy, Progress-earned budget policy and execution telemetry accounting. Allows…, Manages progress-earned execution timeouts., Record completed milestone and grant progress lease extension if within max… (+15 more)

### Community 20 - "pathlib"
Cohesion: 0.09
Nodes (44): argparse, concurrent_futures, contextlib, dataclasses, docker, docker_models_containers, hashlib, io (+36 more)

### Community 21 - "test_generic_rules.py"
Cohesion: 0.18
Nodes (16): apply_generic_rules(), contracts_enabled(), generic_rules_enabled(), Arm-specific behavioural prompt contracts, OFF by default. WHY THIS SWITCH…, Whether the portable discipline rules are injected into baseline arms. Separate…, Append the portable discipline rules to a baseline arm's prompt, if enabled., Whether arm-specific behavioural contracts are injected into agent prompts.…, The generic-rules leg tests whether execution discipline is portable off… (+8 more)

### Community 22 - "test_in_container_driver.py"
Cohesion: 0.15
Nodes (22): base64, _first(), InContainerClaudeDriver, InContainerDriverError, Any, Path, RuntimeError, Raised when the in-container agent cannot be invoked. (+14 more)

### Community 23 - "eval_offline_review.py"
Cohesion: 0.13
Nodes (24): clean_json_response(), get_task_instruction(), main(), Offline code review evaluation against harvested false-pass and true-pass runs.…, Retrieve the task instruction markdown., Extract clean JSON text from LLM response., Execute review for a single harvested run record., run_review_single() (+16 more)

### Community 24 - "Feature Implementation Plan"
Cohesion: 0.40
Nodes (4): Feature Implementation Plan, Task 1: Setup database schema, Task 2: Implement repository methods, Task 3: Expose REST endpoint

### Community 25 - "Design Specification: Autonomous TDD DAG Execution & Hand-Authored Fixture Elimination"
Cohesion: 0.13
Nodes (14): 1. Executive Summary & Context, 2.1 Milestone Specifications, 2. Architecture: Deterministic 2-Node TDD State Graph, 3.1 Arm Definition, 3.2 State Initialization (`_init_daemon_state`), 3.3 Zero Prompt Engineering Compliance, 3. Harness Integration in `superstate-eval`, 4.1 Experiment EXP-064 (+6 more)

### Community 26 - "superstate-eval"
Cohesion: 0.20
Nodes (9): A note on what this harness has taught us, Differential parity, How a run works, Layout, Quick start, superstate-eval, Tasks, What is measured (+1 more)

### Community 34 - "SuperstateAgentMcpAdapter"
Cohesion: 0.10
Nodes (20): MCP Evaluation Dual Architecture Implementation Plan, Any, BudgetHook, Path, Report state engine, transport, and autonomous tooling provenance. Returns:…, Keep harness files from dirtying the git working tree. Appends harness-internal…, Sanitize workspace by stripping legacy guidance and excluding harness…, Strip host-side bridge scripts when running verification inside the container.… (+12 more)

### Community 35 - "Design Specification: Agent-Driven Worktrees & Full-Context Turnkey Execution"
Cohesion: 0.12
Nodes (15): 1.1 `ExecutionState` Model (`crates/superstate-core/src/models.rs`), 1.2 Full-Context Turnkey Prompt (`crates/superstate-core/src/prompt.rs`), 1. Problem Statement & Motivation, 2.1 Default In-Place Execution in `state init`, 2.2 Dedicated Agent Worktree Commands, 2. Core Architectural Principles, 3.1 Universal Zero-Turn Direct Initialization, 3.2 Dynamic Turn & Milestone Execution (+7 more)

### Community 36 - "DockerManager"
Cohesion: 0.18
Nodes (12): DockerClient, DockerManager, Prune dangling images, stopped containers, and unreferenced volumes., Manages Docker containers and host disk resource reclamation., Tests for Docker Lifecycle and Disk Space Watchdog., test_check_disk_space_healthy(), test_check_disk_space_raises_on_emergency_limit(), test_check_disk_space_triggers_prune_when_below_min() (+4 more)

### Community 37 - "load_benchmark_tasks"
Cohesion: 0.17
Nodes (16): _extract_collect_commands(), load_benchmark_tasks(), load_task_from_dir(), Any, Path, Ingest collector command sequences used to extract test or run artifacts., Parse task.toml and instruction.md from task_dir into a TaskSpec., Scan directory tree for benchmark task directories containing task.toml. (+8 more)

### Community 38 - "test_superstate_mcp_client.py"
Cohesion: 0.09
Nodes (26): FakeMcpServerProcess, MonkeyPatch, Path, Tests for SuperstateMcpClient. Verifies stdio JSON-RPC MCP protocol handshake,…, Verify initialize, initialized notification, tools/list, and caching 25 tools., Verify call_tool parses text and nested json in result.content., Verify call_tool raises McpRpcError on JSON-RPC error payload., Verify context manager automatically starts and terminates child process. (+18 more)

### Community 39 - "Control-Plane Evaluation — Plan"
Cohesion: 0.13
Nodes (14): Control-Plane Evaluation — Plan, Harness defects found by running (all fixed), Parked, with reasons, Standing lesson from today, Stream 1 — Produce a credible measurement, Stream 2 — Rust parity — COMPLETE (2026-09-09), Task 1: Pin the engine explicitly and record it — DONE, Task 2: Drive the real state-engine loop — DONE (+6 more)

### Community 40 - "pytest"
Cohesion: 0.10
Nodes (27): pytest, requires_engine, MonkeyPatch, Every arm must receive the same inputs, or a comparison measures the harness.…, superstate_daemon_review must run with review blocking and without auto-…, All arms must consult GATE_FIXTURES before falling back. superstate_mcp.py was…, The `true` fallback must come AFTER the fixture lookup, not instead of it., The daemon spawns its own worker, bypassing AgyCliDriver. Each flag… (+19 more)

### Community 41 - "pilot.py"
Cohesion: 0.13
Nodes (13): Path, Adapter configuring markdown rules and vendored superpowers skills., Install markdown guidance and copy superpowers skills into workspace., Configure workspace with Superpowers guidance before execution begins., SuperpowersAdapter, PilotShowdownRunner, Pilot showdown runner executing end-to-end task runs across Vanilla,…, Executes a single benchmark task across evaluation arms with isolated… (+5 more)

### Community 42 - "test_approval.py"
Cohesion: 0.29
Nodes (9): is_waiting_for_user_input(), Analyze agent response text to detect if the agent paused for human approval or…, Tests for Mechanical User and Autonomous Human-in-the-Loop Elimination., test_is_waiting_for_user_input_detects_ask_question_tool(), test_is_waiting_for_user_input_detects_standard_approval_prompts(), test_is_waiting_for_user_input_detects_superpowers_state_gates(), test_is_waiting_for_user_input_ignores_normal_completions(), test_resolve_next_turn_prompt_returns_mechanical_approval() (+1 more)

### Community 43 - "AgentImageBuilder"
Cohesion: 0.24
Nodes (6): AgentImageBuilder, Docker tags allow a restricted character set; image refs do not., Builds and caches per-task agent images., A deterministic tag: this image holds no secrets, so caching is safe. Unlike…, Build (or reuse) an image with the Claude Code CLI on top of `base_image`., _slug()

### Community 44 - "Superstate Resilience, Diagnostic Retry Loops, and Git Native State Tracking Design"
Cohesion: 0.20
Nodes (9): 1. Context & Motivation, 2. Goals & Non-Goals, 3.1 Diagnostic Retry Loop in `lab/engine/adapters/superstate.py`, 3.2 Greenfield Git Resilience, 3. Architecture & Mechanics, 4. Verification & Testing, Goals, Non-Goals (+1 more)

### Community 45 - "WorkspaceSeedError"
Cohesion: 0.22
Nodes (8): DiskSpaceError, Path, RuntimeError, Copy the task repository out of `image` into the host directory `dest`. A bind…, Raised when host disk space falls below the critical emergency threshold., Check available disk space. Prune docker if below min_free_gb; raise if below…, Raised when the task repository cannot be materialized onto the host., WorkspaceSeedError

### Community 46 - "TaskSpec"
Cohesion: 0.14
Nodes (22): Cross-Agent Relay & Autonomous Detached Daemon Evaluation Implementation Plan, Global Constraints, Task 1: Implement `SuperstateRelayAdapter`, Task 2: Implement `SuperstateDaemonAdapter`, Task 3: Wire Adapters into Runner and Add End-to-End Harness Tests, Task 4: Automated Pilot Script & 5-Task Benchmark Execution, Specification of an evaluation benchmark task., TaskSpec (+14 more)

### Community 47 - "Global Constraints"
Cohesion: 0.25
Nodes (7): Global Constraints, Superstate Resilience and Diagnostic Retry Loop Implementation Plan, Task 1: Implement Greenfield Git Handling in `lab/engine/adapters/superstate.py`, Task 2: Implement Milestone Diagnostic Retry Loop in `lab/engine/adapters/superstate.py`, Task 3: Unit Tests for Retry Loop & Greenfield Handling, Task 4: Native Git Initialization in Rust `superstate`, Task 5: Verification & Checkpoint

### Community 48 - ".execute"
Cohesion: 0.10
Nodes (19): Any, BudgetHook, Path, Resolve active worktree path from state.json if provisioned., Report which state engine actually drove this run., Record the engine used, downgrading to the fallback if it is ever hit., Keep harness files from dirtying the tree the git-clean gate inspects. The…, Sanitize workspace so Arm C sees the same blank slate as the control arm. (+11 more)

### Community 49 - "test_superstate_resilience.py"
Cohesion: 0.31
Nodes (7): FlakyGateDriver, Path, Tests for Superstate milestone retry loops and greenfield resilience., Verify that a greenfield workspace without .git does not crash when advancing…, Fails on turn 1 by not creating marker.txt, then creates it on turn 2 after…, test_greenfield_workspace_advances_without_git(), test_milestone_retry_loop_on_failed_gate()

### Community 50 - "ConcurrencyGovernor"
Cohesion: 0.07
Nodes (36): Concurrent Evaluation Isolation & Universal Progress Budgeting Implementation Plan, Proposed File Changes, Task 1: Dynamic Machine-Aware Concurrency Governor, Task 4: Blind Extraction & Verification Pipeline, Task 5: End-to-End Concurrent Runner & Integration, 1. Executive Summary & Goals, 2. Dynamic Concurrency Governor, 3. Strict Docker Sandbox Quotas & Volume Isolation (+28 more)

### Community 51 - "SuperstateMcpClient"
Cohesion: 0.11
Nodes (27): Task 1: `SuperstateMcpClient` Implementation & Protocol Handshake, Task 2: Harness-Level Adapter (`SuperstateMcpAdapter`), Execution Flow:, Ledger, Any, Path, Client for communicating with the superstate MCP server over stdio JSON-RPC.…, Return cached map of discovered tools keyed by name. (+19 more)

### Community 52 - "SuperstateAdapter"
Cohesion: 0.23
Nodes (12): Adapter executing tasks under the deterministic Superstate engine., Extract a clean, concise finding from the turn's response to keep prompts…, Strip a host-side bridge wrapper when the gate already runs in the sandbox., SuperstateAdapter, Path, test_switch_container_workspace_handles_exec_nonzero_exit(), test_switch_container_workspace_handles_none_container(), test_switch_container_workspace_no_worktree_mode() (+4 more)

### Community 53 - "test_agent_failure_is_diagnosed_before_the_grading_symptom"
Cohesion: 0.25
Nodes (5): A result from a driver with a host shell carries a weaker guarantee. It must…, An agent that times out leaves a bad patch; the timeout is the cause. Reporting…, test_agent_failure_is_diagnosed_before_the_grading_symptom(), test_run_telemetry_records_whether_execution_was_isolated(), fake_sandbox()

### Community 54 - "HeldOutVerifier"
Cohesion: 0.30
Nodes (13): 3.1 `SuperstateRelayAdapter` (`lab/engine/adapters/superstate_relay.py`), 3.2 `SuperstateDaemonAdapter` (`lab/engine/adapters/superstate_daemon.py`), 3. Architecture & Adapter Specifications, HeldOutVerifier, Builds and runs the task's own verifier image., _manager(), Path, The verifier image is the held-out answer key; it must not linger on the host. (+5 more)

### Community 55 - ".run_sandbox"
Cohesion: 0.20
Nodes (8): Container, Task 2: Container Resource Constraints & Volume Isolation, Dynamic Container Workspace Switching Implementation Plan, Global Constraints, Task 1: Runner Mount Decoupling & Container Symlink Setup, Task 2: Worktree Turn Repointing in Superstate Adapter, Task 3: Live Verification on `db-wal-recovery`, Run a container with guaranteed teardown upon context exit. Guarantees that the…

### Community 56 - "Design Spec: Dynamic Container Workspace Switching for Worktree Isolation"
Cohesion: 0.33
Nodes (5): 1. Problem Statement, 2. Proposed Architecture, 3. Benefits & Performance, Design Spec: Dynamic Container Workspace Switching for Worktree Isolation, Dynamic `/app` Symlink via `/workspace_root` Mount

### Community 57 - "McpRpcError"
Cohesion: 0.22
Nodes (12): 3.1 `SuperstateMcpClient` (`lab/engine/mcp/client.py`), Responsibilities:, Exception, McpError, McpRpcError, McpTimeoutError, Base exception for all MCP client errors., Raised when the MCP server returns a JSON-RPC error response. (+4 more)

### Community 58 - ".__init__"
Cohesion: 0.15
Nodes (12): advisory_review_enabled(), auto_rollback_enabled(), Whether code review blocks advancement when Critical/High issues are found., Whether automatic rollback on milestone failure is enabled for the daemon., Initialize SuperstateDaemonAdapter with driver preset and polling configuration., Whether advisory code review is enabled for the daemon., review_blocking_enabled(), MonkeyPatch (+4 more)

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

### Community 65 - "VanillaAdapter"
Cohesion: 0.18
Nodes (9): Path, Unguided baseline adapter enforcing complete isolation from rules or skills., Sanitize workspace by removing all guidance, rule files, and skills., Ensure pristine unguided workspace before execution., VanillaAdapter, test_adapter_passes_container_handle_to_driver(), test_production_turn_caps_do_not_bind_on_ordinary_runs(), test_turn_loop_breaker_reports_failure() (+1 more)

### Community 66 - "McpProcessError"
Cohesion: 0.17
Nodes (9): McpProcessError, Start the MCP server when entering the context block., Spawn the superstate mcp process and execute protocol handshake. Raises:…, Execute standard MCP initialization handshake and populate tool cache., Send a JSON-RPC notification message without awaiting reply., Send a JSON-RPC request and wait for the corresponding response. Parameters:…, Read a single line from stdout with a timeout deadline. Parameters: deadline:…, Read lines from stdout until receiving the matching JSON-RPC response. Filters… (+1 more)

### Community 67 - "Global Constraints"
Cohesion: 0.22
Nodes (8): Global Constraints, Superstate Massive Adoption & Founder Prestige Implementation Plan, Task 1: Prebuilt Multi-Platform Binary Releases & Homebrew Tap Setup, Task 2: Interactive `superstate init` Repository Wizard, Task 3: MCP Registry & Smithery Integration Metadata, Task 4: Empirical Technical Whitepaper & Academic Preprint, Task 5: Launch Campaign Package (Show HN, Viral X Thread, Video Script), Task 6: Turnkey GitHub Action (`superstate/action@v1`)

### Community 68 - "FakePipe"
Cohesion: 0.22
Nodes (3): FakePipe, Any, Mock file-like pipe supporting write and readline.

### Community 69 - "Global Constraints"
Cohesion: 0.67
Nodes (3): Global Constraints, Task 3: Driver MCP Support & Agent-Level Autonomous Adapter, Task 4: Runner Integration & Benchmark Parity Verification

### Community 70 - ".__exit__"
Cohesion: 0.40
Nodes (3): BaseException, Terminate the server process cleanly upon exiting context., Cleanly terminate the superstate child process and close pipes.

### Community 71 - "test_superstate_agent_mcp.py"
Cohesion: 0.11
Nodes (30): _init_git_repo(), _make_dummy_task(), MockDriver, Any, MonkeyPatch, Path, Tests for SuperstateAgentMcpAdapter. Tests the agent-level autonomous MCP…, Verify setup_workspace strips legacy files and excludes harness artifacts. (+22 more)

### Community 72 - "_ScriptedDriver"
Cohesion: 0.17
Nodes (9): SimpleNamespace, Driver stub returning a different response per successive turn., An incomplete gate is worse than no gate: the worker stops the moment it…, A critique may only strengthen the contract. A no-op reply keeps the original., A widened gate that already passes cannot discriminate, so the original stands., _ScriptedDriver, test_critique_cannot_weaken_the_gate(), test_critique_rejecting_an_already_passing_gate() (+1 more)

### Community 79 - "effect.py"
Cohesion: 0.08
Nodes (32): collections, itertools, random, bootstrap_ci(), collect(), _infra_failure(), main(), permutation_p() (+24 more)

### Community 80 - "test_adapters.py"
Cohesion: 0.11
Nodes (18): _extract_plan_milestones(), flush(), find_superstate_binary(), Resolve the state-engine binary for a named implementation. Resolution is…, Extract milestone headers and their targeted verification commands from a plan., Tests for Evaluation Arm Adapters: Vanilla, Superpowers, and Superstate., Regression from the first live run. The agy driver hands the agent `./run-in-…, Verify AblationRunner resolves superstate_mcp and superstate_agent_mcp adapters. (+10 more)

### Community 81 - "agent_gate_for"
Cohesion: 0.09
Nodes (22): Arm input parity — the single most common source of false findings, Gated vs ungated — why it decides what a run measures, Terminology — use these exact words, agent_gate_for(), Whether a command reads the sealed held-out grader at the container root., Return the hand-authored agent-facing gate for a task, if one exists. This is…, references_sealed_grader(), image_present() (+14 more)

### Community 82 - "test_canary_task_set.py"
Cohesion: 0.09
Nodes (26): ArgumentParser, excluded_reason(), is_canary(), is_discriminating(), Which tasks a comparison should actually run. The 30-task corpus does not…, Whether a task can contribute signal to an arm-vs-arm comparison., Why a gradeable task is kept out of the core set, or None if it is in., Whether a task belongs to the fast 3-task Canary slice. (+18 more)

### Community 83 - "Working in superstate-eval"
Cohesion: 0.12
Nodes (16): A bad gate is worse than no gate, Arms — check the name before comparing anything, Before running anything: check the ledger, Do not run `vanilla` by default, Drivers, Gate precision — read it after every run, Python environment, Run `--core`, not the whole corpus (+8 more)

### Community 84 - "Working in superstate-eval"
Cohesion: 0.12
Nodes (16): A bad gate is worse than no gate, Arms — check the name before comparing anything, Before running anything: check the ledger, Do not run `vanilla` by default, Drivers, Gate precision — read it after every run, Python environment, Run `--core`, not the whole corpus (+8 more)

### Community 85 - "What the evaluation establishes"
Cohesion: 0.11
Nodes (18): 10. The +20pp routing lift was an in-sample artifact, 1. The effect is real, and its size is +19pp, 2. The mechanism is the handoff prompt, not the control loop, 3. The daemon is a legitimate default, 4. The loop does fire — on hard enough tasks, 5. The benchmark corpus is a third the size it appears, 6. Nothing in superstate builds the gate, 7. The gate is not an eval convention — it is ours (+10 more)

### Community 86 - "._init_daemon_state"
Cohesion: 0.22
Nodes (7): Autonomous TDD DAG Execution Implementation Plan, Global Constraints, Task 1: Add `tdd_dag` Configuration and 2-Node DAG Construction in `SuperstateDaemonAdapter`, Task 2: Register `superstate_daemon_dag` Arm and Verify Parity, Task 3: Register and Execute EXP-064 Canary Benchmark, Construct a deterministic 2-node TDD dependency graph for the task. Milestone 1…, Initialize state machine tracking via MCP superstate_handoff or CLI fallback.

### Community 87 - "MockDriver"
Cohesion: 0.12
Nodes (15): MockDriver, Any, Mock agent driver for testing., When auto_rollback is True, --auto-rollback is appended to the daemon spawn…, When auto_rollback is False, --no-auto-rollback is appended to the daemon spawn…, _spawn_daemon includes --auto-rollback or --no-auto-rollback in subprocess.run…, tdd_dag flag initializes correctly and appears in provenance., _build_tdd_milestones creates a valid 2-node TDD dependency graph. (+7 more)

### Community 88 - "superstate.py"
Cohesion: 0.10
Nodes (26): Hand-authored agent-facing verification gates, one per benchmark task. WHY…, Agent-level autonomous adapter for Superstate over Model Context Protocol…, Harness-level adapter for Superstate orchestration over stdio JSON-RPC MCP.…, Persist a milestone attempt and its gate verdict if tracing is enabled., Milestone, Arm C: Superstate (Deterministic State Engine) Adapter. Executes milestone DAGs…, A single plan milestone and its targeted verification gate., Mechanical User and Autonomous Human-in-the-Loop Interceptor. Prevents… (+18 more)

### Community 89 - "apply_contract"
Cohesion: 0.24
Nodes (9): apply_contract(), Append an arm-specific behavioural contract, if the switch is on. Returns the…, The default measurement must contain no arm-specific prompt engineering., The thesis is that managing state produces the gain, so nothing else may…, Preserved, not deleted -- reproducing historical runs must remain possible., Every injection must route through the switch, or the default silently leaks., test_contracts_are_off_by_default(), test_contracts_can_be_re_enabled_explicitly() (+1 more)

### Community 90 - "test_runner_mounts_workspace_root_and_inits_symlink"
Cohesion: 0.33
Nodes (5): Path, test_agy_cli_driver_run_in_container_sets_workdir(), test_runner_mounts_workspace_root_and_inits_symlink(), fake_run_sandbox(), run()

### Community 91 - "ImageBuildError"
Cohesion: 0.29
Nodes (5): ImageBuildError, Build an image from `context_dir` and return its tag. Used for the held-out…, Build an image from an inline Dockerfile with no build context., Stop docker-py invoking every configured credential helper on build. docker-py…, Raised when an image (typically the held-out verifier) cannot be built.

### Community 92 - "unittest_mock"
Cohesion: 0.33
Nodes (5): Tests for Concurrent Execution Runner with Dynamic Concurrency Governor., test_ablation_runner_universal_lease_extension(), fake_executor(), test_run_cohort_concurrency_governor_dispatch(), unittest_mock

### Community 93 - "AblationRunner"
Cohesion: 0.10
Nodes (20): AblationRunner, InsufficientResourcesError, Any, Resolve a cohort entry into (task_id, image, base_budget_sec, task_spec)., Execute a matrix of tasks x arms concurrently using the dynamic governor., Raised when the host cannot safely run even a single concurrent evaluation., Executes benchmark tasks across evaluation arms with resource and lease…, main() (+12 more)

### Community 94 - "compute_review_metrics"
Cohesion: 0.40
Nodes (5): compute_review_metrics(), Any, Compute aggregate precision, recall, and false alarm rate from review results., Test calculation of bug recall, false alarm rate, and precision., test_compute_review_metrics()

### Community 95 - "is_unmeasurable"
Cohesion: 0.20
Nodes (10): A task with no sealed grader cannot be scored, is_unmeasurable(), Reason a task cannot be scored, or None if it can., A task whose grader cannot run scores every arm zero and shrinks the…, A task with no held-out tests/ cannot be scored, so it must be listed. The…, test_tasks_without_a_sealed_grader_are_marked_unmeasurable(), test_unmeasurable_tasks_are_documented_with_a_reason(), A task with no held-out grader cannot contribute signal, only self-grading.… (+2 more)

### Community 96 - "test_governor_sizing.py"
Cohesion: 0.25
Nodes (7): A worker must be sized from what the tasks declare, not from a constant., Sizing depends on memory_mb being present; without it the fix silently reverts., The flat 1.5 GB assumption advertised a ceiling the machine could not honour.…, Over-subscription must fail loudly, not silently record starved workers as…, test_heavier_tasks_lower_the_concurrency_ceiling(), test_paired_run_refuses_to_oversubscribe(), test_tasks_declare_their_memory_requirement()

### Community 97 - "run_exp060.sh"
Cohesion: 0.40
Nodes (4): run_exp060.sh script, SUPERSTATE_EVAL_DERIVE_GATES, SUPERSTATE_EVAL_GENERIC_RULES, SUPERSTATE_EVAL_PROMPT_CONTRACTS

### Community 98 - "Experiment ledger"
Cohesion: 0.25
Nodes (4): Cross-cutting findings, Experiment ledger, Rules, Status values

### Community 99 - "test_ablation_runner_default_execution_mounts_workspace_into_container"
Cohesion: 0.40
Nodes (4): _fake_sandbox_factory(), Build a run_sandbox stand-in that writes a passing verifier artifact., test_ablation_runner_default_execution_mounts_workspace_into_container(), run()

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
Cohesion: 0.17
Nodes (9): ignore_gate_fixtures(), Whether to skip the hand-authored fixture so the driver must author the gate.…, derivation_on(), fixture, The daemon arm must resolve the Rust engine, which is the only one with `state…, Gate derivation is opt-in: the daemon does not author its own contract by…, Gate authorship cannot be measured while a fixture exists for every task.…, test_daemon_resolves_rust_engine_not_python() (+1 more)

### Community 105 - "launch_derived_gates.sh"
Cohesion: 0.50
Nodes (3): launch_derived_gates.sh script, SUPERSTATE_EVAL_DERIVE_GATES, SUPERSTATE_EVAL_IGNORE_GATE_FIXTURES

## Knowledge Gaps
- **171 isolated node(s):** `superstate-eval`, `launch_datacurve_3arm.sh script`, `launch_datacurve_clean.sh script`, `launch_datacurve_planned.sh script`, `launch_derived_gates.sh script` (+166 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 837 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **30 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TaskSpec` connect `TaskSpec` to `test_superstate_mcp_adapter.py`, `DriverTelemetry`, `AgyCliDriver`, `ClaudeCliDriver`, `test_ablation_runner.py`, `AnswerKeyGuard`, `.run_pilot`, `AgentDriver`, `extract_and_grade`, `BaseCliDriver`, `SuperstateMcpAdapter`, `test_runner.py`, `SuperstateDaemonAdapter`, `test_superstate_daemon_adapter.py`, `pathlib`, `test_generic_rules.py`, `test_in_container_driver.py`, `SuperstateAgentMcpAdapter`, `load_benchmark_tasks`, `Control-Plane Evaluation — Plan`, `pytest`, `pilot.py`, `.execute`, `test_superstate_resilience.py`, `SuperstateAdapter`, `test_agent_failure_is_diagnosed_before_the_grading_symptom`, `test_superstate_agent_mcp.py`, `test_adapters.py`, `._init_daemon_state`, `MockDriver`, `superstate.py`, `AblationRunner`, `test_ablation_runner_default_execution_mounts_workspace_into_container`?**
  _High betweenness centrality (0.206) - this node is a cross-community bridge._
- **Why does `SuperstateMcpClient` connect `SuperstateMcpClient` to `test_superstate_mcp_adapter.py`, `SuperstateAgentMcpAdapter`, `McpProcessError`, `Global Constraints`, `.__exit__`, `test_superstate_agent_mcp.py`, `test_superstate_mcp_client.py`, `.is_running`, `SuperstateMcpAdapter`, `SuperstateDaemonAdapter`, `pathlib`, `._init_daemon_state`, `superstate.py`, `McpRpcError`, `3. Detailed Component Design`, `resolve_superstate_binary`?**
  _High betweenness centrality (0.102) - this node is a cross-community bridge._
- **Why does `SuperstateDaemonAdapter` connect `SuperstateDaemonAdapter` to `_ScriptedDriver`, `AgentDriver`, `ignore_gate_fixtures`, `TaskSpec`, `test_adapters.py`, `test_superstate_daemon_adapter.py`, `SuperstateMcpClient`, `pathlib`, `HeldOutVerifier`, `._init_daemon_state`, `superstate.py`, `MockDriver`, `.__init__`, `AblationRunner`?**
  _High betweenness centrality (0.072) - this node is a cross-community bridge._
- **Are the 31 inferred relationships involving `TaskSpec` (e.g. with `Stream 2 — Rust parity — COMPLETE (2026-09-09)` and `Task 1: TaskSpec `has_verifier_dockerfile` Seal Resilience & Test`) actually correct?**
  _`TaskSpec` has 31 INFERRED edges - model-reasoned connections that need verification._
- **Are the 16 inferred relationships involving `DriverTelemetry` (e.g. with `Task 1: Implement `SuperstateRelayAdapter`` and `2. Core Objectives`) actually correct?**
  _`DriverTelemetry` has 16 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `SuperstateAdapter` (e.g. with `Task 3: Universal Zero-Turn Planning in Adapter (`superstate-eval`)` and `2. Core Objectives`) actually correct?**
  _`SuperstateAdapter` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `SuperstateDaemonAdapter` (e.g. with `Cross-Agent Relay & Autonomous Detached Daemon Evaluation Implementation Plan` and `Task 2: Implement `SuperstateDaemonAdapter``) actually correct?**
  _`SuperstateDaemonAdapter` has 11 INFERRED edges - model-reasoned connections that need verification._