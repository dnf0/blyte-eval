# Graph Report - feat-eval-philosophy-autonomous-tdd  (2026-09-20)

## Corpus Check
- 240 files · ~773,344 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 61 file(s) not represented in the graph (top: .log 52, (none) 6, .diff 2)

## Summary
- 2101 nodes · 4613 edges · 139 communities (108 shown, 31 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 355 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7fa712d2`
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
- superstate.py
- Path
- SuperstateMcpAdapter
- Design Specification: Native AST Symbol Inspection & Deterministic Context Bounding
- test_canary_task_set.py
- handle
- load_task_from_dir
- ProgressTracker
- McpProcessError
- test_differential.py
- AblationRunner
- DockerManager
- Working in superstate-eval
- ImageBuildError
- test_ablation_runner.py
- test_superstate_mcp_client.py
- Working in superstate-eval
- .__init__
- test_runner.py
- SuperstateMcpClient
- test_docker_integration.py
- pytest
- TaskSpec
- MockDriver
- Path
- .run_sandbox
- test_task_sets.py
- AgentDriver
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
- test_docker_manager_shunting.py
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
- test_approval.py
- unittest_mock
- .run
- test_state_engine_loop.py
- AgyCliDriver
- AgyCliDriverError
- AgentImageBuilder
- PilotShowdownRunner
- .clean_workspace
- _ScriptedDriver
- Global Constraints
- Design Specification: Repository-First Software Engineering Benchmarks
- Superstate Evaluation Philosophy & Benchmark Integrity Manifesto
- Task 2 Brief: In-Container Static Linux Binary Mounting
- Frontier Triad Benchmark: Final Evaluation Report
- Superstate Resilience, Diagnostic Retry Loops, and Git Native State Tracking Design
- 3. Detailed Component Design
- .__exit__
- Run `--canary` or `--core`, not toy puzzles or the whole corpus
- test_is_transient_stream_interruption_detection
- superstate-eval
- .__init__
- Global Constraints
- TDD Verification Lifecycle
- .run
- FakePipe
- Global Constraints
- Global Constraints
- 4. Corpus Audit: FrontierHarness Eval Classification
- estimate_cost_usd
- test_superstate_resilience.py
- BudgetPolicy
- Global Constraints
- Global Constraints
- 2. The Core Evaluation Philosophy
- Experiment provenance: what the 2026-09-13 benchmark actually ran
- Design Spec: Dynamic Container Workspace Switching for Worktree Isolation
- 2. The Five Mandatory Task Qualification Requirements
- .call_tool
- harvest_run_diffs.py
- Experiment ledger
- .run_task
- Feature Implementation Plan
- run_exp060.sh
- is_unmeasurable
- gate_derivation_enabled
- ignore_gate_fixtures
- launch_derived_gates.sh
- The short version
- run_exp058_canary.sh
- run_exp065_canary.sh
- run_weekend_benchmark.sh
- derivation_on
- benchmarks/__init__.py
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

## Communities (139 total, 31 thin omitted)

### Community 0 - "extract_and_grade"
Cohesion: 0.07
Nodes (54): Global Constraints, Task 1: Extend EvaluationResult and Implement compute_test_metrics, Task 2: Integrate Test Metrics into Runner Telemetry and CLI Output, Test Pass Fraction & Test Statistics Implementation Plan, 1. Context & Motivation, 2.1 EvaluationResult Dataclass Extension, 2.2 Metric Extraction Helper, 2.3 AblationRunner Telemetry Integration (+46 more)

### Community 1 - "pathlib"
Cohesion: 0.10
Nodes (39): argparse, concurrent_futures, contextlib, dataclasses, docker, docker_models_containers, hashlib, io (+31 more)

### Community 2 - "SuperstateAgentMcpAdapter"
Cohesion: 0.11
Nodes (33): Adapter evaluating autonomous agent behavior with direct Superstate MCP tooling., Name of the evaluation arm., SuperstateAgentMcpAdapter, _init_git_repo(), _make_dummy_task(), MockDriver, MonkeyPatch, Path (+25 more)

### Community 3 - "ConcurrencyGovernor"
Cohesion: 0.07
Nodes (37): Concurrent Evaluation Isolation & Universal Progress Budgeting Implementation Plan, Proposed File Changes, Task 1: Dynamic Machine-Aware Concurrency Governor, Task 4: Blind Extraction & Verification Pipeline, Task 5: End-to-End Concurrent Runner & Integration, 1. Executive Summary & Goals, 2. Dynamic Concurrency Governor, 3. Strict Docker Sandbox Quotas & Volume Isolation (+29 more)

### Community 4 - "ClaudeCliDriver"
Cohesion: 0.10
Nodes (40): Name of the evaluation arm., ClaudeCliDriver, ClaudeCliDriverError, estimate_cost_usd(), find_superstate_binary(), _first(), Any, Path (+32 more)

### Community 5 - "DriverTelemetry"
Cohesion: 0.10
Nodes (48): 2. Core Objectives, DriverTelemetry, Outcome and telemetry metrics from a single driver invocation turn., Unguided baseline adapter enforcing complete isolation from rules or skills., VanillaAdapter, _make_dummy_task(), MockDriver, Any (+40 more)

### Community 6 - "AnswerKeyGuard"
Cohesion: 0.07
Nodes (39): Concurrent Verifier Seal Resolution & 4-Worker Concurrency Plan, Task 1: TaskSpec `has_verifier_dockerfile` Seal Resilience & Test, Task 2: Concurrency 4 Configuration, Task 3: Full Verification Suite, Task 4: Commit & Merge, Task 5: Launch Benchmark Suite at Concurrency 4, 1. Overview & Objective, 2. Benchmark Task Suite: 5-Task Representative Pilot (+31 more)

### Community 7 - "SuperstateDaemonAdapter"
Cohesion: 0.10
Nodes (25): is_pid_alive(), Any, BudgetHook, Path, Check if process with given PID is alive., Adapter executing tasks autonomously via the detached Superstate DaemonRunner., Name of the evaluation arm., Report execution provenance metadata. (+17 more)

### Community 8 - "test_superstate_daemon_adapter.py"
Cohesion: 0.09
Nodes (39): Path, Driver stub returning a canned gate proposal., A gate that passes before any work cannot discriminate, so it must be refused.…, The driver must never gate on /tests/ -- that is the answer key., The daemon expands the bare `agy` preset without --model or JSON output.…, The daemon's worker must be told where the project environment actually is. The…, Gate authoring must not be capped so tightly that it silently degrades to no-…, A gate that cannot be derived must be visible in the log, not silent. (+31 more)

### Community 9 - ".execute"
Cohesion: 0.10
Nodes (19): _extract_plan_milestones(), flush(), Milestone, Any, BudgetHook, Extract milestone headers and their targeted verification commands from a plan., Resolve active worktree path from state.json if provisioned., Report which state engine actually drove this run. (+11 more)

### Community 10 - "superstate.py"
Cohesion: 0.11
Nodes (28): Hand-authored agent-facing verification gates, one per benchmark task. WHY…, Whether a command reads the sealed held-out grader at the container root., references_sealed_grader(), Remove guidance files the task repo ships. Returns what was removed., strip_preexisting_guidance(), Arm adapters for Vanilla, Superpowers, and Superstate execution., Agent-level autonomous adapter for Superstate over Model Context Protocol…, Superstate daemon evaluation adapter for autonomous detached headless execution. (+20 more)

### Community 11 - "Path"
Cohesion: 0.11
Nodes (19): Task 1: `SuperstateMcpClient` Implementation & Protocol Handshake, 3.3 Agent-Level Autonomous Adapter: `SuperstateAgentMcpAdapter` (`lab/engine/adapters/superstate_agent_mcp.py`), Execution Flow:, Ledger, Path, Initialize the MCP client configuration. Parameters: superstate_bin: Path to…, Resolve a repo path or direct state file path into a state argument string., Invoke CLI binary fallback for low-level state mutation commands. (+11 more)

### Community 12 - "SuperstateMcpAdapter"
Cohesion: 0.05
Nodes (55): Gate precision — read it after every run, Any, BudgetHook, Path, Keep harness files from dirtying the tree that git verification gates inspect., Sanitize workspace by stripping legacy guidance and excluding harness artifacts., Resolve active worktree path from state.json if provisioned., Strip a host-side bridge wrapper when the gate already runs in the sandbox. (+47 more)

### Community 13 - "Design Specification: Native AST Symbol Inspection & Deterministic Context Bounding"
Cohesion: 0.11
Nodes (17): 1. Executive Summary & Problem Context, 2.1 The Zero Prompt Engineering Invariant, 2.2 Non-Goals, 2. Strict Invariants & Non-Goals, 3.1 `superstate-syntax` Engine Enhancements, 3.2 `superstate-cli` Command: `superstate inspect`, 3. Architecture & Interfaces, 4. Error Handling & Edge Cases (+9 more)

### Community 14 - "test_canary_task_set.py"
Cohesion: 0.14
Nodes (15): ArgumentParser, is_canary(), Whether a task belongs to the fast 3-task Canary slice., build_parser(), Unit tests for the Canary 3 task set and runner configuration., Canary set must contain exactly the 3 designated fast tri-language repository…, is_canary must identify canary tasks and reject others., Every canary task must belong to DISCRIMINATING_TASKS to provide valid signal. (+7 more)

### Community 15 - "handle"
Cohesion: 0.13
Nodes (25): ContainerExec, _error(), handle(), log(), main(), Any, A minimal stdio MCP server exposing exactly one tool: exec in ONE container.…, Handle one JSON-RPC message. Returns a response, or None for notifications. (+17 more)

### Community 16 - "load_task_from_dir"
Cohesion: 0.17
Nodes (14): _extract_collect_commands(), load_task_from_dir(), Any, Path, Ingest collector command sequences used to extract test or run artifacts., Parse task.toml and instruction.md from task_dir into a TaskSpec., Directory holding the held-out verifier (Dockerfile, test.sh, grader.py)., main() (+6 more)

### Community 17 - "ProgressTracker"
Cohesion: 0.16
Nodes (12): Task 3: Universal Progress-Earned Budget Tracker, Record completed milestone and grant progress lease extension if within max…, ProgressTracker, Path, Monitors workspace state and awards progress-earned lease extensions to any arm., Query current HEAD commit hash from workspace git repository., Parse completed task count from .agent-state/state.json if present., Check for forward progress signals and trigger lease extension on advancement. (+4 more)

### Community 18 - "McpProcessError"
Cohesion: 0.16
Nodes (16): 3.1 `SuperstateMcpClient` (`lab/engine/mcp/client.py`), Responsibilities:, Exception, McpError, McpProcessError, McpRpcError, McpTimeoutError, Read a single line from stdout with a timeout deadline. Parameters: deadline:… (+8 more)

### Community 19 - "test_differential.py"
Cohesion: 0.06
Nodes (48): deepdiff, clean_json_response(), compute_review_metrics(), get_task_instruction(), main(), Any, Offline code review evaluation against harvested false-pass and true-pass runs.…, Compute aggregate precision, recall, and false alarm rate from review results. (+40 more)

### Community 20 - "AblationRunner"
Cohesion: 0.11
Nodes (18): AblationRunner, InsufficientResourcesError, Any, Resolve a cohort entry into (task_id, image, base_budget_sec, task_spec)., Execute a matrix of tasks x arms concurrently using the dynamic governor., Raised when the host cannot safely run even a single concurrent evaluation., Executes benchmark tasks across evaluation arms with resource and lease…, A cohort of 8 GB tasks must not be dispatched at the 4 GB default width. (+10 more)

### Community 21 - "DockerManager"
Cohesion: 0.12
Nodes (17): DockerClient, DiskSpaceError, DockerManager, Path, Copy the task repository out of `image` into the host directory `dest`. A bind…, Raised when host disk space falls below the critical emergency threshold., Prune dangling images, stopped containers, and unreferenced volumes., Check available disk space. Prune docker if below min_free_gb; raise if below… (+9 more)

### Community 22 - "Working in superstate-eval"
Cohesion: 0.09
Nodes (22): A bad gate is worse than no gate, Arm input parity — the single most common source of false findings, Arms — check the name before comparing anything, Before running anything: check the ledger, Do not run `vanilla` by default, Drivers, Evaluation Philosophy: Autonomous TDD vs. Answer-Key Cheating, Full Benchmark: `SWE-Core` (`--core`) (+14 more)

### Community 23 - "ImageBuildError"
Cohesion: 0.29
Nodes (5): ImageBuildError, Build an image from `context_dir` and return its tag. Used for the held-out…, Build an image from an inline Dockerfile with no build context., Stop docker-py invoking every configured credential helper on build. docker-py…, Raised when an image (typically the held-out verifier) cannot be built.

### Community 24 - "test_ablation_runner.py"
Cohesion: 0.18
Nodes (19): Any, Auditable execution telemetry across an evaluation unit., RunTelemetry, compute_control_plane_lift(), _harness_of(), Cluster failures per arm so recurring defects are visible. A pass rate says an…, Render clustered failures as text, most frequent first., Measure what each layer adds to a given harness, task by task. This evaluation… (+11 more)

### Community 25 - "test_superstate_mcp_client.py"
Cohesion: 0.09
Nodes (26): FakeMcpServerProcess, MonkeyPatch, Path, Tests for SuperstateMcpClient. Verifies stdio JSON-RPC MCP protocol handshake,…, Verify initialize, initialized notification, tools/list, and caching 25 tools., Verify call_tool parses text and nested json in result.content., Verify call_tool raises McpRpcError on JSON-RPC error payload., Verify context manager automatically starts and terminates child process. (+18 more)

### Community 26 - "Working in superstate-eval"
Cohesion: 0.11
Nodes (19): A bad gate is worse than no gate, Arm input parity — the single most common source of false findings, Arms — check the name before comparing anything, Before running anything: check the ledger, Do not run `vanilla` by default, Drivers, Evaluation Philosophy: Autonomous TDD vs. Answer-Key Cheating, Gated vs ungated — why it decides what a run measures (+11 more)

### Community 27 - ".__init__"
Cohesion: 0.10
Nodes (18): Autonomous TDD DAG Execution Implementation Plan, Global Constraints, Task 1: Add `tdd_dag` Configuration and 2-Node DAG Construction in `SuperstateDaemonAdapter`, Task 2: Register `superstate_daemon_dag` Arm and Verify Parity, Task 3: Register and Execute EXP-064 Canary Benchmark, Evaluation Philosophy & Autonomous TDD Benchmark Architecture Implementation Plan, Global Constraints, Task 1: Author and Publish `docs/EVALUATION-PHILOSOPHY.md` (+10 more)

### Community 28 - "test_runner.py"
Cohesion: 0.06
Nodes (41): EvaluationResult, Outcome of blind verification and patch extraction., _fake_sandbox_factory(), Build a run_sandbox stand-in that writes a passing verifier artifact., test_ablation_runner_default_execution_mounts_workspace_into_container(), run(), Path, test_agy_cli_driver_run_in_container_sets_workdir() (+33 more)

### Community 29 - "SuperstateMcpClient"
Cohesion: 0.12
Nodes (16): Global Constraints, MCP Evaluation Dual Architecture Implementation Plan, Task 2: Harness-Level Adapter (`SuperstateMcpAdapter`), Task 3: Driver MCP Support & Agent-Level Autonomous Adapter, Task 4: Runner Integration & Benchmark Parity Verification, 3.2 Harness-Level Adapter: `SuperstateMcpAdapter` (`lab/engine/adapters/superstate_mcp.py`), Execution Flow:, Client for communicating with the superstate MCP server over stdio JSON-RPC.… (+8 more)

### Community 30 - "test_docker_integration.py"
Cohesion: 0.13
Nodes (21): collections_abc, RuntimeError, Raised when the task repository cannot be materialized onto the host., WorkspaceSeedError, requires_docker, fixture, Path, Integration tests exercising a real Docker daemon. The unit suite mocks… (+13 more)

### Community 31 - "pytest"
Cohesion: 0.17
Nodes (13): agent_gate_for(), Return the hand-authored agent-facing gate for a task, if one exists. This is…, load_benchmark_tasks(), Scan directory tree for benchmark task directories containing task.toml., pytest, image_present(), main(), Run each agent-facing gate inside a pristine task container. A gate that PASSES… (+5 more)

### Community 32 - "TaskSpec"
Cohesion: 0.13
Nodes (24): Cross-Agent Relay & Autonomous Detached Daemon Evaluation Implementation Plan, Global Constraints, Task 1: Implement `SuperstateRelayAdapter`, Task 2: Implement `SuperstateDaemonAdapter`, Task 3: Wire Adapters into Runner and Add End-to-End Harness Tests, Task 4: Automated Pilot Script & 5-Task Benchmark Execution, Specification of an evaluation benchmark task., TaskSpec (+16 more)

### Community 33 - "MockDriver"
Cohesion: 0.10
Nodes (20): auto_rollback_enabled(), impact_slicing_enabled(), Whether automatic rollback on milestone failure is enabled for the daemon., Whether milestone-scoped test impact slicing is enabled for the daemon., MockDriver, Any, MonkeyPatch, Mock agent driver for testing. (+12 more)

### Community 34 - "Path"
Cohesion: 0.13
Nodes (12): find_superstate_binary(), Path, Resolve the state-engine binary for a named implementation. Resolution is…, Keep harness files from dirtying the tree the git-clean gate inspects. The…, Sanitize workspace so Arm C sees the same blank slate as the control arm., Invoke the state engine, returning (exit_code, stdout)., Unblocked tasks from the plan's dependency DAG (`state ready --json`). This…, The engine's own turnkey prompt (`state prompt --with-graph`). Generating this… (+4 more)

### Community 35 - ".run_sandbox"
Cohesion: 0.12
Nodes (15): Container, Task 2: Container Resource Constraints & Volume Isolation, Dynamic Container Workspace Switching Implementation Plan, Global Constraints, Task 1: Runner Mount Decoupling & Container Symlink Setup, Task 2: Worktree Turn Repointing in Superstate Adapter, Task 3: Live Verification on `db-wal-recovery`, 2. GREEN Phase (+7 more)

### Community 36 - "test_task_sets.py"
Cohesion: 0.23
Nodes (9): excluded_reason(), is_discriminating(), Which tasks a comparison should actually run. The 30-task corpus does not…, Whether a task can contribute signal to an arm-vs-arm comparison., Why a gradeable task is kept out of the core set, or None if it is in., The core set must account for every task, and never include an ungradeable one., A task is in the core set, excluded with a reason, or ungradeable -- never lost., test_every_exclusion_states_a_reason() (+1 more)

### Community 37 - "AgentDriver"
Cohesion: 0.09
Nodes (24): abc, AgentDriver, Any, BudgetHook, Path, Base interfaces and data structures for execution adapters and agent drivers., Run an agent session or turn within the target workspace., Execute a task in the given workspace using the provided driver. (+16 more)

### Community 38 - ".execute"
Cohesion: 0.12
Nodes (14): is_transient_stream_interruption(), Classify whether an error string represents a transient API transport…, Any, BudgetHook, Path, Report state engine, transport, and autonomous tooling provenance. Returns:…, Keep harness files from dirtying the git working tree. Appends harness-internal…, Sanitize workspace by stripping legacy guidance and excluding harness… (+6 more)

### Community 39 - "SuperstateAdapter"
Cohesion: 0.18
Nodes (16): Adapter executing tasks under the deterministic Superstate engine., Extract a clean, concise finding from the turn's response to keep prompts…, SuperstateAdapter, Path, test_switch_container_workspace_handles_exec_nonzero_exit(), test_switch_container_workspace_handles_none_container(), test_switch_container_workspace_no_worktree_mode(), test_switch_container_workspace_resets_to_root() (+8 more)

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
Cohesion: 0.08
Nodes (32): collections, itertools, random, bootstrap_ci(), collect(), _infra_failure(), main(), permutation_p() (+24 more)

### Community 46 - "BaseCliDriver"
Cohesion: 0.15
Nodes (13): BaseCliDriver, CliDriverError, first(), Any, Path, RuntimeError, Turn the CLI's JSON result into telemetry., Raised when the agent CLI cannot be located or invoked. (+5 more)

### Community 47 - "reporter.py"
Cohesion: 0.17
Nodes (17): _failure_signature(), generate_comparison_summary(), Any, Evaluation reporter generating cost-efficiency frontier comparisons., Collapse a failure reason to a comparable class, stripping run-specific detail., Group run telemetry by paradigm arm and calculate core efficiency metrics., Render control-plane lift, with the caveat that small n cannot support it., Render summary as a formatted text table for reports. (+9 more)

### Community 48 - "test_docker_manager_shunting.py"
Cohesion: 0.19
Nodes (15): find_static_superstate_binary(), Locate pre-compiled static Linux superstate binary if available on host. Checks…, MonkeyPatch, Path, Tests for mounting static Linux superstate binary into sandbox containers., Verify find_static_superstate_binary respects SUPERSTATE_LINUX_BIN when file…, Verify find_static_superstate_binary falls back when SUPERSTATE_LINUX_BIN does…, Verify find_static_superstate_binary returns None when no binaries exist. (+7 more)

### Community 49 - "Design Specification: Agent-Driven Worktrees & Full-Context Turnkey Execution"
Cohesion: 0.12
Nodes (15): 1.1 `ExecutionState` Model (`crates/superstate-core/src/models.rs`), 1.2 Full-Context Turnkey Prompt (`crates/superstate-core/src/prompt.rs`), 1. Problem Statement & Motivation, 2.1 Default In-Place Execution in `state init`, 2.2 Dedicated Agent Worktree Commands, 2. Core Architectural Principles, 3.1 Universal Zero-Turn Direct Initialization, 3.2 Dynamic Turn & Milestone Execution (+7 more)

### Community 50 - "SuperpowersAdapter"
Cohesion: 0.15
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
Cohesion: 0.25
Nodes (14): 3.1 `SuperstateRelayAdapter` (`lab/engine/adapters/superstate_relay.py`), 3.2 `SuperstateDaemonAdapter` (`lab/engine/adapters/superstate_daemon.py`), 3. Architecture & Adapter Specifications, Path, HeldOutVerifier, Builds and runs the task's own verifier image., _manager(), Path (+6 more)

### Community 56 - "Design Specification: Autonomous TDD DAG Execution & Hand-Authored Fixture Elimination"
Cohesion: 0.13
Nodes (14): 1. Executive Summary & Context, 2.1 Milestone Specifications, 2. Architecture: Deterministic 2-Node TDD State Graph, 3.1 Arm Definition, 3.2 State Initialization (`_init_daemon_state`), 3.3 Zero Prompt Engineering Compliance, 3. Harness Integration in `superstate-eval`, 4.1 Experiment EXP-064 (+6 more)

### Community 57 - "Design Specification: Evaluation Philosophy & Autonomous TDD Benchmark Architecture"
Cohesion: 0.13
Nodes (14): 1. Executive Summary & Context, 2.1 The Four Non-Negotiable Invariants, 2. The Core Philosophy, 3.1 Milestone 1: `tdd-reproduction-test` (Gate Derivation), 3.2 Milestone 2: `fix-implementation` (Autonomous Convergence), 3.3 Post-Run Held-Out Grading, 3. Architecture: Autonomous TDD State DAG, 4.1 `superstate-eval/AGENTS.md` (+6 more)

### Community 58 - "test_gate_fixtures.py"
Cohesion: 0.15
Nodes (12): The gate fixtures are the contract of record, so their shape is worth pinning., Gating on /tests/ would let the agent read the answer key it is scored against., The sealed grader is at /tests/, whereas /app/<pkg>/tests/ is an in-repo suite., A gate that cannot fail cannot discriminate, and the worker stops the moment it…, A fixture with a quoting error fails for the wrong reason and looks like a hard…, A derived gate once reduced to `test -f <file> && not-on-main`, satisfiable by…, test_every_fixture_is_valid_shell(), test_every_pilot_task_has_a_fixture() (+4 more)

### Community 59 - "Hybrid Tool Output Shunting & Distillation Design Spec"
Cohesion: 0.14
Nodes (13): 1. Problem Statement & Context, 2. Core Architectural Objectives, 3. System Architecture & Data Flow, 4.1 Container Bridge Shunting (`lab/engine/drivers/agy_cli.py`), 4.2 Shunt CLI Command Hardening (`crates/superstate-cli/src/commands/shunt.rs`), 4.3 In-Container Native Binary Mounting (`lab/sandbox/docker_manager.py`), 4.4 Linux Static Build Pipeline (`repos/superstate`), 4. Component Specifications (+5 more)

### Community 60 - "test_approval.py"
Cohesion: 0.29
Nodes (9): is_waiting_for_user_input(), Analyze agent response text to detect if the agent paused for human approval or…, Tests for Mechanical User and Autonomous Human-in-the-Loop Elimination., test_is_waiting_for_user_input_detects_ask_question_tool(), test_is_waiting_for_user_input_detects_standard_approval_prompts(), test_is_waiting_for_user_input_detects_superpowers_state_gates(), test_is_waiting_for_user_input_ignores_normal_completions(), test_resolve_next_turn_prompt_returns_mechanical_approval() (+1 more)

### Community 61 - "unittest_mock"
Cohesion: 0.11
Nodes (26): apply_contract(), apply_generic_rules(), contracts_enabled(), generic_rules_enabled(), Arm-specific behavioural prompt contracts, OFF by default. WHY THIS SWITCH…, Whether the portable discipline rules are injected into baseline arms. Separate…, Append the portable discipline rules to a baseline arm's prompt, if enabled., Whether arm-specific behavioural contracts are injected into agent prompts.… (+18 more)

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

### Community 66 - "AgentImageBuilder"
Cohesion: 0.24
Nodes (6): AgentImageBuilder, Docker tags allow a restricted character set; image refs do not., Builds and caches per-task agent images., A deterministic tag: this image holds no secrets, so caching is safe. Unlike…, Build (or reuse) an image with the Claude Code CLI on top of `base_image`., _slug()

### Community 67 - "PilotShowdownRunner"
Cohesion: 0.16
Nodes (10): MockContainer, PilotMockDriver, PilotShowdownRunner, Any, Path, Executes a single benchmark task across evaluation arms with isolated…, Execute task across arms and return structured benchmark outcomes. With…, Predictable mock driver simulating agent behavior for pilot verification. (+2 more)

### Community 68 - ".clean_workspace"
Cohesion: 0.50
Nodes (3): Path, Sanitize workspace by removing all guidance, rule files, and skills., Ensure pristine unguided workspace before execution.

### Community 69 - "_ScriptedDriver"
Cohesion: 0.17
Nodes (9): SimpleNamespace, Driver stub returning a different response per successive turn., An incomplete gate is worse than no gate: the worker stops the moment it…, A critique may only strengthen the contract. A no-op reply keeps the original., A widened gate that already passes cannot discriminate, so the original stands., _ScriptedDriver, test_critique_cannot_weaken_the_gate(), test_critique_rejecting_an_already_passing_gate() (+1 more)

### Community 70 - "Global Constraints"
Cohesion: 0.33
Nodes (5): Global Constraints, Native AST Symbol Inspection & Deterministic Context Bounding Implementation Plan, Task 1: `superstate-syntax` Engine Extensions, Task 2: `superstate-cli` `inspect` Command Implementation & System Installation, Task 3: Arm Input Parity Verification & Container Execution Check

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
Cohesion: 0.25
Nodes (7): 1. Executive Summary & Objective, 2. Architecture & Components, 3.4 Driver Integration (`lab/engine/drivers/claude_cli.py`), 3.5 Runner Arms Configuration (`lab/engine/runner.py`), 3. Detailed Component Design, 4. Verification & Testing Strategy, Design Specification: MCP Evaluation Dual Architecture (`superstate-eval`)

### Community 77 - ".__exit__"
Cohesion: 0.40
Nodes (3): BaseException, Terminate the server process cleanly upon exiting context., Cleanly terminate the superstate child process and close pipes.

### Community 78 - "Run `--canary` or `--core`, not toy puzzles or the whole corpus"
Cohesion: 0.67
Nodes (3): Full Benchmark: `SWE-Core` (`--core`), Rapid Iteration: `SWE-Canary` (`--canary`), Run `--canary` or `--core`, not toy puzzles or the whole corpus

### Community 80 - "superstate-eval"
Cohesion: 0.20
Nodes (10): A note on what this harness has taught us, Autonomous TDD & The Anti-Cheating Invariant, Differential parity, How a run works, Layout, Quick start, superstate-eval, Tasks & Repository-First Suites (+2 more)

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

### Community 91 - "test_superstate_resilience.py"
Cohesion: 0.27
Nodes (7): FlakyGateDriver, Path, Tests for Superstate milestone retry loops and greenfield resilience., Verify that a greenfield workspace without .git does not crash when advancing…, Fails on turn 1 by not creating marker.txt, then creates it on turn 2 after…, test_greenfield_workspace_advances_without_git(), test_milestone_retry_loop_on_failed_gate()

### Community 93 - "BudgetPolicy"
Cohesion: 0.17
Nodes (11): superstate-eval Local Assessment Repository Implementation Plan, Tasks, Verification & Completion Gates, BudgetPolicy, Progress-earned budget policy and execution telemetry accounting. Allows…, Manages progress-earned execution timeouts., Tests for Progress-Earned Budget Policy and Telemetry Accounting., test_budget_policy_earn_extension_on_progress() (+3 more)

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

### Community 101 - ".call_tool"
Cohesion: 0.16
Nodes (9): Any, Return cached map of discovered tools keyed by name., Return server identification info received during protocol handshake., Send a JSON-RPC request and wait for the corresponding response. Parameters:…, Invoke an MCP tool and parse both text and structured JSON content. Parameters:…, Terminate running background daemon processes., Run fail-closed environment and driver diagnostic preflight., Perform health checks and diagnosis on state integrity. (+1 more)

### Community 102 - "harvest_run_diffs.py"
Cohesion: 0.40
Nodes (5): get_git_diff_and_untracked(), harvest(), Path, Harvest labelled diffs and execution telemetry from /tmp/superstate_eval_runs.…, Extract git diff from initial baseline commit to current state, including…

### Community 105 - "Experiment ledger"
Cohesion: 0.40
Nodes (4): Cross-cutting findings, Experiment ledger, Rules, Status values

### Community 106 - ".run_task"
Cohesion: 0.20
Nodes (7): Model the harness was configured with, when the driver knows it., NoDriverConfiguredError, RuntimeError, Execute a single task under the specified arm and budget policy. Guarantees: 1.…, Translate a task's declared network policy into a docker network_mode. A task…, Raised when a live evaluation is requested without an agent driver., resolve_network_mode()

### Community 107 - "Feature Implementation Plan"
Cohesion: 0.40
Nodes (4): Feature Implementation Plan, Task 1: Setup database schema, Task 2: Implement repository methods, Task 3: Expose REST endpoint

### Community 108 - "run_exp060.sh"
Cohesion: 0.40
Nodes (4): run_exp060.sh script, SUPERSTATE_EVAL_DERIVE_GATES, SUPERSTATE_EVAL_GENERIC_RULES, SUPERSTATE_EVAL_PROMPT_CONTRACTS

### Community 109 - "is_unmeasurable"
Cohesion: 0.17
Nodes (12): A task with no sealed grader cannot be scored, is_unmeasurable(), Reason a task cannot be scored, or None if it can., Canary tasks must have held-out verifiers and not be unmeasurable., test_canary_tasks_are_measurable(), A task whose grader cannot run scores every arm zero and shrinks the…, A task with no held-out tests/ cannot be scored, so it must be listed. The…, test_tasks_without_a_sealed_grader_are_marked_unmeasurable() (+4 more)

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
- **270 isolated node(s):** `superstate-eval`, `launch_datacurve_3arm.sh script`, `launch_datacurve_clean.sh script`, `launch_datacurve_planned.sh script`, `launch_derived_gates.sh script` (+265 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 963 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **31 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TaskSpec` connect `TaskSpec` to `extract_and_grade`, `pathlib`, `SuperstateAgentMcpAdapter`, `ClaudeCliDriver`, `DriverTelemetry`, `AnswerKeyGuard`, `SuperstateDaemonAdapter`, `test_superstate_daemon_adapter.py`, `.execute`, `superstate.py`, `SuperstateMcpAdapter`, `load_task_from_dir`, `AblationRunner`, `test_ablation_runner.py`, `.__init__`, `test_runner.py`, `pytest`, `MockDriver`, `AgentDriver`, `.execute`, `SuperstateAdapter`, `test_agy_cli_driver.py`, `test_in_container_driver.py`, `BaseCliDriver`, `Control-Plane Evaluation — Plan`, `.run`, `unittest_mock`, `test_state_engine_loop.py`, `AgyCliDriver`, `PilotShowdownRunner`, `.run`, `test_superstate_resilience.py`, `.run_task`?**
  _High betweenness centrality (0.151) - this node is a cross-community bridge._
- **Why does `SuperstateAdapter` connect `SuperstateAdapter` to `TaskSpec`, `pathlib`, `Path`, `PilotShowdownRunner`, `DriverTelemetry`, `AnswerKeyGuard`, `AgentDriver`, `.execute`, `superstate.py`, `SuperstateMcpAdapter`, `Design Specification: Agent-Driven Worktrees & Full-Context Turnkey Execution`, `SuperpowersAdapter`, `AblationRunner`, `test_superstate_resilience.py`, `Global Constraints`, `test_state_engine_loop.py`?**
  _High betweenness centrality (0.078) - this node is a cross-community bridge._
- **Why does `SuperstateMcpClient` connect `SuperstateMcpClient` to `pathlib`, `SuperstateAgentMcpAdapter`, `.call_tool`, `.execute`, `SuperstateDaemonAdapter`, `superstate.py`, `Path`, `3. Detailed Component Design`, `SuperstateMcpAdapter`, `.__exit__`, `McpProcessError`, `test_superstate_mcp_client.py`, `.__init__`?**
  _High betweenness centrality (0.073) - this node is a cross-community bridge._
- **Are the 32 inferred relationships involving `TaskSpec` (e.g. with `Stream 2 — Rust parity — COMPLETE (2026-09-09)` and `Task 1: TaskSpec `has_verifier_dockerfile` Seal Resilience & Test`) actually correct?**
  _`TaskSpec` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 16 inferred relationships involving `DriverTelemetry` (e.g. with `Task 1: Implement `SuperstateRelayAdapter`` and `2. Core Objectives`) actually correct?**
  _`DriverTelemetry` has 16 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `SuperstateAdapter` (e.g. with `Task 3: Universal Zero-Turn Planning in Adapter (`superstate-eval`)` and `2. Core Objectives`) actually correct?**
  _`SuperstateAdapter` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `SuperstateDaemonAdapter` (e.g. with `Cross-Agent Relay & Autonomous Detached Daemon Evaluation Implementation Plan` and `Task 2: Implement `SuperstateDaemonAdapter``) actually correct?**
  _`SuperstateDaemonAdapter` has 13 INFERRED edges - model-reasoned connections that need verification._