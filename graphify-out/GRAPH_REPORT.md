# Graph Report - superstate-eval  (2026-09-14)

## Corpus Check
- 129 files · ~131,968 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 13 file(s) not represented in the graph (top: .log 7, (none) 5, .lock 1)

## Summary
- 1344 nodes · 2921 edges · 81 communities (64 shown, 13 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 162 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `985b3f74`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- AgentDriver
- DriverTelemetry
- AgyCliDriver
- ClaudeCliDriver
- handle
- test_ablation_runner.py
- AnswerKeyGuard
- verifier.py
- task_loader.py
- TurnBasedAdapter
- extract_and_grade
- RunRecorder
- test_docker_integration.py
- BaseCliDriver
- SuperstateMcpAdapter
- test_differential.py
- test_runner.py
- Architecture Specification: Antigravity CLI Driver (`AgyCliDriver`) & Container Execution Bridge
- Architecture Specification: Concurrent Evaluation Isolation & Universal Progress-Earned Budgeting
- Proposed File Changes
- 2. Architectural Design
- Global Constraints
- InContainerClaudeDriver
- Global Constraints
- Feature Implementation Plan
- superstate-eval Local Assessment Repository Implementation Plan
- superstate-eval
- benchmarks/__init__.py
- dag_plan.md
- superstate-eval
- SuperstateAgentMcpAdapter
- Design Specification: Agent-Driven Worktrees & Full-Context Turnkey Execution
- DockerManager
- load_task_from_dir
- test_superstate_mcp_client.py
- Control-Plane Evaluation — Plan
- test_state_engine_loop.py
- SuperpowersAdapter
- test_approval.py
- AgentImageBuilder
- Superstate Resilience, Diagnostic Retry Loops, and Git Native State Tracking Design
- ImageBuildError
- .check_disk_space_or_prune
- Global Constraints
- .execute
- test_superstate_resilience.py
- ConcurrencyGovernor
- SuperstateMcpClient
- SuperstateAdapter
- TaskSpec
- HeldOutVerifier
- Global Constraints
- Design Spec: Dynamic Container Workspace Switching for Worktree Isolation
- McpProcessError
- Concurrent Verifier Seal Resolution & 4-Worker Concurrency Plan
- Global Constraints
- Superstate Massive Adoption & Founder Prestige Roadmap
- 3. Detailed Component Design
- run_weekend_benchmark.sh
- Any
- Frontier Triad Benchmark: Final Evaluation Report
- VanillaAdapter
- ._perform_handshake
- Global Constraints
- FakePipe
- Global Constraints
- .__exit__
- find_superstate_binary
- claude_cli.py
- test_superstate_adapter_gate_failure_stateless_retry
- launch_frontier_claude_haiku.sh
- launch_frontier_condition_b.sh
- launch_frontier_mcp_rerun.sh
- launch_frontier_triad_benchmark.sh
- launch_weekend_run.sh
- test_runner_resolves_mcp_adapters
- test_is_transient_stream_interruption_detection

## God Nodes (most connected - your core abstractions)
1. `TaskSpec` - 91 edges
2. `DriverTelemetry` - 78 edges
3. `SuperstateAdapter` - 76 edges
4. `AgentDriver` - 52 edges
5. `SuperstateMcpClient` - 52 edges
6. `SuperstateMcpAdapter` - 43 edges
7. `AblationRunner` - 43 edges
8. `DockerManager` - 38 edges
9. `MockDriver` - 37 edges
10. `SuperstateAgentMcpAdapter` - 33 edges

## Surprising Connections (you probably didn't know these)
- `MockDriver` --uses--> `TaskSpec`  [INFERRED]
  tests/test_adapters.py → lab/benchmarks/task_loader.py
- `MockDriver` --uses--> `TaskSpec`  [INFERRED]
  tests/test_runner.py → lab/benchmarks/task_loader.py
- `StubDriver` --uses--> `TaskSpec`  [INFERRED]
  tests/test_runner.py → lab/benchmarks/task_loader.py
- `test_a_failing_gate_stops_the_run_and_is_reported()` --uses--> `TaskSpec`  [INFERRED]
  tests/test_state_engine_loop.py → lab/benchmarks/task_loader.py
- `test_both_engines_produce_the_same_arm_outcome()` --uses--> `TaskSpec`  [INFERRED]
  tests/test_state_engine_loop.py → lab/benchmarks/task_loader.py

## Import Cycles
- None detected.

## Communities (81 total, 13 thin omitted)

### Community 0 - "AgentDriver"
Cohesion: 0.07
Nodes (34): AgentDriver, Model the harness was configured with, when the driver knows it., Abstract driver interface communicating with an underlying agent runtime.…, Driver for running evaluation tasks against Google Antigravity CLI (agy).…, AblationRunner, InsufficientResourcesError, NoDriverConfiguredError, Any (+26 more)

### Community 1 - "DriverTelemetry"
Cohesion: 0.12
Nodes (47): DriverTelemetry, Outcome and telemetry metrics from a single driver invocation turn., run(), _make_dummy_task(), MockDriver, Any, parametrize, Path (+39 more)

### Community 2 - "AgyCliDriver"
Cohesion: 0.10
Nodes (38): Name of the evaluation arm., AgyCliDriver, AgyCliDriverError, base_model_name(), estimate_cost_usd(), Any, Path, RuntimeError (+30 more)

### Community 3 - "ClaudeCliDriver"
Cohesion: 0.12
Nodes (38): ClaudeCliDriver, ClaudeCliDriverError, estimate_cost_usd(), find_superstate_binary(), _first(), Any, Path, RuntimeError (+30 more)

### Community 4 - "handle"
Cohesion: 0.13
Nodes (25): ContainerExec, _error(), handle(), log(), main(), Any, A minimal stdio MCP server exposing exactly one tool: exec in ONE container.…, Handle one JSON-RPC message. Returns a response, or None for notifications. (+17 more)

### Community 5 - "test_ablation_runner.py"
Cohesion: 0.05
Nodes (60): BudgetPolicy, Any, Progress-earned budget policy and execution telemetry accounting. Allows…, Manages progress-earned execution timeouts., Record completed milestone and grant progress lease extension if within max…, Auditable execution telemetry across an evaluation unit., RunTelemetry, ProgressTracker (+52 more)

### Community 6 - "AnswerKeyGuard"
Cohesion: 0.11
Nodes (28): Whether the task has a Dockerfile in its tests/ directory., AnswerKeyGuard, is_readable(), Path, Keep the held-out tests unreadable while the agent is working. A host-side…, Make `paths` unreadable for the duration of the block. Nests safely: concurrent…, Copy a directory somewhere readable before it is sealed. The verifier is built…, Whether the current process can list `path`. Used by tests and diagnostics. (+20 more)

### Community 7 - "verifier.py"
Cohesion: 0.18
Nodes (11): Any, Path, Held-out verification in a separate container. The benchmark's own contract…, Build the verifier image for `task` and return its tag., Run the held-out verifier against the collected patch. `logs_dir` must already…, Delete the verifier image so the hidden tests do not linger on the host., Run the built verifier image against the collected patch., Docker tags allow a restricted character set; task ids do not. (+3 more)

### Community 8 - "task_loader.py"
Cohesion: 0.08
Nodes (30): Benchmark task specification and loader module. Parses SWE-bench / Harbor style…, AgentAdapter, Base interfaces and data structures for execution adapters and agent drivers., Abstract evaluation adapter configuring workspace guidance and managing turns., Remove guidance files the task repo ships. Returns what was removed., Outcome and telemetry metrics for a complete task execution run., strip_preexisting_guidance(), TaskRunResult (+22 more)

### Community 9 - "TurnBasedAdapter"
Cohesion: 0.14
Nodes (13): is_transient_stream_interruption(), Any, BudgetHook, Path, Run an agent session or turn within the target workspace., Execute a task in the given workspace using the provided driver., Classify whether an error string represents a transient API transport…, Base template adapter managing bounded turn execution and mechanical approval. (+5 more)

### Community 10 - "extract_and_grade"
Cohesion: 0.10
Nodes (37): compute_test_metrics(), extract_and_grade(), _extract_blind_patch(), _inject_tests_to_container(), Any, Path, Extract patch by committing workspace changes and running task collection…, Inject tests directory into container at /tests using AnswerKeyGuard. (+29 more)

### Community 11 - "RunRecorder"
Cohesion: 0.13
Nodes (15): _clip(), MilestoneRecord, Any, Path, Run trace capture: the diagnostic record an evaluation leaves behind. Pass/fail…, Capture one driver turn, including the prompt that produced it., Capture a milestone attempt and its gate verdict., Persist the full held-out verifier output, untruncated. (+7 more)

### Community 12 - "test_docker_integration.py"
Cohesion: 0.15
Nodes (20): RuntimeError, Raised when the task repository cannot be materialized onto the host., WorkspaceSeedError, requires_docker, fixture, Path, Integration tests exercising a real Docker daemon. The unit suite mocks…, End-to-end: build the verifier image and have it write reward.json. Mirrors the… (+12 more)

### Community 13 - "BaseCliDriver"
Cohesion: 0.16
Nodes (13): BaseCliDriver, CliDriverError, first(), Any, Path, RuntimeError, Turn the CLI's JSON result into telemetry., Raised when the agent CLI cannot be located or invoked. (+5 more)

### Community 14 - "SuperstateMcpAdapter"
Cohesion: 0.06
Nodes (49): Any, BudgetHook, Path, Keep harness files from dirtying the tree that git verification gates inspect., Sanitize workspace by stripping legacy guidance and excluding harness artifacts., Resolve active worktree path from state.json if provisioned., Strip a host-side bridge wrapper when the gate already runs in the sandbox., Execute a milestone verification command on the host or inside a container. (+41 more)

### Community 15 - "test_differential.py"
Cohesion: 0.19
Nodes (17): check_binaries(), normalize_state(), fixture, Path, Differential parity testing between superstate (Rust) and agent-rules (Python).…, Resolve a binary from env, then PATH (only if a name is given), then fallbacks.…, Both engines must parse a DAG plan and traverse every task identically., Recording an epistemic note must produce identical state on both engines. (+9 more)

### Community 16 - "test_runner.py"
Cohesion: 0.13
Nodes (26): EvaluationResult, Blind patch extraction and held-out verifier scoring. Executes uniformly across…, Outcome of blind verification and patch extraction., MockDriver, Any, parametrize, Path, Tests for AblationRunner telemetry and metrics integration. Validates that… (+18 more)

### Community 17 - "Architecture Specification: Antigravity CLI Driver (`AgyCliDriver`) & Container Execution Bridge"
Cohesion: 0.17
Nodes (11): 1. Executive Summary & Context, 2. Core Objectives, 3.1 Class Definition (`lab/engine/drivers/agy_cli.py`), 3.2 CLI Binary Resolution, 3.3 Command Construction, 3.4 Telemetry & Pricing, 3. Architecture & Driver Implementation, 4. Container Execution Bridge (`./run-in-container`) (+3 more)

### Community 18 - "Architecture Specification: Concurrent Evaluation Isolation & Universal Progress-Earned Budgeting"
Cohesion: 0.22
Nodes (8): 1. Executive Summary & Goals, 2. Dynamic Concurrency Governor, 3. Strict Docker Sandbox Quotas & Volume Isolation, 4. Universal Progress-Earned Budget Policy, 5. Blind Extraction and Grading Pipeline, 6. Verification and Efficacy Frontiers, Architecture Specification: Concurrent Evaluation Isolation & Universal Progress-Earned Budgeting, Core Objectives

### Community 19 - "Proposed File Changes"
Cohesion: 0.25
Nodes (7): Concurrent Evaluation Isolation & Universal Progress Budgeting Implementation Plan, Proposed File Changes, Task 1: Dynamic Machine-Aware Concurrency Governor, Task 2: Container Resource Constraints & Volume Isolation, Task 3: Universal Progress-Earned Budget Tracker, Task 4: Blind Extraction & Verification Pipeline, Task 5: End-to-End Concurrent Runner & Integration

### Community 20 - "2. Architectural Design"
Cohesion: 0.22
Nodes (8): 1. Context & Motivation, 2.1 EvaluationResult Dataclass Extension, 2.2 Metric Extraction Helper, 2.3 AblationRunner Telemetry Integration, 2.4 CLI Output Formatting, 2. Architectural Design, 3. Testing & Verification, Design Specification: Test Pass Fraction & Test Statistics Propagation

### Community 21 - "Global Constraints"
Cohesion: 0.33
Nodes (5): Antigravity CLI Driver (`AgyCliDriver`) Implementation Plan, Global Constraints, Task 1: Implement `AgyCliDriver` Core and Container Execution Bridge, Task 2: Verify Baseline and System Integration, Task 3: Execute Live Single-Task Smoke Run

### Community 22 - "InContainerClaudeDriver"
Cohesion: 0.16
Nodes (21): _first(), InContainerClaudeDriver, InContainerDriverError, Any, Path, RuntimeError, Raised when the in-container agent cannot be invoked., Build the shell line executed inside the container. The prompt is base64'd so… (+13 more)

### Community 23 - "Global Constraints"
Cohesion: 0.40
Nodes (4): Global Constraints, Task 1: Extend EvaluationResult and Implement compute_test_metrics, Task 2: Integrate Test Metrics into Runner Telemetry and CLI Output, Test Pass Fraction & Test Statistics Implementation Plan

### Community 24 - "Feature Implementation Plan"
Cohesion: 0.40
Nodes (4): Feature Implementation Plan, Task 1: Setup database schema, Task 2: Implement repository methods, Task 3: Expose REST endpoint

### Community 25 - "superstate-eval Local Assessment Repository Implementation Plan"
Cohesion: 0.50
Nodes (3): superstate-eval Local Assessment Repository Implementation Plan, Tasks, Verification & Completion Gates

### Community 26 - "superstate-eval"
Cohesion: 0.20
Nodes (9): A note on what this harness has taught us, Differential parity, How a run works, Layout, Quick start, superstate-eval, Tasks, What is measured (+1 more)

### Community 34 - "SuperstateAgentMcpAdapter"
Cohesion: 0.06
Nodes (47): Any, BudgetHook, Path, Report state engine, transport, and autonomous tooling provenance. Returns:…, Keep harness files from dirtying the git working tree. Appends harness-internal…, Sanitize workspace by stripping legacy guidance and excluding harness…, Strip host-side bridge scripts when running verification inside the container.…, Execute a verification command either inside a container sandbox or on the… (+39 more)

### Community 35 - "Design Specification: Agent-Driven Worktrees & Full-Context Turnkey Execution"
Cohesion: 0.12
Nodes (15): 1.1 `ExecutionState` Model (`crates/superstate-core/src/models.rs`), 1.2 Full-Context Turnkey Prompt (`crates/superstate-core/src/prompt.rs`), 1. Problem Statement & Motivation, 2.1 Default In-Place Execution in `state init`, 2.2 Dedicated Agent Worktree Commands, 2. Core Architectural Principles, 3.1 Universal Zero-Turn Direct Initialization, 3.2 Dynamic Turn & Milestone Execution (+7 more)

### Community 36 - "DockerManager"
Cohesion: 0.13
Nodes (18): DockerClient, Builds the image the agent actually runs inside. The agent must not run on the…, DiskSpaceError, DockerManager, Docker lifecycle and host disk space management. Ensures deterministic…, Raised when host disk space falls below the critical emergency threshold., Prune dangling images, stopped containers, and unreferenced volumes., Manages Docker containers and host disk resource reclamation. (+10 more)

### Community 37 - "load_task_from_dir"
Cohesion: 0.18
Nodes (15): _extract_collect_commands(), load_benchmark_tasks(), load_task_from_dir(), Any, Path, Ingest collector command sequences used to extract test or run artifacts., Parse task.toml and instruction.md from task_dir into a TaskSpec., Scan directory tree for benchmark task directories containing task.toml. (+7 more)

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
Cohesion: 0.21
Nodes (7): Any, Path, Adapter configuring markdown rules and vendored superpowers skills., Install markdown guidance and copy superpowers skills into workspace., Configure workspace with Superpowers guidance before execution begins., Record whether the vendored skills library was actually installed., SuperpowersAdapter

### Community 42 - "test_approval.py"
Cohesion: 0.29
Nodes (9): is_waiting_for_user_input(), Analyze agent response text to detect if the agent paused for human approval or…, Tests for Mechanical User and Autonomous Human-in-the-Loop Elimination., test_is_waiting_for_user_input_detects_ask_question_tool(), test_is_waiting_for_user_input_detects_standard_approval_prompts(), test_is_waiting_for_user_input_detects_superpowers_state_gates(), test_is_waiting_for_user_input_ignores_normal_completions(), test_resolve_next_turn_prompt_returns_mechanical_approval() (+1 more)

### Community 43 - "AgentImageBuilder"
Cohesion: 0.24
Nodes (6): AgentImageBuilder, Docker tags allow a restricted character set; image refs do not., Builds and caches per-task agent images., A deterministic tag: this image holds no secrets, so caching is safe. Unlike…, Build (or reuse) an image with the Claude Code CLI on top of `base_image`., _slug()

### Community 44 - "Superstate Resilience, Diagnostic Retry Loops, and Git Native State Tracking Design"
Cohesion: 0.20
Nodes (9): 1. Context & Motivation, 2. Goals & Non-Goals, 3.1 Diagnostic Retry Loop in `lab/engine/adapters/superstate.py`, 3.2 Greenfield Git Resilience, 3. Architecture & Mechanics, 4. Verification & Testing, Goals, Non-Goals (+1 more)

### Community 45 - "ImageBuildError"
Cohesion: 0.29
Nodes (5): ImageBuildError, Build an image from `context_dir` and return its tag. Used for the held-out…, Build an image from an inline Dockerfile with no build context., Stop docker-py invoking every configured credential helper on build. docker-py…, Raised when an image (typically the held-out verifier) cannot be built.

### Community 46 - ".check_disk_space_or_prune"
Cohesion: 0.25
Nodes (5): Container, Path, Copy the task repository out of `image` into the host directory `dest`. A bind…, Check available disk space. Prune docker if below min_free_gb; raise if below…, Run a container with guaranteed teardown upon context exit. Guarantees that the…

### Community 47 - "Global Constraints"
Cohesion: 0.25
Nodes (7): Global Constraints, Superstate Resilience and Diagnostic Retry Loop Implementation Plan, Task 1: Implement Greenfield Git Handling in `lab/engine/adapters/superstate.py`, Task 2: Implement Milestone Diagnostic Retry Loop in `lab/engine/adapters/superstate.py`, Task 3: Unit Tests for Retry Loop & Greenfield Handling, Task 4: Native Git Initialization in Rust `superstate`, Task 5: Verification & Checkpoint

### Community 48 - ".execute"
Cohesion: 0.08
Nodes (25): _extract_plan_milestones(), flush(), Milestone, Any, BudgetHook, Path, Extract milestone headers and their targeted verification commands from a plan., Resolve active worktree path from state.json if provisioned. (+17 more)

### Community 49 - "test_superstate_resilience.py"
Cohesion: 0.27
Nodes (7): FlakyGateDriver, Path, Tests for Superstate milestone retry loops and greenfield resilience., Verify that a greenfield workspace without .git does not crash when advancing…, Fails on turn 1 by not creating marker.txt, then creates it on turn 2 after…, test_greenfield_workspace_advances_without_git(), test_milestone_retry_loop_on_failed_gate()

### Community 50 - "ConcurrencyGovernor"
Cohesion: 0.12
Nodes (23): ConcurrencyGovernor, Path, Machine-aware dynamic concurrency governor for isolated evaluation execution., Block until an execution slot is available under live resource constraints., Release an active execution slot and notify waiting tasks., Context manager acquiring a dynamic concurrency slot., Hardware capacity snapshot used to determine safe concurrency bounds., Governs evaluation concurrency dynamically based on host machine resources. (+15 more)

### Community 51 - "SuperstateMcpClient"
Cohesion: 0.13
Nodes (17): Path, Client for communicating with the superstate MCP server over stdio JSON-RPC.…, Return True if the underlying server process is active and alive., Invoke an MCP tool and parse both text and structured JSON content. Parameters:…, Resolve a repo path or direct state file path into a state argument string., Initialize state machine tracking from a plan markdown or direct goal., Retrieve bounded turnkey prompt for the active task., Advance the milestone state machine past the current task. (+9 more)

### Community 52 - "SuperstateAdapter"
Cohesion: 0.15
Nodes (16): Adapter executing tasks under the deterministic Superstate engine., Extract a clean, concise finding from the turn's response to keep prompts…, Strip a host-side bridge wrapper when the gate already runs in the sandbox., SuperstateAdapter, Path, test_switch_container_workspace_handles_exec_nonzero_exit(), test_switch_container_workspace_handles_none_container(), test_switch_container_workspace_no_worktree_mode() (+8 more)

### Community 53 - "TaskSpec"
Cohesion: 0.11
Nodes (16): Specification of an evaluation benchmark task., TaskSpec, estimate_cost_usd(), Shared plumbing for agent drivers that shell out to a CLI. Subclasses supply…, Cost from explicit rates. Returns 0.0 when rates are unknown. Deliberately…, An AgentDriver that runs the agent CLI inside the task sandbox. This is the…, A cohort of 8 GB tasks must not be dispatched at the 4 GB default width., test_run_cohort_forwards_task_specs_and_driver() (+8 more)

### Community 54 - "HeldOutVerifier"
Cohesion: 0.37
Nodes (10): HeldOutVerifier, Builds and runs the task's own verifier image., _manager(), Path, The verifier image is the held-out answer key; it must not linger on the host., _Task, test_keep_image_is_opt_in_for_debugging(), test_verifier_image_is_removed_after_grading() (+2 more)

### Community 55 - "Global Constraints"
Cohesion: 0.33
Nodes (5): Dynamic Container Workspace Switching Implementation Plan, Global Constraints, Task 1: Runner Mount Decoupling & Container Symlink Setup, Task 2: Worktree Turn Repointing in Superstate Adapter, Task 3: Live Verification on `db-wal-recovery`

### Community 56 - "Design Spec: Dynamic Container Workspace Switching for Worktree Isolation"
Cohesion: 0.33
Nodes (5): 1. Problem Statement, 2. Proposed Architecture, 3. Benefits & Performance, Design Spec: Dynamic Container Workspace Switching for Worktree Isolation, Dynamic `/app` Symlink via `/workspace_root` Mount

### Community 57 - "McpProcessError"
Cohesion: 0.20
Nodes (14): Exception, McpError, McpProcessError, McpRpcError, McpTimeoutError, Superstate MCP stdio JSON-RPC Client. This module implements a robust stdio…, Read a single line from stdout with a timeout deadline. Parameters: deadline:…, Base exception for all MCP client errors. (+6 more)

### Community 58 - "Concurrent Verifier Seal Resolution & 4-Worker Concurrency Plan"
Cohesion: 0.29
Nodes (6): Concurrent Verifier Seal Resolution & 4-Worker Concurrency Plan, Task 1: TaskSpec `has_verifier_dockerfile` Seal Resilience & Test, Task 2: Concurrency 4 Configuration, Task 3: Full Verification Suite, Task 4: Commit & Merge, Task 5: Launch Benchmark Suite at Concurrency 4

### Community 59 - "Global Constraints"
Cohesion: 0.29
Nodes (6): Agent-Driven Worktrees & Full-Context Turnkey Execution Implementation Plan, Global Constraints, Task 1: Model & Prompt Context Fidelity (`superstate-core`), Task 2: In-Place Default & Agent Worktree CLI (`superstate-cli`), Task 3: Universal Zero-Turn Planning in Adapter (`superstate-eval`), Task 4: Targeted Benchmark Verification on Target Subset

### Community 60 - "Superstate Massive Adoption & Founder Prestige Roadmap"
Cohesion: 0.13
Nodes (14): 1. Executive Summary & Core Mission, 2. Core Positioning & Intellectual Anchors, 3. Four-Phase Execution Roadmap, 4. Key Metrics & Success Criteria, 5. Spec Self-Review Checklist, Phase 1: Packaging & Developer Ergonomics (Week 1), Phase 2: The Technical Manifesto & Empirical Paper (Week 2), Phase 3: The Viral Launch Campaign (Week 3) (+6 more)

### Community 61 - "3. Detailed Component Design"
Cohesion: 0.14
Nodes (13): 1. Executive Summary & Objective, 2. Architecture & Components, 3.1 `SuperstateMcpClient` (`lab/engine/mcp/client.py`), 3.2 Harness-Level Adapter: `SuperstateMcpAdapter` (`lab/engine/adapters/superstate_mcp.py`), 3.3 Agent-Level Autonomous Adapter: `SuperstateAgentMcpAdapter` (`lab/engine/adapters/superstate_agent_mcp.py`), 3.4 Driver Integration (`lab/engine/drivers/claude_cli.py`), 3.5 Runner Arms Configuration (`lab/engine/runner.py`), 3. Detailed Component Design (+5 more)

### Community 63 - "Any"
Cohesion: 0.18
Nodes (6): Any, Initialize the MCP client configuration. Parameters: superstate_bin: Path to…, Return cached map of discovered tools keyed by name., Return server identification info received during protocol handshake., Send a JSON-RPC request and wait for the corresponding response. Parameters:…, Read lines from stdout until receiving the matching JSON-RPC response. Filters…

### Community 64 - "Frontier Triad Benchmark: Final Evaluation Report"
Cohesion: 0.20
Nodes (9): 1. Executive Summary, 2. Comparative Scorecard & Economics, 3. Granular Test Breakdown: Moving Past Binary Metrics, 4. Full Per-Task Results (All 30 Tasks), 5. Architectural Findings, Frontier Triad Benchmark: Final Evaluation Report, Standard Benchmark Metrics, SWE-Bench Test Completion Comparison (+1 more)

### Community 65 - "VanillaAdapter"
Cohesion: 0.27
Nodes (6): Path, Unguided baseline adapter enforcing complete isolation from rules or skills., Sanitize workspace by removing all guidance, rule files, and skills., Ensure pristine unguided workspace before execution., VanillaAdapter, test_production_turn_caps_do_not_bind_on_ordinary_runs()

### Community 66 - "._perform_handshake"
Cohesion: 0.22
Nodes (5): Start the MCP server when entering the context block., Generate a monotonically increasing request ID., Spawn the superstate mcp process and execute protocol handshake. Raises:…, Execute standard MCP initialization handshake and populate tool cache., Send a JSON-RPC notification message without awaiting reply.

### Community 67 - "Global Constraints"
Cohesion: 0.22
Nodes (8): Global Constraints, Superstate Massive Adoption & Founder Prestige Implementation Plan, Task 1: Prebuilt Multi-Platform Binary Releases & Homebrew Tap Setup, Task 2: Interactive `superstate init` Repository Wizard, Task 3: MCP Registry & Smithery Integration Metadata, Task 4: Empirical Technical Whitepaper & Academic Preprint, Task 5: Launch Campaign Package (Show HN, Viral X Thread, Video Script), Task 6: Turnkey GitHub Action (`superstate/action@v1`)

### Community 68 - "FakePipe"
Cohesion: 0.22
Nodes (3): FakePipe, Any, Mock file-like pipe supporting write and readline.

### Community 69 - "Global Constraints"
Cohesion: 0.29
Nodes (6): Global Constraints, MCP Evaluation Dual Architecture Implementation Plan, Task 1: `SuperstateMcpClient` Implementation & Protocol Handshake, Task 2: Harness-Level Adapter (`SuperstateMcpAdapter`), Task 3: Driver MCP Support & Agent-Level Autonomous Adapter, Task 4: Runner Integration & Benchmark Parity Verification

### Community 70 - ".__exit__"
Cohesion: 0.40
Nodes (3): BaseException, Terminate the server process cleanly upon exiting context., Cleanly terminate the superstate child process and close pipes.

### Community 71 - "find_superstate_binary"
Cohesion: 0.50
Nodes (3): find_superstate_binary(), Resolve the state-engine binary for a named implementation. Resolution is…, test_superstate_adapter_executes_in_worktree()

## Knowledge Gaps
- **133 isolated node(s):** `superstate-eval`, `launch_frontier_claude_haiku.sh script`, `launch_frontier_condition_b.sh script`, `launch_frontier_mcp_rerun.sh script`, `launch_frontier_triad_benchmark.sh script` (+128 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 606 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TaskSpec` connect `TaskSpec` to `AgentDriver`, `DriverTelemetry`, `AgyCliDriver`, `ClaudeCliDriver`, `test_ablation_runner.py`, `AnswerKeyGuard`, `task_loader.py`, `TurnBasedAdapter`, `extract_and_grade`, `BaseCliDriver`, `SuperstateMcpAdapter`, `test_runner.py`, `InContainerClaudeDriver`, `SuperstateAgentMcpAdapter`, `load_task_from_dir`, `test_state_engine_loop.py`, `.execute`, `test_superstate_resilience.py`, `SuperstateAdapter`, `claude_cli.py`?**
  _High betweenness centrality (0.139) - this node is a cross-community bridge._
- **Why does `SuperstateMcpClient` connect `SuperstateMcpClient` to `SuperstateAgentMcpAdapter`, `._perform_handshake`, `.__exit__`, `test_superstate_mcp_client.py`, `task_loader.py`, `SuperstateMcpAdapter`, `McpProcessError`, `Any`?**
  _High betweenness centrality (0.094) - this node is a cross-community bridge._
- **Why does `DockerManager` connect `DockerManager` to `AgentDriver`, `verifier.py`, `task_loader.py`, `test_docker_integration.py`, `ImageBuildError`, `.check_disk_space_or_prune`, `HeldOutVerifier`?**
  _High betweenness centrality (0.077) - this node is a cross-community bridge._
- **Are the 24 inferred relationships involving `TaskSpec` (e.g. with `AnswerKeyGuard` and `AgentAdapter`) actually correct?**
  _`TaskSpec` has 24 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `DriverTelemetry` (e.g. with `AgyCliDriver` and `BaseCliDriver`) actually correct?**
  _`DriverTelemetry` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `SuperstateAdapter` (e.g. with `TaskSpec` and `AgentDriver`) actually correct?**
  _`SuperstateAdapter` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `AgentDriver` (e.g. with `TaskSpec` and `SuperstateAgentMcpAdapter`) actually correct?**
  _`AgentDriver` has 9 INFERRED edges - model-reasoned connections that need verification._