# Graph Report - feat-eval-philosophy-autonomous-tdd  (2026-09-20)

## Corpus Check
- 238 files · ~771,555 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 61 file(s) not represented in the graph (top: .log 52, (none) 6, .diff 2)

## Summary
- 2077 nodes · 4591 edges · 147 communities (114 shown, 33 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 355 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d4e930b6`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- extract_and_grade
- pathlib
- SuperstateAgentMcpAdapter
- ConcurrencyGovernor
- ClaudeCliDriver
- DriverTelemetry
- AnswerKeyGuard
- SuperstateDaemonAdapter
- test_superstate_daemon_adapter.py
- .execute
- AgentDriver
- .call_tool
- SuperstateMcpAdapter
- test_superstate_mcp_adapter.py
- test_canary_task_set.py
- handle
- load_benchmark_tasks
- BudgetPolicy
- test_superstate_mcp_client.py
- test_offline_review.py
- AblationRunner
- DockerManager
- Working in superstate-eval
- docker_manager.py
- test_ablation_runner.py
- FakeMcpServerProcess
- Working in superstate-eval
- .__init__
- test_runner.py
- SuperstateMcpClient
- test_docker_integration.py
- test_differential.py
- SuperstateRelayAdapter
- MockDriver
- test_adapters.py
- .run_sandbox
- TaskSpec
- TurnBasedAdapter
- .execute
- SuperstateAdapter
- RunRecorder
- test_agy_cli_driver.py
- test_container_bridge.py
- test_in_container_driver.py
- What the evaluation establishes
- effect.py
- BaseCliDriver
- reporter.py
- pytest
- Design Specification: Agent-Driven Worktrees & Full-Context Turnkey Execution
- SuperpowersAdapter
- test_arm_input_parity.py
- Control-Plane Evaluation — Plan
- .run
- Superstate Massive Adoption & Founder Prestige Roadmap
- HeldOutVerifier
- Design Specification: Autonomous TDD DAG Execution & Hand-Authored Fixture Elimination
- Design Specification: Evaluation Philosophy & Autonomous TDD Benchmark Architecture
- test_gate_fixtures.py
- Hybrid Tool Output Shunting & Distillation Design Spec
- resolve_next_turn_prompt
- test_generic_rules.py
- .run
- test_state_engine_loop.py
- AgyCliDriver
- AgyCliDriverError
- agent_image.py
- .run_pilot
- VanillaAdapter
- _ScriptedDriver
- eval_routing_split.py
- Design Specification: Repository-First Software Engineering Benchmarks
- Superstate Evaluation Philosophy & Benchmark Integrity Manifesto
- Task 2 Brief: In-Container Static Linux Binary Mounting
- Frontier Triad Benchmark: Final Evaluation Report
- Superstate Resilience, Diagnostic Retry Loops, and Git Native State Tracking Design
- 3. Detailed Component Design
- test_condition_b.py
- ._perform_handshake
- test_prompt_contracts.py
- superstate-eval
- experiments.py
- Global Constraints
- TDD Verification Lifecycle
- .run
- FakePipe
- Global Constraints
- Global Constraints
- 4. Corpus Audit: FrontierHarness Eval Classification
- estimate_cost_usd
- test_agent_failure_is_diagnosed_before_the_grading_symptom
- FlakyGateDriver
- pilot_run.py
- Tasks
- Global Constraints
- Global Constraints
- 2. The Core Evaluation Philosophy
- Experiment provenance: what the 2026-09-13 benchmark actually ran
- Design Spec: Dynamic Container Workspace Switching for Worktree Isolation
- 2. The Five Mandatory Task Qualification Requirements
- ._send_request
- harvest_run_diffs.py
- test_runner_mounts_workspace_root_and_inits_symlink
- test_domain_wrapper_methods
- Experiment ledger
- InsufficientResourcesError
- Feature Implementation Plan
- run_exp060.sh
- test_tasks_without_a_sealed_grader_are_marked_unmeasurable
- gate_derivation_enabled
- ignore_gate_fixtures
- launch_derived_gates.sh
- The short version
- .__init__
- run_exp058_canary.sh
- run_exp065_canary.sh
- run_weekend_benchmark.sh
- _fake_sandbox_factory
- derivation_on
- benchmarks/__init__.py
- estimate_cost_usd
- _failure_signature
- dag_plan.md
- launch_datacurve_3arm.sh
- launch_datacurve_clean.sh
- launch_datacurve_planned.sh
- launch_frontier_claude_haiku.sh
- launch_frontier_condition_b.sh
- launch_frontier_handoff_pilot.sh
- launch_frontier_mcp_rerun.sh
- launch_frontier_triad_benchmark.sh
- launch_gates_v2.sh
- launch_weekend_run.sh
- run_canary.sh
- run_exp056.sh
- run_exp057.sh
- run_exp059_canary.sh
- run_exp062_core.sh
- run_exp063_canary.sh
- run_exp064_canary.sh
- test_daemon_resolves_rust_engine_not_python
- superstate-eval

## God Nodes (most connected - your core abstractions)
1. `TaskSpec` - 121 edges
2. `DriverTelemetry` - 86 edges
3. `SuperstateAdapter` - 83 edges
4. `SuperstateDaemonAdapter` - 69 edges
5. `SuperstateMcpClient` - 68 edges
6. `AgentDriver` - 55 edges
7. `AblationRunner` - 50 edges
8. `SuperstateMcpAdapter` - 47 edges
9. `AgyCliDriver` - 47 edges
10. `DockerManager` - 44 edges

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

## Communities (147 total, 33 thin omitted)

### Community 0 - "extract_and_grade"
Cohesion: 0.06
Nodes (58): Global Constraints, Task 1: Extend EvaluationResult and Implement compute_test_metrics, Task 2: Integrate Test Metrics into Runner Telemetry and CLI Output, Test Pass Fraction & Test Statistics Implementation Plan, 1. Context & Motivation, 2.1 EvaluationResult Dataclass Extension, 2.2 Metric Extraction Helper, 2.3 AblationRunner Telemetry Integration (+50 more)

### Community 1 - "pathlib"
Cohesion: 0.11
Nodes (36): abc, concurrent_futures, contextlib, dataclasses, json, Benchmark task specification and loader module. Parses SWE-bench / Harbor style…, lab_engine_adapters, Base interfaces and data structures for execution adapters and agent drivers. (+28 more)

### Community 2 - "SuperstateAgentMcpAdapter"
Cohesion: 0.08
Nodes (39): Strip host-side bridge scripts when running verification inside the container.…, Adapter evaluating autonomous agent behavior with direct Superstate MCP tooling., Initialize the autonomous Superstate MCP adapter configuration. Parameters:…, Name of the evaluation arm., SuperstateAgentMcpAdapter, Verify Superstate MCP adapters export from lab.engine.adapters and provenance…, test_mcp_adapters_exported_and_provenance_properties(), _init_git_repo() (+31 more)

### Community 3 - "ConcurrencyGovernor"
Cohesion: 0.06
Nodes (38): Concurrent Evaluation Isolation & Universal Progress Budgeting Implementation Plan, Proposed File Changes, Task 1: Dynamic Machine-Aware Concurrency Governor, Task 4: Blind Extraction & Verification Pipeline, Task 5: End-to-End Concurrent Runner & Integration, 1. Executive Summary & Goals, 2. Dynamic Concurrency Governor, 3. Strict Docker Sandbox Quotas & Volume Isolation (+30 more)

### Community 4 - "ClaudeCliDriver"
Cohesion: 0.11
Nodes (37): Name of the evaluation arm., ClaudeCliDriver, ClaudeCliDriverError, estimate_cost_usd(), _first(), Any, Path, RuntimeError (+29 more)

### Community 5 - "DriverTelemetry"
Cohesion: 0.12
Nodes (39): 2. Core Objectives, DriverTelemetry, Outcome and telemetry metrics from a single driver invocation turn., _make_dummy_task(), MockDriver, Any, parametrize, Path (+31 more)

### Community 6 - "AnswerKeyGuard"
Cohesion: 0.10
Nodes (32): 1. Overview & Objective, 2. Benchmark Task Suite: 5-Task Representative Pilot, 4. Quantitative Metrics & Reporting, 5. Security & Isolation Invariants, Design Specification: Cross-Agent Relay & Autonomous Detached Daemon Evaluation, Evaluation Arms Under Test, AnswerKeyGuard, is_readable() (+24 more)

### Community 7 - "SuperstateDaemonAdapter"
Cohesion: 0.10
Nodes (25): is_pid_alive(), Any, BudgetHook, Path, Check if process with given PID is alive., Adapter executing tasks autonomously via the detached Superstate DaemonRunner., Name of the evaluation arm., Report execution provenance metadata. (+17 more)

### Community 8 - "test_superstate_daemon_adapter.py"
Cohesion: 0.09
Nodes (39): Path, Driver stub returning a canned gate proposal., A gate that passes before any work cannot discriminate, so it must be refused.…, The driver must never gate on /tests/ -- that is the answer key., The daemon expands the bare `agy` preset without --model or JSON output.…, The daemon's worker must be told where the project environment actually is. The…, Gate authoring must not be capped so tightly that it silently degrades to no-…, A gate that cannot be derived must be visible in the log, not silent. (+31 more)

### Community 9 - ".execute"
Cohesion: 0.09
Nodes (24): _extract_plan_milestones(), flush(), Milestone, Any, BudgetHook, Path, Extract milestone headers and their targeted verification commands from a plan., Resolve active worktree path from state.json if provisioned. (+16 more)

### Community 10 - "AgentDriver"
Cohesion: 0.12
Nodes (30): Task 1: Implement `SuperstateRelayAdapter`, Task 2: Implement `SuperstateDaemonAdapter`, agent_gate_for(), Hand-authored agent-facing verification gates, one per benchmark task. WHY…, Whether a command reads the sealed held-out grader at the container root., Return the hand-authored agent-facing gate for a task, if one exists. This is…, references_sealed_grader(), AgentAdapter (+22 more)

### Community 11 - ".call_tool"
Cohesion: 0.12
Nodes (21): Task 1: `SuperstateMcpClient` Implementation & Protocol Handshake, Execution Flow:, Ledger, Any, Path, Invoke an MCP tool and parse both text and structured JSON content. Parameters:…, Resolve a repo path or direct state file path into a state argument string., Invoke CLI binary fallback for low-level state mutation commands. (+13 more)

### Community 12 - "SuperstateMcpAdapter"
Cohesion: 0.10
Nodes (21): Any, BudgetHook, Path, Keep harness files from dirtying the tree that git verification gates inspect., Sanitize workspace by stripping legacy guidance and excluding harness artifacts., Resolve active worktree path from state.json if provisioned., Strip a host-side bridge wrapper when the gate already runs in the sandbox., Execute a milestone verification command on the host or inside a container. (+13 more)

### Community 13 - "test_superstate_mcp_adapter.py"
Cohesion: 0.12
Nodes (28): _init_git_repo(), _make_dummy_task(), MockDriver, Any, MonkeyPatch, Path, Tests for SuperstateMcpAdapter. Tests the harness-level MCP adapter for state…, Verify default parameters and provenance initial structure. (+20 more)

### Community 14 - "test_canary_task_set.py"
Cohesion: 0.08
Nodes (30): ArgumentParser, is_unmeasurable(), Reason a task cannot be scored, or None if it can., excluded_reason(), is_canary(), is_discriminating(), Which tasks a comparison should actually run. The 30-task corpus does not…, Whether a task can contribute signal to an arm-vs-arm comparison. (+22 more)

### Community 15 - "handle"
Cohesion: 0.13
Nodes (25): ContainerExec, _error(), handle(), log(), main(), Any, A minimal stdio MCP server exposing exactly one tool: exec in ONE container.…, Handle one JSON-RPC message. Returns a response, or None for notifications. (+17 more)

### Community 16 - "load_benchmark_tasks"
Cohesion: 0.10
Nodes (24): _extract_collect_commands(), load_benchmark_tasks(), load_task_from_dir(), Any, Path, Ingest collector command sequences used to extract test or run artifacts., Parse task.toml and instruction.md from task_dir into a TaskSpec., Scan directory tree for benchmark task directories containing task.toml. (+16 more)

### Community 17 - "BudgetPolicy"
Cohesion: 0.11
Nodes (20): Task 3: Universal Progress-Earned Budget Tracker, BudgetPolicy, Progress-earned budget policy and execution telemetry accounting. Allows…, Manages progress-earned execution timeouts., Record completed milestone and grant progress lease extension if within max…, ProgressTracker, Path, Monitors workspace state and awards progress-earned lease extensions to any arm. (+12 more)

### Community 18 - "test_superstate_mcp_client.py"
Cohesion: 0.12
Nodes (26): Responsibilities:, Exception, io, find_superstate_binary(), Resolve the superstate executable binary for MCP tool exposure. Checks explicit…, McpError, McpProcessError, McpRpcError (+18 more)

### Community 19 - "test_offline_review.py"
Cohesion: 0.11
Nodes (28): clean_json_response(), compute_review_metrics(), get_task_instruction(), main(), Any, Compute aggregate precision, recall, and false alarm rate from review results., Retrieve the task instruction markdown., Extract clean JSON text from LLM response. (+20 more)

### Community 20 - "AblationRunner"
Cohesion: 0.11
Nodes (20): AblationRunner, Any, Resolve a cohort entry into (task_id, image, base_budget_sec, task_spec)., Execute a matrix of tasks x arms concurrently using the dynamic governor., Executes benchmark tasks across evaluation arms with resource and lease…, A cohort of 8 GB tasks must not be dispatched at the 4 GB default width., test_ablation_runner_live_path_requires_explicit_driver(), test_run_cohort_forwards_task_specs_and_driver() (+12 more)

### Community 21 - "DockerManager"
Cohesion: 0.13
Nodes (18): DockerClient, PilotShowdownRunner, Executes a single benchmark task across evaluation arms with isolated…, DockerManager, Manages Docker containers and host disk resource reclamation., main(), Tests for Docker Lifecycle and Disk Space Watchdog., test_check_disk_space_healthy() (+10 more)

### Community 22 - "Working in superstate-eval"
Cohesion: 0.09
Nodes (23): A bad gate is worse than no gate, Arm input parity — the single most common source of false findings, Arms — check the name before comparing anything, Before running anything: check the ledger, Do not run `vanilla` by default, Drivers, Evaluation Philosophy: Autonomous TDD vs. Answer-Key Cheating, Full Benchmark: `SWE-Core` (`--core`) (+15 more)

### Community 23 - "docker_manager.py"
Cohesion: 0.11
Nodes (17): docker, docker_models_containers, DiskSpaceError, ImageBuildError, Path, RuntimeError, Docker lifecycle and host disk space management. Ensures deterministic…, Copy the task repository out of `image` into the host directory `dest`. A bind… (+9 more)

### Community 24 - "test_ablation_runner.py"
Cohesion: 0.15
Nodes (20): Any, Auditable execution telemetry across an evaluation unit., RunTelemetry, compute_control_plane_lift(), _harness_of(), Cluster failures per arm so recurring defects are visible. A pass rate says an…, Render clustered failures as text, most frequent first., Measure what each layer adds to a given harness, task by task. This evaluation… (+12 more)

### Community 25 - "FakeMcpServerProcess"
Cohesion: 0.11
Nodes (16): FakeMcpServerProcess, MonkeyPatch, Verify initialize, initialized notification, tools/list, and caching 25 tools., Verify call_tool parses text and nested json in result.content., Verify call_tool raises McpRpcError on JSON-RPC error payload., Verify context manager automatically starts and terminates child process., Mock subprocess simulating stdio JSON-RPC MCP server., Verify non-JSON lines preceding a valid JSON-RPC response do not hang. (+8 more)

### Community 26 - "Working in superstate-eval"
Cohesion: 0.09
Nodes (23): A bad gate is worse than no gate, Arm input parity — the single most common source of false findings, Arms — check the name before comparing anything, Before running anything: check the ledger, Do not run `vanilla` by default, Drivers, Evaluation Philosophy: Autonomous TDD vs. Answer-Key Cheating, Full Benchmark: `SWE-Core` (`--core`) (+15 more)

### Community 27 - ".__init__"
Cohesion: 0.10
Nodes (18): Autonomous TDD DAG Execution Implementation Plan, Global Constraints, Task 1: Add `tdd_dag` Configuration and 2-Node DAG Construction in `SuperstateDaemonAdapter`, Task 2: Register `superstate_daemon_dag` Arm and Verify Parity, Task 3: Register and Execute EXP-064 Canary Benchmark, Evaluation Philosophy & Autonomous TDD Benchmark Architecture Implementation Plan, Global Constraints, Task 1: Author and Publish `docs/EVALUATION-PHILOSOPHY.md` (+10 more)

### Community 28 - "test_runner.py"
Cohesion: 0.19
Nodes (19): EvaluationResult, Outcome of blind verification and patch extraction., MockDriver, Any, Path, Tests for AblationRunner telemetry and metrics integration. Validates that…, Verify fallback to 1.0 pass fraction when verifier stats are None and task…, Verify fallback to 0.0 pass fraction when verifier stats are None and task… (+11 more)

### Community 29 - "SuperstateMcpClient"
Cohesion: 0.11
Nodes (15): BaseException, Global Constraints, MCP Evaluation Dual Architecture Implementation Plan, Task 2: Harness-Level Adapter (`SuperstateMcpAdapter`), Task 3: Driver MCP Support & Agent-Level Autonomous Adapter, Task 4: Runner Integration & Benchmark Parity Verification, 3.2 Harness-Level Adapter: `SuperstateMcpAdapter` (`lab/engine/adapters/superstate_mcp.py`), Execution Flow: (+7 more)

### Community 30 - "test_docker_integration.py"
Cohesion: 0.15
Nodes (18): collections_abc, requires_docker, fixture, Path, Integration tests exercising a real Docker daemon. The unit suite mocks…, End-to-end: build the verifier image and have it write reward.json. Mirrors the…, reward.txt == -1 is an infrastructure failure, not a legitimate 0., End-to-end proof the exec lands inside the sandbox. The probe image carries a… (+10 more)

### Community 31 - "test_differential.py"
Cohesion: 0.16
Nodes (19): deepdiff, tempfile, check_binaries(), normalize_state(), fixture, Path, Differential parity testing between superstate (Rust) and agent-rules (Python).…, Resolve a binary from env, then PATH (only if a name is given), then fallbacks.… (+11 more)

### Community 32 - "SuperstateRelayAdapter"
Cohesion: 0.16
Nodes (14): Cross-Agent Relay & Autonomous Detached Daemon Evaluation Implementation Plan, Global Constraints, Task 3: Wire Adapters into Runner and Add End-to-End Harness Tests, Task 4: Automated Pilot Script & 5-Task Benchmark Execution, Any, BudgetHook, Path, Adapter for a two-stage collaboration between Claude and Agy. (+6 more)

### Community 33 - "MockDriver"
Cohesion: 0.10
Nodes (20): auto_rollback_enabled(), impact_slicing_enabled(), Whether automatic rollback on milestone failure is enabled for the daemon., Whether milestone-scoped test impact slicing is enabled for the daemon., MockDriver, Any, MonkeyPatch, Mock agent driver for testing. (+12 more)

### Community 34 - "test_adapters.py"
Cohesion: 0.12
Nodes (16): find_superstate_binary(), Resolve the state-engine binary for a named implementation. Resolution is…, Tests for Evaluation Arm Adapters: Vanilla, Superpowers, and Superstate., Test gate command failure, stateless turn (conv=None), diff stat, and recovery…, Regression from the first live run. The agy driver hands the agent `./run-in-…, Verify AblationRunner resolves superstate_mcp and superstate_agent_mcp adapters., Verify is_transient_stream_interruption correctly classifies transport vs…, test_gate_command_strips_a_host_bridge_wrapper_when_run_in_container() (+8 more)

### Community 35 - ".run_sandbox"
Cohesion: 0.12
Nodes (15): Container, Task 2: Container Resource Constraints & Volume Isolation, Dynamic Container Workspace Switching Implementation Plan, Global Constraints, Task 1: Runner Mount Decoupling & Container Symlink Setup, Task 2: Worktree Turn Repointing in Superstate Adapter, Task 3: Live Verification on `db-wal-recovery`, 2. GREEN Phase (+7 more)

### Community 36 - "TaskSpec"
Cohesion: 0.14
Nodes (14): Concurrent Verifier Seal Resolution & 4-Worker Concurrency Plan, Task 1: TaskSpec `has_verifier_dockerfile` Seal Resilience & Test, Task 2: Concurrency 4 Configuration, Task 3: Full Verification Suite, Task 4: Commit & Merge, Task 5: Launch Benchmark Suite at Concurrency 4, Specification of an evaluation benchmark task., Whether the task has a Dockerfile in its tests/ directory. (+6 more)

### Community 37 - "TurnBasedAdapter"
Cohesion: 0.16
Nodes (11): Any, BudgetHook, Path, Run an agent session or turn within the target workspace., Execute a task in the given workspace using the provided driver., Base template adapter managing bounded turn execution and mechanical approval., Configure or sanitize workspace prior to agent invocation., Provide initial instruction prompt for the task. Baseline arms (vanilla,… (+3 more)

### Community 38 - ".execute"
Cohesion: 0.15
Nodes (12): is_transient_stream_interruption(), Classify whether an error string represents a transient API transport…, Any, BudgetHook, Path, Report state engine, transport, and autonomous tooling provenance. Returns:…, Keep harness files from dirtying the git working tree. Appends harness-internal…, Sanitize workspace by stripping legacy guidance and excluding harness… (+4 more)

### Community 39 - "SuperstateAdapter"
Cohesion: 0.19
Nodes (13): Adapter executing tasks under the deterministic Superstate engine., Extract a clean, concise finding from the turn's response to keep prompts…, Strip a host-side bridge wrapper when the gate already runs in the sandbox., SuperstateAdapter, Path, test_switch_container_workspace_handles_exec_nonzero_exit(), test_switch_container_workspace_handles_none_container(), test_switch_container_workspace_no_worktree_mode() (+5 more)

### Community 40 - "RunRecorder"
Cohesion: 0.15
Nodes (12): _clip(), Any, Path, Capture one driver turn, including the prompt that produced it., Capture a milestone attempt and its gate verdict., Persist the full held-out verifier output, untruncated., Write the headline run record. Returns the path written, if any., Truncate a captured field, saying so explicitly rather than silently. (+4 more)

### Community 41 - "test_agy_cli_driver.py"
Cohesion: 0.33
Nodes (16): FakeContainer, _make_stub(), Path, Tests for the Antigravity CLI (agy) driver. Driven against a stub executable so…, Write a fake `agy` that echoes a fixed JSON payload and records its argv., _read_argv(), _task(), test_container_exec_can_be_disabled() (+8 more)

### Community 42 - "test_container_bridge.py"
Cohesion: 0.20
Nodes (16): _create_fake_docker(), _create_fake_superstate(), FakeContainer, Path, Tests for container bridge script generation and transparent shunting.…, Ensure non-zero exit codes are preserved through the bridge when shunting is…, Ensure stdin streaming is faithfully preserved across the container bridge., Verify that when superstate is present and shunting enabled, superstate shunt… (+8 more)

### Community 43 - "test_in_container_driver.py"
Cohesion: 0.27
Nodes (15): base64, InContainerClaudeDriver, _container(), Tests for the isolated in-container agent driver., _task(), test_agent_runs_as_a_non_root_user(), test_cost_is_estimated_only_from_a_known_rate(), test_driver_declares_itself_isolated() (+7 more)

### Community 44 - "What the evaluation establishes"
Cohesion: 0.12
Nodes (17): 10. The +20pp routing lift was an in-sample artifact, 11. Repository-First Benchmark Architecture: Eliminating Command-Line Puzzles (2026-09-20), 1. The effect is real, and its size is +19pp, 2. The mechanism is the handoff prompt, not the control loop, 3. The daemon is a legitimate default, 4. The loop does fire — on hard enough tasks, 5. The benchmark corpus is a third the size it appears, 6. Nothing in superstate builds the gate (+9 more)

### Community 45 - "effect.py"
Cohesion: 0.16
Nodes (16): itertools, math, bootstrap_ci(), collect(), _infra_failure(), main(), permutation_p(), Path (+8 more)

### Community 46 - "BaseCliDriver"
Cohesion: 0.15
Nodes (13): BaseCliDriver, CliDriverError, first(), Any, Path, RuntimeError, Turn the CLI's JSON result into telemetry., Raised when the agent CLI cannot be located or invoked. (+5 more)

### Community 47 - "reporter.py"
Cohesion: 0.24
Nodes (14): generate_comparison_summary(), Any, Evaluation reporter generating cost-efficiency frontier comparisons., Group run telemetry by paradigm arm and calculate core efficiency metrics., Render control-plane lift, with the caveat that small n cannot support it., Render summary as a formatted text table for reports., Render Total Cost of Ownership (TCO) incorporating human remediation penalties., render_economic_tco_table() (+6 more)

### Community 48 - "pytest"
Cohesion: 0.18
Nodes (16): find_static_superstate_binary(), Locate pre-compiled static Linux superstate binary if available on host. Checks…, pytest, MonkeyPatch, Path, Tests for mounting static Linux superstate binary into sandbox containers., Verify find_static_superstate_binary respects SUPERSTATE_LINUX_BIN when file…, Verify find_static_superstate_binary falls back when SUPERSTATE_LINUX_BIN does… (+8 more)

### Community 49 - "Design Specification: Agent-Driven Worktrees & Full-Context Turnkey Execution"
Cohesion: 0.12
Nodes (15): 1.1 `ExecutionState` Model (`crates/superstate-core/src/models.rs`), 1.2 Full-Context Turnkey Prompt (`crates/superstate-core/src/prompt.rs`), 1. Problem Statement & Motivation, 2.1 Default In-Place Execution in `state init`, 2.2 Dedicated Agent Worktree Commands, 2. Core Architectural Principles, 3.1 Universal Zero-Turn Direct Initialization, 3.2 Dynamic Turn & Milestone Execution (+7 more)

### Community 50 - "SuperpowersAdapter"
Cohesion: 0.14
Nodes (9): Any, Path, Adapter configuring markdown rules and vendored superpowers skills., Install markdown guidance and copy superpowers skills into workspace., Configure workspace with Superpowers guidance before execution begins., Record whether the vendored skills library was actually installed., SuperpowersAdapter, test_production_turn_caps_do_not_bind_on_ordinary_runs() (+1 more)

### Community 51 - "test_arm_input_parity.py"
Cohesion: 0.12
Nodes (15): Every arm must receive the same inputs, or a comparison measures the harness.…, Adapters are passive translation shims. They must NEVER synthesize task…, Adapters must use `references_sealed_grader()` rather than raw `"/tests/" in…, All arms must consult GATE_FIXTURES before falling back. superstate_mcp.py was…, The `true` fallback must come AFTER the fixture lookup, not instead of it., The daemon spawns its own worker, bypassing AgyCliDriver. Each flag…, `turns` must count worker invocations in every arm, or arms cannot be compared.…, Two configurations must never report the same name, or results pool them… (+7 more)

### Community 52 - "Control-Plane Evaluation — Plan"
Cohesion: 0.13
Nodes (14): Control-Plane Evaluation — Plan, Harness defects found by running (all fixed), Parked, with reasons, Standing lesson from today, Stream 1 — Produce a credible measurement, Stream 2 — Rust parity — COMPLETE (2026-09-09), Task 1: Pin the engine explicitly and record it — DONE, Task 2: Drive the real state-engine loop — DONE (+6 more)

### Community 53 - ".run"
Cohesion: 0.16
Nodes (11): Detailed Steps, Files to Touch, Global Constraints, Objective, Task 1 Brief: Container Bridge Output Shunting, Working Directory, Any, Path (+3 more)

### Community 54 - "Superstate Massive Adoption & Founder Prestige Roadmap"
Cohesion: 0.13
Nodes (14): 1. Executive Summary & Core Mission, 2. Core Positioning & Intellectual Anchors, 3. Four-Phase Execution Roadmap, 4. Key Metrics & Success Criteria, 5. Spec Self-Review Checklist, Phase 1: Packaging & Developer Ergonomics (Week 1), Phase 2: The Technical Manifesto & Empirical Paper (Week 2), Phase 3: The Viral Launch Campaign (Week 3) (+6 more)

### Community 55 - "HeldOutVerifier"
Cohesion: 0.30
Nodes (13): 3.1 `SuperstateRelayAdapter` (`lab/engine/adapters/superstate_relay.py`), 3.2 `SuperstateDaemonAdapter` (`lab/engine/adapters/superstate_daemon.py`), 3. Architecture & Adapter Specifications, HeldOutVerifier, Builds and runs the task's own verifier image., _manager(), Path, The verifier image is the held-out answer key; it must not linger on the host. (+5 more)

### Community 56 - "Design Specification: Autonomous TDD DAG Execution & Hand-Authored Fixture Elimination"
Cohesion: 0.13
Nodes (14): 1. Executive Summary & Context, 2.1 Milestone Specifications, 2. Architecture: Deterministic 2-Node TDD State Graph, 3.1 Arm Definition, 3.2 State Initialization (`_init_daemon_state`), 3.3 Zero Prompt Engineering Compliance, 3. Harness Integration in `superstate-eval`, 4.1 Experiment EXP-064 (+6 more)

### Community 57 - "Design Specification: Evaluation Philosophy & Autonomous TDD Benchmark Architecture"
Cohesion: 0.13
Nodes (14): 1. Executive Summary & Context, 2.1 The Four Non-Negotiable Invariants, 2. The Core Philosophy, 3.1 Milestone 1: `tdd-reproduction-test` (Gate Derivation), 3.2 Milestone 2: `fix-implementation` (Autonomous Convergence), 3.3 Post-Run Held-Out Grading, 3. Architecture: Autonomous TDD State DAG, 4.1 `superstate-eval/AGENTS.md` (+6 more)

### Community 58 - "test_gate_fixtures.py"
Cohesion: 0.13
Nodes (14): The gate fixtures are the contract of record, so their shape is worth pinning., Gating on /tests/ would let the agent read the answer key it is scored against., The sealed grader is at /tests/, whereas /app/<pkg>/tests/ is an in-repo suite., A gate that cannot fail cannot discriminate, and the worker stops the moment it…, A fixture with a quoting error fails for the wrong reason and looks like a hard…, A derived gate once reduced to `test -f <file> && not-on-main`, satisfiable by…, A task whose grader cannot run scores every arm zero and shrinks the…, test_every_fixture_is_valid_shell() (+6 more)

### Community 59 - "Hybrid Tool Output Shunting & Distillation Design Spec"
Cohesion: 0.14
Nodes (13): 1. Problem Statement & Context, 2. Core Architectural Objectives, 3. System Architecture & Data Flow, 4.1 Container Bridge Shunting (`lab/engine/drivers/agy_cli.py`), 4.2 Shunt CLI Command Hardening (`crates/superstate-cli/src/commands/shunt.rs`), 4.3 In-Container Native Binary Mounting (`lab/sandbox/docker_manager.py`), 4.4 Linux Static Build Pipeline (`repos/superstate`), 4. Component Specifications (+5 more)

### Community 60 - "resolve_next_turn_prompt"
Cohesion: 0.24
Nodes (12): is_waiting_for_user_input(), Mechanical User and Autonomous Human-in-the-Loop Interceptor. Prevents…, Inspect agent output and return automated approval prompt if waiting, or None…, Analyze agent response text to detect if the agent paused for human approval or…, resolve_next_turn_prompt(), Tests for Mechanical User and Autonomous Human-in-the-Loop Elimination., test_is_waiting_for_user_input_detects_ask_question_tool(), test_is_waiting_for_user_input_detects_standard_approval_prompts() (+4 more)

### Community 61 - "test_generic_rules.py"
Cohesion: 0.21
Nodes (13): apply_generic_rules(), generic_rules_enabled(), Whether the portable discipline rules are injected into baseline arms. Separate…, Append the portable discipline rules to a baseline arm's prompt, if enabled., The generic-rules leg tests whether execution discipline is portable off…, The default measurement gives baselines the bare instruction, as it always has., Half of TARGETED_EXECUTION_CONTRACT is scaffolding for the state machine. Rule…, Conflating the flags would make neither hypothesis answerable. (+5 more)

### Community 62 - ".run"
Cohesion: 0.21
Nodes (10): Any, Path, Build the verifier image for `task` and return its tag., Run the held-out verifier against the collected patch. `logs_dir` must already…, Delete the verifier image so the hidden tests do not linger on the host., Run the built verifier image against the collected patch., Docker tags allow a restricted character set; task ids do not., Read reward.json, falling back to the reward.txt crash sentinel. Returns… (+2 more)

### Community 63 - "test_state_engine_loop.py"
Cohesion: 0.34
Nodes (12): requires_engine, _engines(), parametrize, Path, The superstate adapter driving a real state engine through a full loop. Every…, Succeeds every turn, recording the prompts it was given., ScriptedDriver, test_a_failing_gate_stops_the_run_and_is_reported() (+4 more)

### Community 64 - "AgyCliDriver"
Cohesion: 0.21
Nodes (11): Antigravity CLI Driver (`AgyCliDriver`) Implementation Plan, Global Constraints, Task 1: Implement `AgyCliDriver` Core and Container Execution Bridge, Task 2: Verify Baseline and System Integration, Task 3: Execute Live Single-Task Smoke Run, 1. Executive Summary & Context, 4. Container Execution Bridge (`./run-in-container`), 5. Verification & Testing Strategy (+3 more)

### Community 65 - "AgyCliDriverError"
Cohesion: 0.15
Nodes (12): 3.1 Class Definition (`lab/engine/drivers/agy_cli.py`), 3.2 CLI Binary Resolution, 3.3 Command Construction, 3.4 Telemetry & Pricing, 3. Architecture & Driver Implementation, AgyCliDriverError, RuntimeError, Initialize the agy driver. Args: model: Model identifier for agy (defaults to… (+4 more)

### Community 66 - "agent_image.py"
Cohesion: 0.19
Nodes (8): hashlib, AgentImageBuilder, Builds the image the agent actually runs inside. The agent must not run on the…, Docker tags allow a restricted character set; image refs do not., Builds and caches per-task agent images., A deterministic tag: this image holds no secrets, so caching is safe. Unlike…, Build (or reuse) an image with the Claude Code CLI on top of `base_image`., _slug()

### Community 67 - ".run_pilot"
Cohesion: 0.22
Nodes (7): MockContainer, PilotMockDriver, Any, Path, Execute task across arms and return structured benchmark outcomes. With…, Predictable mock driver simulating agent behavior for pilot verification., Mock container for testing evaluation extractors without live Docker.

### Community 68 - "VanillaAdapter"
Cohesion: 0.20
Nodes (8): Path, Unguided baseline adapter enforcing complete isolation from rules or skills., Sanitize workspace by removing all guidance, rule files, and skills., Ensure pristine unguided workspace before execution., VanillaAdapter, test_adapter_passes_container_handle_to_driver(), test_turn_loop_breaker_reports_failure(), test_vanilla_adapter_cleans_workspace_and_executes()

### Community 69 - "_ScriptedDriver"
Cohesion: 0.17
Nodes (9): SimpleNamespace, Driver stub returning a different response per successive turn., An incomplete gate is worse than no gate: the worker stops the moment it…, A critique may only strengthen the contract. A no-op reply keeps the original., A widened gate that already passes cannot discriminate, so the original stands., _ScriptedDriver, test_critique_cannot_weaken_the_gate(), test_critique_rejecting_an_already_passing_gate() (+1 more)

### Community 70 - "eval_routing_split.py"
Cohesion: 0.22
Nodes (8): collections, random, classify_arm(), evaluate(), load_runs(), Any, Evaluate Section 10's routing claims with a reproducible split-half validation.…, Report how often a passing gate agrees with the sealed grader. The gate is what…

### Community 71 - "Design Specification: Repository-First Software Engineering Benchmarks"
Cohesion: 0.18
Nodes (10): 1.1 The Category Error of Command-Line Puzzles, 1.2 The Canary Bottleneck, 1. Executive Summary & Problem Diagnosis, 2. Core Principles & Invariants, 3.1 Tier 1: `SWE-Canary` (Fast Tri-Language Loop, ~15–20 min total), 3.2 Tier 2: `SWE-Core` (Canonical Real Repository Suite, 8 Repositories), 3. Two-Tier Suite Definition, 4. Formal Exclusions (+2 more)

### Community 72 - "Superstate Evaluation Philosophy & Benchmark Integrity Manifesto"
Cohesion: 0.20
Nodes (10): 1.1 The Synthetic Gate Collapse, 1.2 The Answer-Key Cheating Trap, 1. Executive Summary & The Problem We Solved, 3. The Autonomous TDD State DAG, 4. The Five Evaluation Metrics, 5. Summary: Why This Tests the Superstate Ethos, Milestone 1: `tdd-reproduction-test`, Milestone 2: `fix-implementation` (+2 more)

### Community 73 - "Task 2 Brief: In-Container Static Linux Binary Mounting"
Cohesion: 0.20
Nodes (9): Detailed Steps, Files to Touch, Global Constraints, Objective, Task 2 Brief: In-Container Static Linux Binary Mounting, Working Directory, 1. RED Phase, Verify spawn_sandbox does not add mount when static binary is absent. (+1 more)

### Community 74 - "Frontier Triad Benchmark: Final Evaluation Report"
Cohesion: 0.20
Nodes (9): 1. Executive Summary, 2. Comparative Scorecard & Economics, 3. Granular Test Breakdown: Moving Past Binary Metrics, 4. Full Per-Task Results (All 30 Tasks), 5. Architectural Findings, Frontier Triad Benchmark: Final Evaluation Report, Standard Benchmark Metrics, SWE-Bench Test Completion Comparison (+1 more)

### Community 75 - "Superstate Resilience, Diagnostic Retry Loops, and Git Native State Tracking Design"
Cohesion: 0.20
Nodes (9): 1. Context & Motivation, 2. Goals & Non-Goals, 3.1 Diagnostic Retry Loop in `lab/engine/adapters/superstate.py`, 3.2 Greenfield Git Resilience, 3. Architecture & Mechanics, 4. Verification & Testing, Goals, Non-Goals (+1 more)

### Community 76 - "3. Detailed Component Design"
Cohesion: 0.20
Nodes (9): 1. Executive Summary & Objective, 2. Architecture & Components, 3.1 `SuperstateMcpClient` (`lab/engine/mcp/client.py`), 3.3 Agent-Level Autonomous Adapter: `SuperstateAgentMcpAdapter` (`lab/engine/adapters/superstate_agent_mcp.py`), 3.4 Driver Integration (`lab/engine/drivers/claude_cli.py`), 3.5 Runner Arms Configuration (`lab/engine/runner.py`), 3. Detailed Component Design, 4. Verification & Testing Strategy (+1 more)

### Community 77 - "test_condition_b.py"
Cohesion: 0.24
Nodes (9): carries_conversation(), Whether this arm may thread a conversation id across turns. Condition B arms…, Condition B is defined by stateless turns; guard against that drifting again., Zero-turn injection is the mechanism the 76% result was built on. Threading a…, Condition A is the in-loop paradigm under test; making it stateless would erase…, Every carry-over must route through conversation_id_for, or the invariant leaks., test_condition_a_remains_conversational(), test_condition_b_arms_never_carry_a_conversation() (+1 more)

### Community 78 - "._perform_handshake"
Cohesion: 0.22
Nodes (5): Start the MCP server when entering the context block., Generate a monotonically increasing request ID., Spawn the superstate mcp process and execute protocol handshake. Raises:…, Execute standard MCP initialization handshake and populate tool cache., Send a JSON-RPC notification message without awaiting reply.

### Community 79 - "test_prompt_contracts.py"
Cohesion: 0.24
Nodes (9): contracts_enabled(), Whether arm-specific behavioural contracts are injected into agent prompts.…, The default measurement must contain no arm-specific prompt engineering., The thesis is that managing state produces the gain, so nothing else may…, Preserved, not deleted -- reproducing historical runs must remain possible., Every injection must route through the switch, or the default silently leaks., test_contracts_are_off_by_default(), test_contracts_can_be_re_enabled_explicitly() (+1 more)

### Community 80 - "superstate-eval"
Cohesion: 0.20
Nodes (10): A note on what this harness has taught us, Autonomous TDD & The Anti-Cheating Invariant, Differential parity, How a run works, Layout, Quick start, superstate-eval, Tasks & Repository-First Suites (+2 more)

### Community 81 - "experiments.py"
Cohesion: 0.36
Nodes (9): cmd_check(), cmd_list(), cmd_scan(), main(), parse_ledger(), Path, Reconcile EXPERIMENTS.md against results/ so "has this been run?" is one…, Return (rows, distinct tasks, {arm: (passed, n)}) for a results JSON. (+1 more)

### Community 82 - "Global Constraints"
Cohesion: 0.22
Nodes (8): Global Constraints, Superstate Massive Adoption & Founder Prestige Implementation Plan, Task 1: Prebuilt Multi-Platform Binary Releases & Homebrew Tap Setup, Task 2: Interactive `superstate init` Repository Wizard, Task 3: MCP Registry & Smithery Integration Metadata, Task 4: Empirical Technical Whitepaper & Academic Preprint, Task 5: Launch Campaign Package (Show HN, Viral X Thread, Video Script), Task 6: Turnkey GitHub Action (`superstate/action@v1`)

### Community 83 - "TDD Verification Lifecycle"
Cohesion: 0.22
Nodes (8): 1. RED Phase, 2. GREEN Phase, 3. Static Analysis & Linting, 4. Full Regression Test Suite, Commit, Summary, Task 1 Report: Container Bridge Output Shunting, TDD Verification Lifecycle

### Community 84 - ".run"
Cohesion: 0.25
Nodes (7): _first(), InContainerDriverError, Any, Path, RuntimeError, Raised when the in-container agent cannot be invoked., Build the shell line executed inside the container. The prompt is base64'd so…

### Community 85 - "FakePipe"
Cohesion: 0.22
Nodes (3): FakePipe, Any, Mock file-like pipe supporting write and readline.

### Community 86 - "Global Constraints"
Cohesion: 0.25
Nodes (7): Global Constraints, Superstate Resilience and Diagnostic Retry Loop Implementation Plan, Task 1: Implement Greenfield Git Handling in `lab/engine/adapters/superstate.py`, Task 2: Implement Milestone Diagnostic Retry Loop in `lab/engine/adapters/superstate.py`, Task 3: Unit Tests for Retry Loop & Greenfield Handling, Task 4: Native Git Initialization in Rust `superstate`, Task 5: Verification & Checkpoint

### Community 87 - "Global Constraints"
Cohesion: 0.25
Nodes (7): Global Constraints, Repository-First Software Engineering Benchmarks Implementation Plan, Task 1: Redefine Task Sets and Exclusion Rules in `lab/benchmarks/task_sets.py`, Task 2: Codify Repository-First Invariant in Documentation, Task 3: Update Canary Scripts and Experiment Ledger (EXP-065), Task 4: Execute Tri-Language SWE-Canary Benchmark (EXP-065), Task 5: Complete Verification and Finish Feature Branch

### Community 88 - "4. Corpus Audit: FrontierHarness Eval Classification"
Cohesion: 0.25
Nodes (8): 1. Scientific Rationale: Scoping the Operational Domain, 3. Candidate Task Admission Checklist, 4. Corpus Audit: FrontierHarness Eval Classification, Admitted: Canonical Repositories (`SWE_CORE_TASKS`, n=9), Excluded: Ceilings & Floors (Violate Req 5, n=8), Excluded: Toy Scripts & Command-Line Puzzles (Violate Req 1 & Req 3, n=5), Excluded: Ungradeable (Violate Req 2, n=8), Task Qualification Rubric for Superstate Evaluation

### Community 89 - "estimate_cost_usd"
Cohesion: 0.29
Nodes (8): base_model_name(), estimate_cost_usd(), Strip an effort suffix so variants resolve to the base model's pricing., Calculate USD cost for a given model and token counts. Returns 0.0 for an…, agy exposes one model per effort level; effort changes tokens, not price., test_effort_variants_are_priced_as_their_base_model(), test_pricing_table_covers_gemini_models(), test_unpriced_model_reports_zero_rather_than_a_guess()

### Community 90 - "test_agent_failure_is_diagnosed_before_the_grading_symptom"
Cohesion: 0.25
Nodes (5): A result from a driver with a host shell carries a weaker guarantee. It must…, An agent that times out leaves a bad patch; the timeout is the cause. Reporting…, test_agent_failure_is_diagnosed_before_the_grading_symptom(), test_run_telemetry_records_whether_execution_was_isolated(), fake_sandbox()

### Community 91 - "FlakyGateDriver"
Cohesion: 0.29
Nodes (6): FlakyGateDriver, Path, Verify that a greenfield workspace without .git does not crash when advancing…, Fails on turn 1 by not creating marker.txt, then creates it on turn 2 after…, test_greenfield_workspace_advances_without_git(), test_milestone_retry_loop_on_failed_gate()

### Community 92 - "pilot_run.py"
Cohesion: 0.33
Nodes (5): argparse, Run a pilot benchmark showdown across Vanilla, Superpowers, and Superstate.…, main(), Run a live single-task smoke test using AblationRunner and AgyCliDriver., sys

### Community 93 - "Tasks"
Cohesion: 0.29
Nodes (4): superstate-eval Local Assessment Repository Implementation Plan, Tasks, Verification & Completion Gates, Prune dangling images, stopped containers, and unreferenced volumes.

### Community 94 - "Global Constraints"
Cohesion: 0.29
Nodes (6): Agent-Driven Worktrees & Full-Context Turnkey Execution Implementation Plan, Global Constraints, Task 1: Model & Prompt Context Fidelity (`superstate-core`), Task 2: In-Place Default & Agent Worktree CLI (`superstate-cli`), Task 3: Universal Zero-Turn Planning in Adapter (`superstate-eval`), Task 4: Targeted Benchmark Verification on Target Subset

### Community 95 - "Global Constraints"
Cohesion: 0.29
Nodes (6): Global Constraints, Hybrid Tool Output Shunting & Distillation Implementation Plan, Task 1: Container Bridge Output Shunting (`lab/engine/drivers/agy_cli.py`), Task 2: In-Container Static Linux Binary Mounting (`lab/sandbox/docker_manager.py`), Task 3: Shunt CLI Stdin Streaming & Exit Code Verification (`repos/superstate`), Task 4: Empirical Benchmark Verification on `build-cython-ext`

### Community 97 - "2. The Core Evaluation Philosophy"
Cohesion: 0.33
Nodes (6): 2. The Core Evaluation Philosophy, Invariant 1: The Anti-Cheating Invariant (Sealed Grader Integrity), Invariant 2: Permanent Ban on Hand-Authored Synthetic Fixtures, Invariant 3: The Non-Vacuous Gate Requirement, Invariant 4: Pure Mechanical Control vs. Conversational Vibes, Invariant 5: The Repository-First Invariant (Permanent Ban on Toy Puzzles)

### Community 98 - "Experiment provenance: what the 2026-09-13 benchmark actually ran"
Cohesion: 0.33
Nodes (5): Constant gates, not moving ones, Experiment provenance: what the 2026-09-13 benchmark actually ran, Stateless solo, not conversational, The confound that is real, The valid comparison

### Community 99 - "Design Spec: Dynamic Container Workspace Switching for Worktree Isolation"
Cohesion: 0.33
Nodes (5): 1. Problem Statement, 2. Proposed Architecture, 3. Benefits & Performance, Design Spec: Dynamic Container Workspace Switching for Worktree Isolation, Dynamic `/app` Symlink via `/workspace_root` Mount

### Community 100 - "2. The Five Mandatory Task Qualification Requirements"
Cohesion: 0.33
Nodes (6): 2. The Five Mandatory Task Qualification Requirements, Requirement 1: Multi-File Software Repository with Existing Test Suite, Requirement 2: Sealed Held-Out Grader (`/tests/`), Requirement 3: Multi-Turn Architectural Complexity, Requirement 4: Substantial Build / Test Telemetry, Requirement 5: Discriminative Power (Anti-Ceiling & Anti-Floor)

### Community 101 - "._send_request"
Cohesion: 0.33
Nodes (3): Send a JSON-RPC request and wait for the corresponding response. Parameters:…, Read a single line from stdout with a timeout deadline. Parameters: deadline:…, Read lines from stdout until receiving the matching JSON-RPC response. Filters…

### Community 102 - "harvest_run_diffs.py"
Cohesion: 0.40
Nodes (5): get_git_diff_and_untracked(), harvest(), Path, Harvest labelled diffs and execution telemetry from /tmp/superstate_eval_runs.…, Extract git diff from initial baseline commit to current state, including…

### Community 103 - "test_runner_mounts_workspace_root_and_inits_symlink"
Cohesion: 0.33
Nodes (5): Path, test_agy_cli_driver_run_in_container_sets_workdir(), test_runner_mounts_workspace_root_and_inits_symlink(), fake_run_sandbox(), run()

### Community 104 - "test_domain_wrapper_methods"
Cohesion: 0.33
Nodes (5): Path, Verify all domain helper wrappers delegate to call_tool correctly., Live integration test against the local superstate binary., test_domain_wrapper_methods(), test_real_superstate_mcp_integration()

### Community 105 - "Experiment ledger"
Cohesion: 0.40
Nodes (4): Cross-cutting findings, Experiment ledger, Rules, Status values

### Community 106 - "InsufficientResourcesError"
Cohesion: 0.40
Nodes (5): InsufficientResourcesError, NoDriverConfiguredError, RuntimeError, Raised when a live evaluation is requested without an agent driver., Raised when the host cannot safely run even a single concurrent evaluation.

### Community 107 - "Feature Implementation Plan"
Cohesion: 0.40
Nodes (4): Feature Implementation Plan, Task 1: Setup database schema, Task 2: Implement repository methods, Task 3: Expose REST endpoint

### Community 108 - "run_exp060.sh"
Cohesion: 0.40
Nodes (4): run_exp060.sh script, SUPERSTATE_EVAL_DERIVE_GATES, SUPERSTATE_EVAL_GENERIC_RULES, SUPERSTATE_EVAL_PROMPT_CONTRACTS

### Community 109 - "test_tasks_without_a_sealed_grader_are_marked_unmeasurable"
Cohesion: 0.50
Nodes (4): A task with no sealed grader cannot be scored, A task with no held-out tests/ cannot be scored, so it must be listed. The…, test_tasks_without_a_sealed_grader_are_marked_unmeasurable(), A task with no sealed grader cannot be scored

### Community 110 - "gate_derivation_enabled"
Cohesion: 0.50
Nodes (4): gate_derivation_enabled(), Whether the daemon may author its own verification contract when none is…, Retained behind a flag so the 2026-09-15 runs that used it stay reproducible., test_gate_derivation_can_be_re_enabled_for_reproduction()

### Community 111 - "ignore_gate_fixtures"
Cohesion: 0.50
Nodes (4): ignore_gate_fixtures(), Whether to skip the hand-authored fixture so the driver must author the gate.…, Gate authorship cannot be measured while a fixture exists for every task.…, test_fixture_short_circuits_derivation_unless_explicitly_ignored()

### Community 112 - "launch_derived_gates.sh"
Cohesion: 0.50
Nodes (3): launch_derived_gates.sh script, SUPERSTATE_EVAL_DERIVE_GATES, SUPERSTATE_EVAL_IGNORE_GATE_FIXTURES

### Community 113 - "The short version"
Cohesion: 0.67
Nodes (3): The short version, The split that matters, Why: superstate swaps the agent's stopping judgement for the gate's

### Community 119 - "derivation_on"
Cohesion: 0.67
Nodes (3): derivation_on(), fixture, Gate derivation is opt-in: the daemon does not author its own contract by…

## Knowledge Gaps
- **256 isolated node(s):** `superstate-eval`, `launch_datacurve_3arm.sh script`, `launch_datacurve_clean.sh script`, `launch_datacurve_planned.sh script`, `launch_derived_gates.sh script` (+251 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 947 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **33 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TaskSpec` connect `TaskSpec` to `extract_and_grade`, `pathlib`, `SuperstateAgentMcpAdapter`, `ClaudeCliDriver`, `DriverTelemetry`, `AnswerKeyGuard`, `SuperstateDaemonAdapter`, `test_superstate_daemon_adapter.py`, `.execute`, `AgentDriver`, `SuperstateMcpAdapter`, `test_superstate_mcp_adapter.py`, `load_benchmark_tasks`, `AblationRunner`, `DockerManager`, `test_ablation_runner.py`, `.__init__`, `test_runner.py`, `SuperstateRelayAdapter`, `MockDriver`, `test_adapters.py`, `TurnBasedAdapter`, `.execute`, `SuperstateAdapter`, `test_agy_cli_driver.py`, `test_in_container_driver.py`, `BaseCliDriver`, `Control-Plane Evaluation — Plan`, `.run`, `test_generic_rules.py`, `test_state_engine_loop.py`, `AgyCliDriver`, `.run_pilot`, `.run`, `test_agent_failure_is_diagnosed_before_the_grading_symptom`, `FlakyGateDriver`?**
  _High betweenness centrality (0.155) - this node is a cross-community bridge._
- **Why does `SuperstateAdapter` connect `SuperstateAdapter` to `pathlib`, `test_adapters.py`, `TaskSpec`, `DriverTelemetry`, `AnswerKeyGuard`, `.execute`, `AgentDriver`, `Design Specification: Agent-Driven Worktrees & Full-Context Turnkey Execution`, `SuperpowersAdapter`, `AblationRunner`, `DockerManager`, `FlakyGateDriver`, `Global Constraints`, `test_state_engine_loop.py`?**
  _High betweenness centrality (0.081) - this node is a cross-community bridge._
- **Why does `SuperstateMcpClient` connect `SuperstateMcpClient` to `SuperstateAgentMcpAdapter`, `._send_request`, `.execute`, `SuperstateDaemonAdapter`, `test_domain_wrapper_methods`, `AgentDriver`, `.call_tool`, `3. Detailed Component Design`, `SuperstateMcpAdapter`, `._perform_handshake`, `test_superstate_mcp_adapter.py`, `test_superstate_mcp_client.py`, `.__init__`, `FakeMcpServerProcess`, `.__init__`?**
  _High betweenness centrality (0.075) - this node is a cross-community bridge._
- **Are the 32 inferred relationships involving `TaskSpec` (e.g. with `Stream 2 — Rust parity — COMPLETE (2026-09-09)` and `Task 1: TaskSpec `has_verifier_dockerfile` Seal Resilience & Test`) actually correct?**
  _`TaskSpec` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 16 inferred relationships involving `DriverTelemetry` (e.g. with `Task 1: Implement `SuperstateRelayAdapter`` and `2. Core Objectives`) actually correct?**
  _`DriverTelemetry` has 16 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `SuperstateAdapter` (e.g. with `Task 3: Universal Zero-Turn Planning in Adapter (`superstate-eval`)` and `2. Core Objectives`) actually correct?**
  _`SuperstateAdapter` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `SuperstateDaemonAdapter` (e.g. with `Cross-Agent Relay & Autonomous Detached Daemon Evaluation Implementation Plan` and `Task 2: Implement `SuperstateDaemonAdapter``) actually correct?**
  _`SuperstateDaemonAdapter` has 13 INFERRED edges - model-reasoned connections that need verification._