# Graph Report - feat-handoff-daemon-benchmark  (2026-09-14)

## Corpus Check
- 138 files · ~137,398 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 15 file(s) not represented in the graph (top: .log 8, (none) 6, .lock 1)

## Summary
- 1406 nodes · 3077 edges · 89 communities (73 shown, 12 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 173 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e3e672b7`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- TaskSpec
- DriverTelemetry
- AgyCliDriver
- ClaudeCliDriver
- SuperstateMcpClient
- extract_and_grade
- .execute
- test_superstate_mcp_client.py
- SuperstateAgentMcpAdapter
- test_superstate_agent_mcp.py
- handle
- BudgetPolicy
- ConcurrencyGovernor
- test_superstate_mcp_adapter.py
- resolve_next_turn_prompt
- .execute
- base.py
- DockerManager
- task_loader.py
- InContainerClaudeDriver
- AblationRunner
- test_docker_integration.py
- McpProcessError
- AgentDriver
- .run_task
- SuperstateMcpAdapter
- RunRecorder
- verifier.py
- test_ablation_runner.py
- test_answer_key.py
- test_differential.py
- AnswerKeyGuard
- SuperstateAdapter
- BaseCliDriver
- reporter.py
- Design Specification: Agent-Driven Worktrees & Full-Context Turnkey Execution
- Control-Plane Evaluation — Plan
- Superstate Massive Adoption & Founder Prestige Roadmap
- SuperpowersAdapter
- 3. Detailed Component Design
- RunTelemetry
- Architecture Specification: Antigravity CLI Driver (`AgyCliDriver`) & Container Execution Bridge
- VanillaAdapter
- runner.py
- HeldOutVerifier
- AgentImageBuilder
- Frontier Triad Benchmark: Final Evaluation Report
- Superstate Resilience, Diagnostic Retry Loops, and Git Native State Tracking Design
- Design Specification: Cross-Agent Relay & Autonomous Detached Daemon Evaluation
- ._perform_handshake
- superstate-eval
- Global Constraints
- Architecture Specification: Concurrent Evaluation Isolation & Universal Progress-Earned Budgeting
- 2. Architectural Design
- FakePipe
- .check_disk_space_or_prune
- Proposed File Changes
- Global Constraints
- ImageBuildError
- test_agent_failure_is_diagnosed_before_the_grading_symptom
- FlakyGateDriver
- Concurrent Verifier Seal Resolution & 4-Worker Concurrency Plan
- Global Constraints
- Global Constraints
- Global Constraints
- MockDriver
- Global Constraints
- Global Constraints
- Design Spec: Dynamic Container Workspace Switching for Worktree Isolation
- Global Constraints
- Feature Implementation Plan
- superstate-eval Local Assessment Repository Implementation Plan
- is_transient_stream_interruption
- run_weekend_benchmark.sh
- test_superstate_adapter_gate_failure_stateless_retry
- benchmarks/__init__.py
- dag_plan.md
- launch_frontier_claude_haiku.sh
- launch_frontier_condition_b.sh
- launch_frontier_handoff_pilot.sh
- launch_frontier_mcp_rerun.sh
- launch_frontier_triad_benchmark.sh
- launch_weekend_run.sh
- .__init__
- superstate-eval

## God Nodes (most connected - your core abstractions)
1. `TaskSpec` - 107 edges
2. `DriverTelemetry` - 83 edges
3. `SuperstateAdapter` - 78 edges
4. `AgentDriver` - 55 edges
5. `SuperstateMcpClient` - 52 edges
6. `AblationRunner` - 45 edges
7. `SuperstateMcpAdapter` - 43 edges
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
- `MockDriver` --uses--> `TaskSpec`  [INFERRED]
  tests/test_superstate_agent_mcp.py → lab/benchmarks/task_loader.py
- `MockDriver` --uses--> `TaskSpec`  [INFERRED]
  tests/test_superstate_mcp_adapter.py → lab/benchmarks/task_loader.py

## Import Cycles
- None detected.

## Communities (89 total, 12 thin omitted)

### Community 0 - "TaskSpec"
Cohesion: 0.05
Nodes (47): Specification of an evaluation benchmark task., TaskSpec, is_pid_alive(), Any, BudgetHook, Path, Superstate daemon adapter for autonomous headless execution., Hook for executing verification gate commands; mockable in tests. (+39 more)

### Community 1 - "DriverTelemetry"
Cohesion: 0.11
Nodes (47): DriverTelemetry, Outcome and telemetry metrics from a single driver invocation turn., find_superstate_binary(), Resolve the state-engine binary for a named implementation. Resolution is…, _make_dummy_task(), MockDriver, Any, parametrize (+39 more)

### Community 2 - "AgyCliDriver"
Cohesion: 0.10
Nodes (39): Name of the evaluation arm., AgyCliDriver, AgyCliDriverError, base_model_name(), estimate_cost_usd(), Any, Path, RuntimeError (+31 more)

### Community 3 - "ClaudeCliDriver"
Cohesion: 0.11
Nodes (39): ClaudeCliDriver, ClaudeCliDriverError, estimate_cost_usd(), find_superstate_binary(), _first(), Any, Path, RuntimeError (+31 more)

### Community 4 - "SuperstateMcpClient"
Cohesion: 0.09
Nodes (25): BaseException, Any, Path, Client for communicating with the superstate MCP server over stdio JSON-RPC.…, Initialize the MCP client configuration. Parameters: superstate_bin: Path to…, Return True if the underlying server process is active and alive., Return cached map of discovered tools keyed by name., Return server identification info received during protocol handshake. (+17 more)

### Community 5 - "extract_and_grade"
Cohesion: 0.10
Nodes (35): Directory holding the held-out verifier (Dockerfile, test.sh, grader.py)., compute_test_metrics(), extract_and_grade(), _extract_blind_patch(), _inject_tests_to_container(), Any, Path, Extract patch by committing workspace changes and running task collection… (+27 more)

### Community 6 - ".execute"
Cohesion: 0.09
Nodes (20): Any, BudgetHook, Path, Resolve active worktree path from state.json if provisioned., Report which state engine actually drove this run., Record the engine used, downgrading to the fallback if it is ever hit., Keep harness files from dirtying the tree the git-clean gate inspects. The…, Sanitize workspace so Arm C sees the same blank slate as the control arm. (+12 more)

### Community 7 - "test_superstate_mcp_client.py"
Cohesion: 0.09
Nodes (26): FakeMcpServerProcess, MonkeyPatch, Path, Tests for SuperstateMcpClient. Verifies stdio JSON-RPC MCP protocol handshake,…, Verify initialize, initialized notification, tools/list, and caching 25 tools., Verify call_tool parses text and nested json in result.content., Verify call_tool raises McpRpcError on JSON-RPC error payload., Verify context manager automatically starts and terminates child process. (+18 more)

### Community 8 - "SuperstateAgentMcpAdapter"
Cohesion: 0.09
Nodes (23): Remove guidance files the task repo ships. Returns what was removed., Outcome and telemetry metrics for a complete task execution run., strip_preexisting_guidance(), TaskRunResult, Any, BudgetHook, Path, Agent-level autonomous adapter for Superstate over Model Context Protocol… (+15 more)

### Community 9 - "test_superstate_agent_mcp.py"
Cohesion: 0.12
Nodes (27): _init_git_repo(), _make_dummy_task(), MockDriver, Any, MonkeyPatch, Path, Tests for SuperstateAgentMcpAdapter. Tests the agent-level autonomous MCP…, Verify setup_workspace strips legacy files and excludes harness artifacts. (+19 more)

### Community 10 - "handle"
Cohesion: 0.13
Nodes (25): ContainerExec, _error(), handle(), log(), main(), Any, A minimal stdio MCP server exposing exactly one tool: exec in ONE container.…, Handle one JSON-RPC message. Returns a response, or None for notifications. (+17 more)

### Community 11 - "BudgetPolicy"
Cohesion: 0.11
Nodes (20): BudgetPolicy, Progress-earned budget policy and execution telemetry accounting. Allows…, Manages progress-earned execution timeouts., Record completed milestone and grant progress lease extension if within max…, ProgressTracker, Path, Universal progress tracker for granting runtime lease extensions across…, Monitors workspace state and awards progress-earned lease extensions to any arm. (+12 more)

### Community 12 - "ConcurrencyGovernor"
Cohesion: 0.12
Nodes (23): ConcurrencyGovernor, Path, Machine-aware dynamic concurrency governor for isolated evaluation execution., Block until an execution slot is available under live resource constraints., Release an active execution slot and notify waiting tasks., Context manager acquiring a dynamic concurrency slot., Hardware capacity snapshot used to determine safe concurrency bounds., Governs evaluation concurrency dynamically based on host machine resources. (+15 more)

### Community 13 - "test_superstate_mcp_adapter.py"
Cohesion: 0.14
Nodes (25): _init_git_repo(), _make_dummy_task(), MockDriver, MonkeyPatch, Path, Tests for SuperstateMcpAdapter. Tests the harness-level MCP adapter for state…, Verify setup_workspace strips legacy files and excludes harness artifacts., Execute a single-milestone task with zero-turn planning using real superstate. (+17 more)

### Community 14 - "resolve_next_turn_prompt"
Cohesion: 0.10
Nodes (21): Any, BudgetHook, Path, Run an agent session or turn within the target workspace., Execute a task in the given workspace using the provided driver., Configure or sanitize workspace prior to agent invocation., Provide initial instruction prompt for the task., Report arm-specific facts about how this run was actually configured. (+13 more)

### Community 15 - ".execute"
Cohesion: 0.12
Nodes (19): _extract_plan_milestones(), flush(), Any, BudgetHook, Path, Resolve active worktree path from state.json if provisioned., Execute a milestone verification command on the host or inside a container., Dynamically repoint /app inside container to the active worktree or… (+11 more)

### Community 16 - "base.py"
Cohesion: 0.13
Nodes (16): AgentAdapter, Base interfaces and data structures for execution adapters and agent drivers., Abstract evaluation adapter configuring workspace guidance and managing turns., Base template adapter managing bounded turn execution and mechanical approval., TurnBasedAdapter, Arm adapters for Vanilla, Superpowers, and Superstate execution., Arm B: Superpowers Adapter. Installs standard AGENTS.md rules and vendored…, Arm C: Superstate (Deterministic State Engine) Adapter. Executes milestone DAGs… (+8 more)

### Community 17 - "DockerManager"
Cohesion: 0.12
Nodes (18): DockerClient, DiskSpaceError, DockerManager, RuntimeError, Docker lifecycle and host disk space management. Ensures deterministic…, Raised when host disk space falls below the critical emergency threshold., Prune dangling images, stopped containers, and unreferenced volumes., Manages Docker containers and host disk resource reclamation. (+10 more)

### Community 18 - "task_loader.py"
Cohesion: 0.14
Nodes (19): _extract_collect_commands(), load_benchmark_tasks(), load_task_from_dir(), Any, Path, Benchmark task specification and loader module. Parses SWE-bench / Harbor style…, Ingest collector command sequences used to extract test or run artifacts., Parse task.toml and instruction.md from task_dir into a TaskSpec. (+11 more)

### Community 19 - "InContainerClaudeDriver"
Cohesion: 0.16
Nodes (21): _first(), InContainerClaudeDriver, InContainerDriverError, Any, Path, RuntimeError, Raised when the in-container agent cannot be invoked., Build the shell line executed inside the container. The prompt is base64'd so… (+13 more)

### Community 20 - "AblationRunner"
Cohesion: 0.19
Nodes (23): EvaluationResult, Outcome of blind verification and patch extraction., AblationRunner, Executes benchmark tasks across evaluation arms with resource and lease…, parametrize, Path, Tests for AblationRunner telemetry and metrics integration. Validates that…, Verify fallback to 1.0 pass fraction when verifier stats are None and task… (+15 more)

### Community 21 - "test_docker_integration.py"
Cohesion: 0.16
Nodes (19): Raised when the task repository cannot be materialized onto the host., WorkspaceSeedError, requires_docker, fixture, Path, Integration tests exercising a real Docker daemon. The unit suite mocks…, End-to-end: build the verifier image and have it write reward.json. Mirrors the…, reward.txt == -1 is an infrastructure failure, not a legitimate 0. (+11 more)

### Community 22 - "McpProcessError"
Cohesion: 0.16
Nodes (16): Exception, McpError, McpProcessError, McpRpcError, McpTimeoutError, Superstate MCP stdio JSON-RPC Client. This module implements a robust stdio…, Send a JSON-RPC request and wait for the corresponding response. Parameters:…, Read a single line from stdout with a timeout deadline. Parameters: deadline:… (+8 more)

### Community 23 - "AgentDriver"
Cohesion: 0.11
Nodes (16): AgentDriver, Abstract driver interface communicating with an underlying agent runtime.…, estimate_cost_usd(), Shared plumbing for agent drivers that shell out to a CLI. Subclasses supply…, Cost from explicit rates. Returns 0.0 when rates are unknown. Deliberately…, An AgentDriver that runs the agent CLI inside the task sandbox. This is the…, Path, test_ablation_runner_default_execution_mounts_workspace_into_container() (+8 more)

### Community 24 - ".run_task"
Cohesion: 0.12
Nodes (14): Model the harness was configured with, when the driver knows it., Isolated only with container_exec on: that is what removes host Bash., InsufficientResourcesError, NoDriverConfiguredError, Any, RuntimeError, Execute a single task under the specified arm and budget policy. Guarantees: 1.…, Resolve a cohort entry into (task_id, image, base_budget_sec, task_spec). (+6 more)

### Community 25 - "SuperstateMcpAdapter"
Cohesion: 0.11
Nodes (14): Keep harness files from dirtying the tree that git verification gates inspect., Sanitize workspace by stripping legacy guidance and excluding harness artifacts., Strip a host-side bridge wrapper when the gate already runs in the sandbox., Extract a clean, concise finding from the turn response to keep prompt bounded., Adapter executing tasks under the deterministic Superstate engine via stdio MCP., Initialize the Superstate MCP adapter configuration., Name of the evaluation arm., SuperstateMcpAdapter (+6 more)

### Community 26 - "RunRecorder"
Cohesion: 0.14
Nodes (13): _clip(), Any, Path, Run trace capture: the diagnostic record an evaluation leaves behind. Pass/fail…, Capture one driver turn, including the prompt that produced it., Capture a milestone attempt and its gate verdict., Persist the full held-out verifier output, untruncated., Write the headline run record. Returns the path written, if any. (+5 more)

### Community 27 - "verifier.py"
Cohesion: 0.15
Nodes (14): Any, Path, Held-out verification in a separate container. The benchmark's own contract…, Build the verifier image for `task` and return its tag., Run the held-out verifier against the collected patch. `logs_dir` must already…, Delete the verifier image so the hidden tests do not linger on the host., Run the built verifier image against the collected patch., Result of running the held-out verifier. (+6 more)

### Community 28 - "test_ablation_runner.py"
Cohesion: 0.15
Nodes (16): compute_control_plane_lift(), _harness_of(), Measure what each layer adds to a given harness, task by task. This evaluation…, _fake_sandbox_factory(), _paired(), Tests for Ablation Runner and Reporter., Build a run_sandbox stand-in that writes a passing verifier artifact., A cohort of 8 GB tasks must not be dispatched at the 4 GB default width. (+8 more)

### Community 29 - "test_answer_key.py"
Cohesion: 0.26
Nodes (18): is_readable(), Whether the current process can list `path`. Used by tests and diagnostics., _guard(), fixture, Path, The held-out tests must be unreadable while a host-side agent is working., A cohort runs many tasks at once and they share the task directory. Live…, test_a_hard_kill_is_healed_by_the_next_run() (+10 more)

### Community 30 - "test_differential.py"
Cohesion: 0.19
Nodes (17): check_binaries(), normalize_state(), fixture, Path, Differential parity testing between superstate (Rust) and agent-rules (Python).…, Resolve a binary from env, then PATH (only if a name is given), then fallbacks.…, Both engines must parse a DAG plan and traverse every task identically., Recording an epistemic note must produce identical state on both engines. (+9 more)

### Community 31 - "AnswerKeyGuard"
Cohesion: 0.18
Nodes (9): Whether the task has a Dockerfile in its tests/ directory., AnswerKeyGuard, Path, Make `paths` unreadable for the duration of the block. Nests safely: concurrent…, Copy a directory somewhere readable before it is sealed. The verifier is built…, Seals and restores held-out test directories with thread-safe reference…, A readable copy of a sealed directory, for grading. The verifier is built from…, Yield a readable view of `path`, for grading. Deliberately does not unseal the… (+1 more)

### Community 32 - "SuperstateAdapter"
Cohesion: 0.19
Nodes (14): Adapter executing tasks under the deterministic Superstate engine., Extract a clean, concise finding from the turn's response to keep prompts…, SuperstateAdapter, Path, test_switch_container_workspace_handles_exec_nonzero_exit(), test_switch_container_workspace_handles_none_container(), test_switch_container_workspace_no_worktree_mode(), test_switch_container_workspace_resets_to_root() (+6 more)

### Community 33 - "BaseCliDriver"
Cohesion: 0.16
Nodes (13): BaseCliDriver, CliDriverError, first(), Any, Path, RuntimeError, Turn the CLI's JSON result into telemetry., Raised when the agent CLI cannot be located or invoked. (+5 more)

### Community 34 - "reporter.py"
Cohesion: 0.24
Nodes (14): generate_comparison_summary(), Any, Evaluation reporter generating cost-efficiency frontier comparisons., Group run telemetry by paradigm arm and calculate core efficiency metrics., Render control-plane lift, with the caveat that small n cannot support it., Render summary as a formatted text table for reports., Render Total Cost of Ownership (TCO) incorporating human remediation penalties., render_economic_tco_table() (+6 more)

### Community 35 - "Design Specification: Agent-Driven Worktrees & Full-Context Turnkey Execution"
Cohesion: 0.12
Nodes (15): 1.1 `ExecutionState` Model (`crates/superstate-core/src/models.rs`), 1.2 Full-Context Turnkey Prompt (`crates/superstate-core/src/prompt.rs`), 1. Problem Statement & Motivation, 2.1 Default In-Place Execution in `state init`, 2.2 Dedicated Agent Worktree Commands, 2. Core Architectural Principles, 3.1 Universal Zero-Turn Direct Initialization, 3.2 Dynamic Turn & Milestone Execution (+7 more)

### Community 36 - "Control-Plane Evaluation — Plan"
Cohesion: 0.13
Nodes (14): Control-Plane Evaluation — Plan, Harness defects found by running (all fixed), Parked, with reasons, Standing lesson from today, Stream 1 — Produce a credible measurement, Stream 2 — Rust parity — COMPLETE (2026-09-09), Task 1: Pin the engine explicitly and record it — DONE, Task 2: Drive the real state-engine loop — DONE (+6 more)

### Community 37 - "Superstate Massive Adoption & Founder Prestige Roadmap"
Cohesion: 0.13
Nodes (14): 1. Executive Summary & Core Mission, 2. Core Positioning & Intellectual Anchors, 3. Four-Phase Execution Roadmap, 4. Key Metrics & Success Criteria, 5. Spec Self-Review Checklist, Phase 1: Packaging & Developer Ergonomics (Week 1), Phase 2: The Technical Manifesto & Empirical Paper (Week 2), Phase 3: The Viral Launch Campaign (Week 3) (+6 more)

### Community 38 - "SuperpowersAdapter"
Cohesion: 0.16
Nodes (9): Any, Path, Adapter configuring markdown rules and vendored superpowers skills., Install markdown guidance and copy superpowers skills into workspace., Configure workspace with Superpowers guidance before execution begins., Record whether the vendored skills library was actually installed., SuperpowersAdapter, test_production_turn_caps_do_not_bind_on_ordinary_runs() (+1 more)

### Community 39 - "3. Detailed Component Design"
Cohesion: 0.14
Nodes (13): 1. Executive Summary & Objective, 2. Architecture & Components, 3.1 `SuperstateMcpClient` (`lab/engine/mcp/client.py`), 3.2 Harness-Level Adapter: `SuperstateMcpAdapter` (`lab/engine/adapters/superstate_mcp.py`), 3.3 Agent-Level Autonomous Adapter: `SuperstateAgentMcpAdapter` (`lab/engine/adapters/superstate_agent_mcp.py`), 3.4 Driver Integration (`lab/engine/drivers/claude_cli.py`), 3.5 Runner Arms Configuration (`lab/engine/runner.py`), 3. Detailed Component Design (+5 more)

### Community 40 - "RunTelemetry"
Cohesion: 0.19
Nodes (12): Any, Auditable execution telemetry across an evaluation unit., RunTelemetry, _failure_signature(), Collapse a failure reason to a comparable class, stripping run-specific detail., Cluster failures per arm so recurring defects are visible. A pass rate says an…, Render clustered failures as text, most frequent first., render_failure_report() (+4 more)

### Community 41 - "Architecture Specification: Antigravity CLI Driver (`AgyCliDriver`) & Container Execution Bridge"
Cohesion: 0.17
Nodes (11): 1. Executive Summary & Context, 2. Core Objectives, 3.1 Class Definition (`lab/engine/drivers/agy_cli.py`), 3.2 CLI Binary Resolution, 3.3 Command Construction, 3.4 Telemetry & Pricing, 3. Architecture & Driver Implementation, 4. Container Execution Bridge (`./run-in-container`) (+3 more)

### Community 42 - "VanillaAdapter"
Cohesion: 0.21
Nodes (8): Path, Unguided baseline adapter enforcing complete isolation from rules or skills., Sanitize workspace by removing all guidance, rule files, and skills., Ensure pristine unguided workspace before execution., VanillaAdapter, test_adapter_passes_container_handle_to_driver(), test_turn_loop_breaker_reports_failure(), test_vanilla_adapter_cleans_workspace_and_executes()

### Community 43 - "runner.py"
Cohesion: 0.18
Nodes (7): Blind patch extraction and held-out verifier scoring. Executes uniformly across…, Ablation and efficacy benchmark runner. Executes evaluation arms (Vanilla,…, Keep the held-out tests unreadable while the agent is working. A host-side…, Tests for Concurrent Execution Runner with Dynamic Concurrency Governor., test_ablation_runner_universal_lease_extension(), fake_executor(), test_run_cohort_concurrency_governor_dispatch()

### Community 44 - "HeldOutVerifier"
Cohesion: 0.42
Nodes (10): HeldOutVerifier, Builds and runs the task's own verifier image., _manager(), Path, The verifier image is the held-out answer key; it must not linger on the host., _Task, test_keep_image_is_opt_in_for_debugging(), test_verifier_image_is_removed_after_grading() (+2 more)

### Community 45 - "AgentImageBuilder"
Cohesion: 0.21
Nodes (7): AgentImageBuilder, Builds the image the agent actually runs inside. The agent must not run on the…, Docker tags allow a restricted character set; image refs do not., Builds and caches per-task agent images., A deterministic tag: this image holds no secrets, so caching is safe. Unlike…, Build (or reuse) an image with the Claude Code CLI on top of `base_image`., _slug()

### Community 46 - "Frontier Triad Benchmark: Final Evaluation Report"
Cohesion: 0.20
Nodes (9): 1. Executive Summary, 2. Comparative Scorecard & Economics, 3. Granular Test Breakdown: Moving Past Binary Metrics, 4. Full Per-Task Results (All 30 Tasks), 5. Architectural Findings, Frontier Triad Benchmark: Final Evaluation Report, Standard Benchmark Metrics, SWE-Bench Test Completion Comparison (+1 more)

### Community 47 - "Superstate Resilience, Diagnostic Retry Loops, and Git Native State Tracking Design"
Cohesion: 0.20
Nodes (9): 1. Context & Motivation, 2. Goals & Non-Goals, 3.1 Diagnostic Retry Loop in `lab/engine/adapters/superstate.py`, 3.2 Greenfield Git Resilience, 3. Architecture & Mechanics, 4. Verification & Testing, Goals, Non-Goals (+1 more)

### Community 48 - "Design Specification: Cross-Agent Relay & Autonomous Detached Daemon Evaluation"
Cohesion: 0.20
Nodes (9): 1. Overview & Objective, 2. Benchmark Task Suite: 5-Task Representative Pilot, 3.1 `SuperstateRelayAdapter` (`lab/engine/adapters/superstate_relay.py`), 3.2 `SuperstateDaemonAdapter` (`lab/engine/adapters/superstate_daemon.py`), 3. Architecture & Adapter Specifications, 4. Quantitative Metrics & Reporting, 5. Security & Isolation Invariants, Design Specification: Cross-Agent Relay & Autonomous Detached Daemon Evaluation (+1 more)

### Community 49 - "._perform_handshake"
Cohesion: 0.22
Nodes (5): Start the MCP server when entering the context block., Generate a monotonically increasing request ID., Spawn the superstate mcp process and execute protocol handshake. Raises:…, Execute standard MCP initialization handshake and populate tool cache., Send a JSON-RPC notification message without awaiting reply.

### Community 50 - "superstate-eval"
Cohesion: 0.20
Nodes (9): A note on what this harness has taught us, Differential parity, How a run works, Layout, Quick start, superstate-eval, Tasks, What is measured (+1 more)

### Community 51 - "Global Constraints"
Cohesion: 0.22
Nodes (8): Global Constraints, Superstate Massive Adoption & Founder Prestige Implementation Plan, Task 1: Prebuilt Multi-Platform Binary Releases & Homebrew Tap Setup, Task 2: Interactive `superstate init` Repository Wizard, Task 3: MCP Registry & Smithery Integration Metadata, Task 4: Empirical Technical Whitepaper & Academic Preprint, Task 5: Launch Campaign Package (Show HN, Viral X Thread, Video Script), Task 6: Turnkey GitHub Action (`superstate/action@v1`)

### Community 52 - "Architecture Specification: Concurrent Evaluation Isolation & Universal Progress-Earned Budgeting"
Cohesion: 0.22
Nodes (8): 1. Executive Summary & Goals, 2. Dynamic Concurrency Governor, 3. Strict Docker Sandbox Quotas & Volume Isolation, 4. Universal Progress-Earned Budget Policy, 5. Blind Extraction and Grading Pipeline, 6. Verification and Efficacy Frontiers, Architecture Specification: Concurrent Evaluation Isolation & Universal Progress-Earned Budgeting, Core Objectives

### Community 53 - "2. Architectural Design"
Cohesion: 0.22
Nodes (8): 1. Context & Motivation, 2.1 EvaluationResult Dataclass Extension, 2.2 Metric Extraction Helper, 2.3 AblationRunner Telemetry Integration, 2.4 CLI Output Formatting, 2. Architectural Design, 3. Testing & Verification, Design Specification: Test Pass Fraction & Test Statistics Propagation

### Community 54 - "FakePipe"
Cohesion: 0.22
Nodes (3): FakePipe, Any, Mock file-like pipe supporting write and readline.

### Community 55 - ".check_disk_space_or_prune"
Cohesion: 0.25
Nodes (5): Container, Path, Copy the task repository out of `image` into the host directory `dest`. A bind…, Check available disk space. Prune docker if below min_free_gb; raise if below…, Run a container with guaranteed teardown upon context exit. Guarantees that the…

### Community 56 - "Proposed File Changes"
Cohesion: 0.25
Nodes (7): Concurrent Evaluation Isolation & Universal Progress Budgeting Implementation Plan, Proposed File Changes, Task 1: Dynamic Machine-Aware Concurrency Governor, Task 2: Container Resource Constraints & Volume Isolation, Task 3: Universal Progress-Earned Budget Tracker, Task 4: Blind Extraction & Verification Pipeline, Task 5: End-to-End Concurrent Runner & Integration

### Community 57 - "Global Constraints"
Cohesion: 0.25
Nodes (7): Global Constraints, Superstate Resilience and Diagnostic Retry Loop Implementation Plan, Task 1: Implement Greenfield Git Handling in `lab/engine/adapters/superstate.py`, Task 2: Implement Milestone Diagnostic Retry Loop in `lab/engine/adapters/superstate.py`, Task 3: Unit Tests for Retry Loop & Greenfield Handling, Task 4: Native Git Initialization in Rust `superstate`, Task 5: Verification & Checkpoint

### Community 58 - "ImageBuildError"
Cohesion: 0.29
Nodes (5): ImageBuildError, Build an image from `context_dir` and return its tag. Used for the held-out…, Build an image from an inline Dockerfile with no build context., Stop docker-py invoking every configured credential helper on build. docker-py…, Raised when an image (typically the held-out verifier) cannot be built.

### Community 59 - "test_agent_failure_is_diagnosed_before_the_grading_symptom"
Cohesion: 0.25
Nodes (7): A result from a driver with a host shell carries a weaker guarantee. It must…, An agent that times out leaves a bad patch; the timeout is the cause. Reporting…, test_agent_failure_is_diagnosed_before_the_grading_symptom(), run(), test_run_telemetry_records_whether_execution_was_isolated(), fake_sandbox(), run()

### Community 60 - "FlakyGateDriver"
Cohesion: 0.29
Nodes (6): FlakyGateDriver, Path, Verify that a greenfield workspace without .git does not crash when advancing…, Fails on turn 1 by not creating marker.txt, then creates it on turn 2 after…, test_greenfield_workspace_advances_without_git(), test_milestone_retry_loop_on_failed_gate()

### Community 61 - "Concurrent Verifier Seal Resolution & 4-Worker Concurrency Plan"
Cohesion: 0.29
Nodes (6): Concurrent Verifier Seal Resolution & 4-Worker Concurrency Plan, Task 1: TaskSpec `has_verifier_dockerfile` Seal Resilience & Test, Task 2: Concurrency 4 Configuration, Task 3: Full Verification Suite, Task 4: Commit & Merge, Task 5: Launch Benchmark Suite at Concurrency 4

### Community 62 - "Global Constraints"
Cohesion: 0.29
Nodes (6): Agent-Driven Worktrees & Full-Context Turnkey Execution Implementation Plan, Global Constraints, Task 1: Model & Prompt Context Fidelity (`superstate-core`), Task 2: In-Place Default & Agent Worktree CLI (`superstate-cli`), Task 3: Universal Zero-Turn Planning in Adapter (`superstate-eval`), Task 4: Targeted Benchmark Verification on Target Subset

### Community 63 - "Global Constraints"
Cohesion: 0.29
Nodes (6): Global Constraints, MCP Evaluation Dual Architecture Implementation Plan, Task 1: `SuperstateMcpClient` Implementation & Protocol Handshake, Task 2: Harness-Level Adapter (`SuperstateMcpAdapter`), Task 3: Driver MCP Support & Agent-Level Autonomous Adapter, Task 4: Runner Integration & Benchmark Parity Verification

### Community 64 - "Global Constraints"
Cohesion: 0.29
Nodes (6): Cross-Agent Relay & Autonomous Detached Daemon Evaluation Implementation Plan, Global Constraints, Task 1: Implement `SuperstateRelayAdapter`, Task 2: Implement `SuperstateDaemonAdapter`, Task 3: Wire Adapters into Runner and Add End-to-End Harness Tests, Task 4: Automated Pilot Script & 5-Task Benchmark Execution

### Community 65 - "MockDriver"
Cohesion: 0.33
Nodes (4): MockDriver, Any, Predictable mock driver recording calls and returning successful telemetry., Simulate agent execution by writing a stub solution file. Parameters: task:…

### Community 66 - "Global Constraints"
Cohesion: 0.33
Nodes (5): Antigravity CLI Driver (`AgyCliDriver`) Implementation Plan, Global Constraints, Task 1: Implement `AgyCliDriver` Core and Container Execution Bridge, Task 2: Verify Baseline and System Integration, Task 3: Execute Live Single-Task Smoke Run

### Community 67 - "Global Constraints"
Cohesion: 0.33
Nodes (5): Dynamic Container Workspace Switching Implementation Plan, Global Constraints, Task 1: Runner Mount Decoupling & Container Symlink Setup, Task 2: Worktree Turn Repointing in Superstate Adapter, Task 3: Live Verification on `db-wal-recovery`

### Community 68 - "Design Spec: Dynamic Container Workspace Switching for Worktree Isolation"
Cohesion: 0.33
Nodes (5): 1. Problem Statement, 2. Proposed Architecture, 3. Benefits & Performance, Design Spec: Dynamic Container Workspace Switching for Worktree Isolation, Dynamic `/app` Symlink via `/workspace_root` Mount

### Community 69 - "Global Constraints"
Cohesion: 0.40
Nodes (4): Global Constraints, Task 1: Extend EvaluationResult and Implement compute_test_metrics, Task 2: Integrate Test Metrics into Runner Telemetry and CLI Output, Test Pass Fraction & Test Statistics Implementation Plan

### Community 70 - "Feature Implementation Plan"
Cohesion: 0.40
Nodes (4): Feature Implementation Plan, Task 1: Setup database schema, Task 2: Implement repository methods, Task 3: Expose REST endpoint

### Community 71 - "superstate-eval Local Assessment Repository Implementation Plan"
Cohesion: 0.50
Nodes (3): superstate-eval Local Assessment Repository Implementation Plan, Tasks, Verification & Completion Gates

### Community 72 - "is_transient_stream_interruption"
Cohesion: 0.50
Nodes (4): is_transient_stream_interruption(), Classify whether an error string represents a transient API transport…, Verify is_transient_stream_interruption correctly classifies transport vs…, test_is_transient_stream_interruption_detection()

## Knowledge Gaps
- **144 isolated node(s):** `superstate-eval`, `launch_frontier_claude_haiku.sh script`, `launch_frontier_condition_b.sh script`, `launch_frontier_handoff_pilot.sh script`, `launch_frontier_mcp_rerun.sh script` (+139 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 632 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **12 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TaskSpec` connect `TaskSpec` to `DriverTelemetry`, `AgyCliDriver`, `ClaudeCliDriver`, `extract_and_grade`, `.execute`, `SuperstateAgentMcpAdapter`, `test_superstate_agent_mcp.py`, `test_superstate_mcp_adapter.py`, `resolve_next_turn_prompt`, `.execute`, `base.py`, `task_loader.py`, `InContainerClaudeDriver`, `AblationRunner`, `AgentDriver`, `.run_task`, `SuperstateMcpAdapter`, `test_ablation_runner.py`, `AnswerKeyGuard`, `SuperstateAdapter`, `BaseCliDriver`, `runner.py`, `test_agent_failure_is_diagnosed_before_the_grading_symptom`, `FlakyGateDriver`, `MockDriver`?**
  _High betweenness centrality (0.166) - this node is a cross-community bridge._
- **Why does `SuperstateMcpClient` connect `SuperstateMcpClient` to `test_superstate_mcp_client.py`, `SuperstateAgentMcpAdapter`, `test_superstate_agent_mcp.py`, `test_superstate_mcp_adapter.py`, `.execute`, `._perform_handshake`, `McpProcessError`, `SuperstateMcpAdapter`?**
  _High betweenness centrality (0.132) - this node is a cross-community bridge._
- **Why does `SuperstateMcpAdapter` connect `SuperstateMcpAdapter` to `TaskSpec`, `DriverTelemetry`, `SuperstateMcpClient`, `SuperpowersAdapter`, `SuperstateAgentMcpAdapter`, `runner.py`, `test_superstate_mcp_adapter.py`, `.execute`, `base.py`, `AblationRunner`, `AgentDriver`?**
  _High betweenness centrality (0.071) - this node is a cross-community bridge._
- **Are the 26 inferred relationships involving `TaskSpec` (e.g. with `AnswerKeyGuard` and `AgentAdapter`) actually correct?**
  _`TaskSpec` has 26 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `DriverTelemetry` (e.g. with `SuperstateRelayAdapter` and `AgyCliDriver`) actually correct?**
  _`DriverTelemetry` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `SuperstateAdapter` (e.g. with `TaskSpec` and `AgentDriver`) actually correct?**
  _`SuperstateAdapter` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `AgentDriver` (e.g. with `TaskSpec` and `SuperstateAgentMcpAdapter`) actually correct?**
  _`AgentDriver` has 10 INFERRED edges - model-reasoned connections that need verification._