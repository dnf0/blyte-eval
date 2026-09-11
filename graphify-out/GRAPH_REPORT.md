# Graph Report - superstate-eval  (2026-09-11)

## Corpus Check
- 79 files · ~46,346 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 910 nodes · 1995 edges · 53 communities (45 shown, 4 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 110 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e39f8cfe`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- AblationRunner
- SuperstateAdapter
- test_agy_cli_driver.py
- ClaudeCliDriver
- handle
- BudgetPolicy
- AnswerKeyGuard
- HeldOutVerifier
- AgentDriver
- TurnBasedAdapter
- extract_and_grade
- RunRecorder
- test_docker_integration.py
- BaseCliDriver
- PilotShowdownRunner
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
- RunTelemetry
- .run_task
- DockerManager
- TaskSpec
- test_ablation_runner.py
- Control-Plane Evaluation — Plan
- test_state_engine_loop.py
- SuperpowersAdapter
- resolve_next_turn_prompt
- AgentImageBuilder
- Superstate Resilience, Diagnostic Retry Loops, and Git Native State Tracking Design
- docker_manager.py
- .check_disk_space_or_prune
- Global Constraints
- .__init__
- FlakyGateDriver
- .build_image
- _extract_collect_commands
- estimate_cost_usd

## God Nodes (most connected - your core abstractions)
1. `TaskSpec` - 70 edges
2. `SuperstateAdapter` - 66 edges
3. `DriverTelemetry` - 57 edges
4. `AblationRunner` - 41 edges
5. `AgentDriver` - 40 edges
6. `DockerManager` - 38 edges
7. `MockDriver` - 31 edges
8. `_make_dummy_task()` - 27 edges
9. `extract_and_grade()` - 25 edges
10. `AgyCliDriver` - 24 edges

## Surprising Connections (you probably didn't know these)
- `MockDriver` --uses--> `TaskSpec`  [INFERRED]
  tests/test_adapters.py → lab/benchmarks/task_loader.py
- `StubDriver` --uses--> `TaskSpec`  [INFERRED]
  tests/test_runner.py → lab/benchmarks/task_loader.py
- `test_a_failing_gate_stops_the_run_and_is_reported()` --uses--> `TaskSpec`  [INFERRED]
  tests/test_state_engine_loop.py → lab/benchmarks/task_loader.py
- `test_both_engines_produce_the_same_arm_outcome()` --uses--> `TaskSpec`  [INFERRED]
  tests/test_state_engine_loop.py → lab/benchmarks/task_loader.py
- `test_every_milestone_executes_and_advances()` --uses--> `TaskSpec`  [INFERRED]
  tests/test_state_engine_loop.py → lab/benchmarks/task_loader.py

## Import Cycles
- None detected.

## Communities (53 total, 4 thin omitted)

### Community 0 - "AblationRunner"
Cohesion: 0.12
Nodes (17): AblationRunner, InsufficientResourcesError, Any, Resolve a cohort entry into (task_id, image, base_budget_sec, task_spec)., Execute a matrix of tasks x arms concurrently using the dynamic governor., Raised when the host cannot safely run even a single concurrent evaluation., Executes benchmark tasks across evaluation arms with resource and lease…, A cohort of 8 GB tasks must not be dispatched at the 4 GB default width. (+9 more)

### Community 1 - "SuperstateAdapter"
Cohesion: 0.05
Nodes (77): DriverTelemetry, Outcome and telemetry metrics from a single driver invocation turn., _extract_plan_milestones(), flush(), find_superstate_binary(), Milestone, Any, BudgetHook (+69 more)

### Community 2 - "test_agy_cli_driver.py"
Cohesion: 0.10
Nodes (38): Name of the evaluation arm., AgyCliDriver, AgyCliDriverError, base_model_name(), estimate_cost_usd(), Any, Path, RuntimeError (+30 more)

### Community 3 - "ClaudeCliDriver"
Cohesion: 0.14
Nodes (32): ClaudeCliDriver, ClaudeCliDriverError, estimate_cost_usd(), _first(), Any, Path, RuntimeError, Inline MCP config launching the container-exec server for THIS container. (+24 more)

### Community 4 - "handle"
Cohesion: 0.13
Nodes (25): ContainerExec, _error(), handle(), log(), main(), Any, A minimal stdio MCP server exposing exactly one tool: exec in ONE container.…, Handle one JSON-RPC message. Returns a response, or None for notifications. (+17 more)

### Community 5 - "BudgetPolicy"
Cohesion: 0.14
Nodes (16): BudgetPolicy, Progress-earned budget policy and execution telemetry accounting. Allows…, Manages progress-earned execution timeouts., Record completed milestone and grant progress lease extension if within max…, ProgressTracker, Universal progress tracker for granting runtime lease extensions across…, Monitors workspace state and awards progress-earned lease extensions to any arm., Tests for Progress-Earned Budget Policy and Telemetry Accounting. (+8 more)

### Community 6 - "AnswerKeyGuard"
Cohesion: 0.05
Nodes (54): ConcurrencyGovernor, Path, Machine-aware dynamic concurrency governor for isolated evaluation execution., Block until an execution slot is available under live resource constraints., Release an active execution slot and notify waiting tasks., Context manager acquiring a dynamic concurrency slot., Hardware capacity snapshot used to determine safe concurrency bounds., Governs evaluation concurrency dynamically based on host machine resources. (+46 more)

### Community 7 - "HeldOutVerifier"
Cohesion: 0.16
Nodes (20): HeldOutVerifier, Any, Path, Build the verifier image for `task` and return its tag., Run the held-out verifier against the collected patch. `logs_dir` must already…, Delete the verifier image so the hidden tests do not linger on the host., Run the built verifier image against the collected patch., Docker tags allow a restricted character set; task ids do not. (+12 more)

### Community 8 - "AgentDriver"
Cohesion: 0.12
Nodes (17): Benchmark task specification and loader module. Parses SWE-bench / Harbor style…, AgentDriver, Base interfaces and data structures for execution adapters and agent drivers., Abstract driver interface communicating with an underlying agent runtime.…, Arm adapters for Vanilla, Superpowers, and Superstate execution., Arm B: Superpowers Adapter. Installs standard AGENTS.md rules and vendored…, Arm C: Superstate (Deterministic State Engine) Adapter. Executes milestone DAGs…, Arm A: Vanilla (Control) Adapter. Runs unguided SWE-bench baseline execution… (+9 more)

### Community 9 - "TurnBasedAdapter"
Cohesion: 0.16
Nodes (13): Any, BudgetHook, Path, Run an agent session or turn within the target workspace., Execute a task in the given workspace using the provided driver., Base template adapter managing bounded turn execution and mechanical approval., Configure or sanitize workspace prior to agent invocation., Provide initial instruction prompt for the task. (+5 more)

### Community 10 - "extract_and_grade"
Cohesion: 0.09
Nodes (38): Whether the task has a Dockerfile in its tests/ directory., compute_test_metrics(), extract_and_grade(), _extract_blind_patch(), _inject_tests_to_container(), Any, Path, Blind patch extraction and held-out verifier scoring. Executes uniformly across… (+30 more)

### Community 11 - "RunRecorder"
Cohesion: 0.13
Nodes (15): _clip(), MilestoneRecord, Any, Path, Run trace capture: the diagnostic record an evaluation leaves behind. Pass/fail…, Capture one driver turn, including the prompt that produced it., Capture a milestone attempt and its gate verdict., Persist the full held-out verifier output, untruncated. (+7 more)

### Community 12 - "test_docker_integration.py"
Cohesion: 0.17
Nodes (17): requires_docker, fixture, Path, Integration tests exercising a real Docker daemon. The unit suite mocks…, End-to-end: build the verifier image and have it write reward.json. Mirrors the…, reward.txt == -1 is an infrastructure failure, not a legitimate 0., End-to-end proof the exec lands inside the sandbox. The probe image carries a…, The regression this suite exists for. A bind mount shadows the image's /app.… (+9 more)

### Community 13 - "BaseCliDriver"
Cohesion: 0.16
Nodes (13): BaseCliDriver, CliDriverError, first(), Any, Path, RuntimeError, Turn the CLI's JSON result into telemetry., Raised when the agent CLI cannot be located or invoked. (+5 more)

### Community 14 - "PilotShowdownRunner"
Cohesion: 0.12
Nodes (14): AgentAdapter, Abstract evaluation adapter configuring workspace guidance and managing turns., MockContainer, PilotMockDriver, PilotShowdownRunner, Any, Path, Executes a single benchmark task across evaluation arms with isolated… (+6 more)

### Community 15 - "test_differential.py"
Cohesion: 0.19
Nodes (17): check_binaries(), normalize_state(), fixture, Path, Differential parity testing between superstate (Rust) and agent-rules (Python).…, Resolve a binary from env, then PATH (only if a name is given), then fallbacks.…, Both engines must parse a DAG plan and traverse every task identically., Recording an epistemic note must produce identical state on both engines. (+9 more)

### Community 16 - "test_runner.py"
Cohesion: 0.11
Nodes (23): EvaluationResult, Outcome of blind verification and patch extraction., Any, Path, Tests for AblationRunner telemetry and metrics integration. Validates that…, Verify fallback to 1.0 pass fraction when verifier stats are None and task…, Verify fallback to 0.0 pass fraction when verifier stats are None and task…, A result from a driver with a host shell carries a weaker guarantee. It must… (+15 more)

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

### Community 34 - "RunTelemetry"
Cohesion: 0.15
Nodes (19): Any, Auditable execution telemetry across an evaluation unit., RunTelemetry, _failure_signature(), generate_comparison_summary(), _harness_of(), Any, Evaluation reporter generating cost-efficiency frontier comparisons. (+11 more)

### Community 35 - ".run_task"
Cohesion: 0.18
Nodes (8): Model the harness was configured with, when the driver knows it., Isolated only with container_exec on: that is what removes host Bash., NoDriverConfiguredError, RuntimeError, Execute a single task under the specified arm and budget policy. Guarantees: 1.…, Translate a task's declared network policy into a docker network_mode. A task…, Raised when a live evaluation is requested without an agent driver., resolve_network_mode()

### Community 36 - "DockerManager"
Cohesion: 0.15
Nodes (14): DockerClient, DockerManager, Prune dangling images, stopped containers, and unreferenced volumes., Manages Docker containers and host disk resource reclamation., main(), Run a pilot benchmark showdown across Vanilla, Superpowers, and Superstate.…, Tests for Docker Lifecycle and Disk Space Watchdog., test_check_disk_space_healthy() (+6 more)

### Community 37 - "TaskSpec"
Cohesion: 0.22
Nodes (14): load_benchmark_tasks(), load_task_from_dir(), Path, Scan directory tree for benchmark task directories containing task.toml., Specification of an evaluation benchmark task., Directory holding the held-out verifier (Dockerfile, test.sh, grader.py)., Parse task.toml and instruction.md from task_dir into a TaskSpec., TaskSpec (+6 more)

### Community 38 - "test_ablation_runner.py"
Cohesion: 0.21
Nodes (14): compute_control_plane_lift(), Measure what each layer adds to a given harness, task by task. This evaluation…, Render control-plane lift, with the caveat that small n cannot support it., render_lift_report(), _fake_sandbox_factory(), _paired(), Tests for Ablation Runner and Reporter., Build a run_sandbox stand-in that writes a passing verifier artifact. (+6 more)

### Community 39 - "Control-Plane Evaluation — Plan"
Cohesion: 0.13
Nodes (14): Control-Plane Evaluation — Plan, Harness defects found by running (all fixed), Parked, with reasons, Standing lesson from today, Stream 1 — Produce a credible measurement, Stream 2 — Rust parity — COMPLETE (2026-09-09), Task 1: Pin the engine explicitly and record it — DONE, Task 2: Drive the real state-engine loop — DONE (+6 more)

### Community 40 - "test_state_engine_loop.py"
Cohesion: 0.30
Nodes (12): requires_engine, _engines(), parametrize, Path, The superstate adapter driving a real state engine through a full loop. Every…, Succeeds every turn, recording the prompts it was given., ScriptedDriver, test_a_failing_gate_stops_the_run_and_is_reported() (+4 more)

### Community 41 - "SuperpowersAdapter"
Cohesion: 0.16
Nodes (9): Remove guidance files the task repo ships. Returns what was removed., strip_preexisting_guidance(), Any, Path, Adapter configuring markdown rules and vendored superpowers skills., Install markdown guidance and copy superpowers skills into workspace., Configure workspace with Superpowers guidance before execution begins., Record whether the vendored skills library was actually installed. (+1 more)

### Community 42 - "resolve_next_turn_prompt"
Cohesion: 0.24
Nodes (12): is_waiting_for_user_input(), Mechanical User and Autonomous Human-in-the-Loop Interceptor. Prevents…, Inspect agent output and return automated approval prompt if waiting, or None…, Analyze agent response text to detect if the agent paused for human approval or…, resolve_next_turn_prompt(), Tests for Mechanical User and Autonomous Human-in-the-Loop Elimination., test_is_waiting_for_user_input_detects_ask_question_tool(), test_is_waiting_for_user_input_detects_standard_approval_prompts() (+4 more)

### Community 43 - "AgentImageBuilder"
Cohesion: 0.21
Nodes (7): AgentImageBuilder, Builds the image the agent actually runs inside. The agent must not run on the…, Docker tags allow a restricted character set; image refs do not., Builds and caches per-task agent images., A deterministic tag: this image holds no secrets, so caching is safe. Unlike…, Build (or reuse) an image with the Claude Code CLI on top of `base_image`., _slug()

### Community 44 - "Superstate Resilience, Diagnostic Retry Loops, and Git Native State Tracking Design"
Cohesion: 0.20
Nodes (9): 1. Context & Motivation, 2. Goals & Non-Goals, 3.1 Diagnostic Retry Loop in `lab/engine/adapters/superstate.py`, 3.2 Greenfield Git Resilience, 3. Architecture & Mechanics, 4. Verification & Testing, Goals, Non-Goals (+1 more)

### Community 45 - "docker_manager.py"
Cohesion: 0.28
Nodes (8): DiskSpaceError, ImageBuildError, RuntimeError, Docker lifecycle and host disk space management. Ensures deterministic…, Raised when host disk space falls below the critical emergency threshold., Raised when the task repository cannot be materialized onto the host., Raised when an image (typically the held-out verifier) cannot be built., WorkspaceSeedError

### Community 46 - ".check_disk_space_or_prune"
Cohesion: 0.25
Nodes (5): Container, Path, Copy the task repository out of `image` into the host directory `dest`. A bind…, Check available disk space. Prune docker if below min_free_gb; raise if below…, Run a container with guaranteed teardown upon context exit. Guarantees that the…

### Community 47 - "Global Constraints"
Cohesion: 0.25
Nodes (7): Global Constraints, Superstate Resilience and Diagnostic Retry Loop Implementation Plan, Task 1: Implement Greenfield Git Handling in `lab/engine/adapters/superstate.py`, Task 2: Implement Milestone Diagnostic Retry Loop in `lab/engine/adapters/superstate.py`, Task 3: Unit Tests for Retry Loop & Greenfield Handling, Task 4: Native Git Initialization in Rust `superstate`, Task 5: Verification & Checkpoint

### Community 48 - ".__init__"
Cohesion: 0.29
Nodes (4): Path, Query current HEAD commit hash from workspace git repository., Parse completed task count from .agent-state/state.json if present., Check for forward progress signals and trigger lease extension on advancement.

### Community 49 - "FlakyGateDriver"
Cohesion: 0.33
Nodes (6): FlakyGateDriver, Path, Verify that a greenfield workspace without .git does not crash when advancing…, Fails on turn 1 by not creating marker.txt, then creates it on turn 2 after…, test_greenfield_workspace_advances_without_git(), test_milestone_retry_loop_on_failed_gate()

### Community 50 - ".build_image"
Cohesion: 0.33
Nodes (3): Build an image from `context_dir` and return its tag. Used for the held-out…, Build an image from an inline Dockerfile with no build context., Stop docker-py invoking every configured credential helper on build. docker-py…

### Community 51 - "_extract_collect_commands"
Cohesion: 0.67
Nodes (3): _extract_collect_commands(), Any, Ingest collector command sequences used to extract test or run artifacts.

## Knowledge Gaps
- **68 isolated node(s):** `superstate-eval`, `What is measured`, `What is reported`, `How a run works`, `Quick start` (+63 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 378 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TaskSpec` connect `TaskSpec` to `AblationRunner`, `SuperstateAdapter`, `test_agy_cli_driver.py`, `ClaudeCliDriver`, `.run_task`, `test_ablation_runner.py`, `AgentDriver`, `TurnBasedAdapter`, `extract_and_grade`, `test_state_engine_loop.py`, `BaseCliDriver`, `PilotShowdownRunner`, `test_runner.py`, `FlakyGateDriver`, `InContainerClaudeDriver`?**
  _High betweenness centrality (0.167) - this node is a cross-community bridge._
- **Why does `AblationRunner` connect `AblationRunner` to `SuperstateAdapter`, `RunTelemetry`, `.run_task`, `DockerManager`, `TaskSpec`, `BudgetPolicy`, `AnswerKeyGuard`, `AgentDriver`, `SuperpowersAdapter`, `HeldOutVerifier`, `RunRecorder`, `test_ablation_runner.py`, `PilotShowdownRunner`, `test_runner.py`?**
  _High betweenness centrality (0.112) - this node is a cross-community bridge._
- **Why does `DockerManager` connect `DockerManager` to `AblationRunner`, `AnswerKeyGuard`, `HeldOutVerifier`, `AgentDriver`, `AgentImageBuilder`, `test_docker_integration.py`, `docker_manager.py`, `PilotShowdownRunner`, `.check_disk_space_or_prune`, `.build_image`?**
  _High betweenness centrality (0.091) - this node is a cross-community bridge._
- **Are the 18 inferred relationships involving `TaskSpec` (e.g. with `AgentAdapter` and `AgentDriver`) actually correct?**
  _`TaskSpec` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `SuperstateAdapter` (e.g. with `TaskSpec` and `AgentDriver`) actually correct?**
  _`SuperstateAdapter` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `DriverTelemetry` (e.g. with `AgyCliDriver` and `BaseCliDriver`) actually correct?**
  _`DriverTelemetry` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `AblationRunner` (e.g. with `TaskSpec` and `AgentAdapter`) actually correct?**
  _`AblationRunner` has 14 INFERRED edges - model-reasoned connections that need verification._