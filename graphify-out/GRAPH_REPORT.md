# Graph Report - container-worktree-symlink  (2026-09-11)

## Corpus Check
- 84 files · ~47,763 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 939 nodes · 2052 edges · 60 communities (50 shown, 6 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 113 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e598ca05`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- SuperstateAdapter
- AgyCliDriver
- extract_and_grade
- ClaudeCliDriver
- AnswerKeyGuard
- ConcurrencyGovernor
- handle
- TaskSpec
- test_ablation_runner.py
- DockerManager
- InContainerClaudeDriver
- AblationRunner
- BudgetPolicy
- RunRecorder
- test_docker_integration.py
- .run_task
- test_runner.py
- verifier.py
- test_differential.py
- TurnBasedAdapter
- BaseCliDriver
- load_task_from_dir
- base.py
- Control-Plane Evaluation — Plan
- test_state_engine_loop.py
- resolve_next_turn_prompt
- AgentDriver
- Architecture Specification: Antigravity CLI Driver (`AgyCliDriver`) & Container Execution Bridge
- SuperpowersAdapter
- HeldOutVerifier
- Superstate Resilience, Diagnostic Retry Loops, and Git Native State Tracking Design
- AgentImageBuilder
- superstate-eval
- test_superstate_resilience.py
- Architecture Specification: Concurrent Evaluation Isolation & Universal Progress-Earned Budgeting
- 2. Architectural Design
- .check_disk_space_or_prune
- Proposed File Changes
- Global Constraints
- .__init__
- ImageBuildError
- paired_run.py
- Global Constraints
- Global Constraints
- Design Spec: Dynamic Container Workspace Switching for Worktree Isolation
- test_agent_failure_is_diagnosed_before_the_grading_symptom
- Global Constraints
- .clean_workspace
- Feature Implementation Plan
- superstate-eval Local Assessment Repository Implementation Plan
- _fake_sandbox_factory
- benchmarks/__init__.py
- .to_dict
- dag_plan.md
- test_ablation_runner_execution_and_cleanup
- superstate-eval

## God Nodes (most connected - your core abstractions)
1. `SuperstateAdapter` - 74 edges
2. `TaskSpec` - 70 edges
3. `DriverTelemetry` - 60 edges
4. `AblationRunner` - 43 edges
5. `AgentDriver` - 42 edges
6. `DockerManager` - 38 edges
7. `MockDriver` - 31 edges
8. `_make_dummy_task()` - 27 edges
9. `AgyCliDriver` - 26 edges
10. `extract_and_grade()` - 25 edges

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

## Communities (60 total, 6 thin omitted)

### Community 0 - "SuperstateAdapter"
Cohesion: 0.05
Nodes (82): DriverTelemetry, Outcome and telemetry metrics from a single driver invocation turn., _extract_plan_milestones(), flush(), find_superstate_binary(), Milestone, Any, BudgetHook (+74 more)

### Community 1 - "AgyCliDriver"
Cohesion: 0.10
Nodes (39): Name of the evaluation arm., AgyCliDriver, AgyCliDriverError, base_model_name(), estimate_cost_usd(), Any, Path, RuntimeError (+31 more)

### Community 2 - "extract_and_grade"
Cohesion: 0.10
Nodes (34): Whether the task has a Dockerfile in its tests/ directory., compute_test_metrics(), extract_and_grade(), _extract_blind_patch(), _inject_tests_to_container(), Any, Path, Extract patch by committing workspace changes and running task collection… (+26 more)

### Community 3 - "ClaudeCliDriver"
Cohesion: 0.14
Nodes (32): ClaudeCliDriver, ClaudeCliDriverError, estimate_cost_usd(), _first(), Any, Path, RuntimeError, Inline MCP config launching the container-exec server for THIS container. (+24 more)

### Community 4 - "AnswerKeyGuard"
Cohesion: 0.12
Nodes (27): AnswerKeyGuard, is_readable(), Path, Keep the held-out tests unreadable while the agent is working. A host-side…, Make `paths` unreadable for the duration of the block. Nests safely: concurrent…, Copy a directory somewhere readable before it is sealed. The verifier is built…, Whether the current process can list `path`. Used by tests and diagnostics., Seals and restores held-out test directories with thread-safe reference… (+19 more)

### Community 5 - "ConcurrencyGovernor"
Cohesion: 0.11
Nodes (24): ConcurrencyGovernor, Path, Machine-aware dynamic concurrency governor for isolated evaluation execution., Block until an execution slot is available under live resource constraints., Release an active execution slot and notify waiting tasks., Context manager acquiring a dynamic concurrency slot., Hardware capacity snapshot used to determine safe concurrency bounds., Governs evaluation concurrency dynamically based on host machine resources. (+16 more)

### Community 6 - "handle"
Cohesion: 0.13
Nodes (25): ContainerExec, _error(), handle(), log(), main(), Any, A minimal stdio MCP server exposing exactly one tool: exec in ONE container.…, Handle one JSON-RPC message. Returns a response, or None for notifications. (+17 more)

### Community 7 - "TaskSpec"
Cohesion: 0.12
Nodes (19): Benchmark task specification and loader module. Parses SWE-bench / Harbor style…, Specification of an evaluation benchmark task., TaskSpec, AgentAdapter, Abstract evaluation adapter configuring workspace guidance and managing turns., Arm C: Superstate (Deterministic State Engine) Adapter. Executes milestone DAGs…, MockContainer, PilotMockDriver (+11 more)

### Community 8 - "test_ablation_runner.py"
Cohesion: 0.15
Nodes (26): Auditable execution telemetry across an evaluation unit., RunTelemetry, compute_control_plane_lift(), _failure_signature(), generate_comparison_summary(), _harness_of(), Evaluation reporter generating cost-efficiency frontier comparisons., Render clustered failures as text, most frequent first. (+18 more)

### Community 9 - "DockerManager"
Cohesion: 0.11
Nodes (19): DockerClient, Builds the image the agent actually runs inside. The agent must not run on the…, DiskSpaceError, DockerManager, RuntimeError, Docker lifecycle and host disk space management. Ensures deterministic…, Raised when host disk space falls below the critical emergency threshold., Prune dangling images, stopped containers, and unreferenced volumes. (+11 more)

### Community 10 - "InContainerClaudeDriver"
Cohesion: 0.16
Nodes (21): _first(), InContainerClaudeDriver, InContainerDriverError, Any, Path, RuntimeError, Raised when the in-container agent cannot be invoked., Build the shell line executed inside the container. The prompt is base64'd so… (+13 more)

### Community 11 - "AblationRunner"
Cohesion: 0.12
Nodes (17): Arm A: Vanilla (Control) Adapter. Runs unguided SWE-bench baseline execution…, Unguided baseline adapter enforcing complete isolation from rules or skills., VanillaAdapter, AblationRunner, Ablation and efficacy benchmark runner. Executes evaluation arms (Vanilla,…, Executes benchmark tasks across evaluation arms with resource and lease…, main(), Run a live single-task smoke test using AblationRunner and AgyCliDriver. (+9 more)

### Community 12 - "BudgetPolicy"
Cohesion: 0.14
Nodes (16): BudgetPolicy, Progress-earned budget policy and execution telemetry accounting. Allows…, Manages progress-earned execution timeouts., Record completed milestone and grant progress lease extension if within max…, ProgressTracker, Universal progress tracker for granting runtime lease extensions across…, Monitors workspace state and awards progress-earned lease extensions to any arm., Tests for Progress-Earned Budget Policy and Telemetry Accounting. (+8 more)

### Community 13 - "RunRecorder"
Cohesion: 0.13
Nodes (15): _clip(), MilestoneRecord, Any, Path, Run trace capture: the diagnostic record an evaluation leaves behind. Pass/fail…, Capture one driver turn, including the prompt that produced it., Capture a milestone attempt and its gate verdict., Persist the full held-out verifier output, untruncated. (+7 more)

### Community 14 - "test_docker_integration.py"
Cohesion: 0.16
Nodes (19): Raised when the task repository cannot be materialized onto the host., WorkspaceSeedError, requires_docker, fixture, Path, Integration tests exercising a real Docker daemon. The unit suite mocks…, End-to-end: build the verifier image and have it write reward.json. Mirrors the…, reward.txt == -1 is an infrastructure failure, not a legitimate 0. (+11 more)

### Community 15 - ".run_task"
Cohesion: 0.12
Nodes (14): Model the harness was configured with, when the driver knows it., Isolated only with container_exec on: that is what removes host Bash., InsufficientResourcesError, NoDriverConfiguredError, Any, RuntimeError, Execute a single task under the specified arm and budget policy. Guarantees: 1.…, Resolve a cohort entry into (task_id, image, base_budget_sec, task_spec). (+6 more)

### Community 16 - "test_runner.py"
Cohesion: 0.16
Nodes (17): EvaluationResult, Blind patch extraction and held-out verifier scoring. Executes uniformly across…, Outcome of blind verification and patch extraction., Any, Path, Tests for AblationRunner telemetry and metrics integration. Validates that…, Verify fallback to 1.0 pass fraction when verifier stats are None and task…, Verify fallback to 0.0 pass fraction when verifier stats are None and task… (+9 more)

### Community 17 - "verifier.py"
Cohesion: 0.15
Nodes (14): Any, Path, Held-out verification in a separate container. The benchmark's own contract…, Build the verifier image for `task` and return its tag., Run the held-out verifier against the collected patch. `logs_dir` must already…, Delete the verifier image so the hidden tests do not linger on the host., Run the built verifier image against the collected patch., Result of running the held-out verifier. (+6 more)

### Community 18 - "test_differential.py"
Cohesion: 0.19
Nodes (17): check_binaries(), normalize_state(), fixture, Path, Differential parity testing between superstate (Rust) and agent-rules (Python).…, Resolve a binary from env, then PATH (only if a name is given), then fallbacks.…, Both engines must parse a DAG plan and traverse every task identically., Recording an epistemic note must produce identical state on both engines. (+9 more)

### Community 19 - "TurnBasedAdapter"
Cohesion: 0.18
Nodes (11): Any, BudgetHook, Path, Run an agent session or turn within the target workspace., Execute a task in the given workspace using the provided driver., Base template adapter managing bounded turn execution and mechanical approval., Configure or sanitize workspace prior to agent invocation., Provide initial instruction prompt for the task. (+3 more)

### Community 20 - "BaseCliDriver"
Cohesion: 0.16
Nodes (13): BaseCliDriver, CliDriverError, first(), Any, Path, RuntimeError, Turn the CLI's JSON result into telemetry., Raised when the agent CLI cannot be located or invoked. (+5 more)

### Community 21 - "load_task_from_dir"
Cohesion: 0.18
Nodes (14): _extract_collect_commands(), load_benchmark_tasks(), load_task_from_dir(), Any, Path, Scan directory tree for benchmark task directories containing task.toml., Directory holding the held-out verifier (Dockerfile, test.sh, grader.py)., Ingest collector command sequences used to extract test or run artifacts. (+6 more)

### Community 22 - "base.py"
Cohesion: 0.15
Nodes (11): Base interfaces and data structures for execution adapters and agent drivers., Remove guidance files the task repo ships. Returns what was removed., Outcome and telemetry metrics for a complete task execution run., strip_preexisting_guidance(), TaskRunResult, Arm adapters for Vanilla, Superpowers, and Superstate execution., Arm B: Superpowers Adapter. Installs standard AGENTS.md rules and vendored…, estimate_cost_usd() (+3 more)

### Community 23 - "Control-Plane Evaluation — Plan"
Cohesion: 0.13
Nodes (14): Control-Plane Evaluation — Plan, Harness defects found by running (all fixed), Parked, with reasons, Standing lesson from today, Stream 1 — Produce a credible measurement, Stream 2 — Rust parity — COMPLETE (2026-09-09), Task 1: Pin the engine explicitly and record it — DONE, Task 2: Drive the real state-engine loop — DONE (+6 more)

### Community 24 - "test_state_engine_loop.py"
Cohesion: 0.30
Nodes (12): requires_engine, _engines(), parametrize, Path, The superstate adapter driving a real state engine through a full loop. Every…, Succeeds every turn, recording the prompts it was given., ScriptedDriver, test_a_failing_gate_stops_the_run_and_is_reported() (+4 more)

### Community 25 - "resolve_next_turn_prompt"
Cohesion: 0.24
Nodes (12): is_waiting_for_user_input(), Mechanical User and Autonomous Human-in-the-Loop Interceptor. Prevents…, Inspect agent output and return automated approval prompt if waiting, or None…, Analyze agent response text to detect if the agent paused for human approval or…, resolve_next_turn_prompt(), Tests for Mechanical User and Autonomous Human-in-the-Loop Elimination., test_is_waiting_for_user_input_detects_ask_question_tool(), test_is_waiting_for_user_input_detects_standard_approval_prompts() (+4 more)

### Community 26 - "AgentDriver"
Cohesion: 0.19
Nodes (9): AgentDriver, Abstract driver interface communicating with an underlying agent runtime.…, Driver for running evaluation tasks against Google Antigravity CLI (agy).…, A live AgentDriver backed by the Claude Code CLI. The agent process runs on the…, Path, test_agy_cli_driver_run_in_container_sets_workdir(), test_runner_mounts_workspace_root_and_inits_symlink(), fake_run_sandbox() (+1 more)

### Community 27 - "Architecture Specification: Antigravity CLI Driver (`AgyCliDriver`) & Container Execution Bridge"
Cohesion: 0.17
Nodes (11): 1. Executive Summary & Context, 2. Core Objectives, 3.1 Class Definition (`lab/engine/drivers/agy_cli.py`), 3.2 CLI Binary Resolution, 3.3 Command Construction, 3.4 Telemetry & Pricing, 3. Architecture & Driver Implementation, 4. Container Execution Bridge (`./run-in-container`) (+3 more)

### Community 28 - "SuperpowersAdapter"
Cohesion: 0.20
Nodes (7): Any, Path, Adapter configuring markdown rules and vendored superpowers skills., Install markdown guidance and copy superpowers skills into workspace., Configure workspace with Superpowers guidance before execution begins., Record whether the vendored skills library was actually installed., SuperpowersAdapter

### Community 29 - "HeldOutVerifier"
Cohesion: 0.42
Nodes (10): HeldOutVerifier, Builds and runs the task's own verifier image., _manager(), Path, The verifier image is the held-out answer key; it must not linger on the host., _Task, test_keep_image_is_opt_in_for_debugging(), test_verifier_image_is_removed_after_grading() (+2 more)

### Community 30 - "Superstate Resilience, Diagnostic Retry Loops, and Git Native State Tracking Design"
Cohesion: 0.20
Nodes (9): 1. Context & Motivation, 2. Goals & Non-Goals, 3.1 Diagnostic Retry Loop in `lab/engine/adapters/superstate.py`, 3.2 Greenfield Git Resilience, 3. Architecture & Mechanics, 4. Verification & Testing, Goals, Non-Goals (+1 more)

### Community 31 - "AgentImageBuilder"
Cohesion: 0.24
Nodes (6): AgentImageBuilder, Docker tags allow a restricted character set; image refs do not., Builds and caches per-task agent images., A deterministic tag: this image holds no secrets, so caching is safe. Unlike…, Build (or reuse) an image with the Claude Code CLI on top of `base_image`., _slug()

### Community 32 - "superstate-eval"
Cohesion: 0.20
Nodes (9): A note on what this harness has taught us, Differential parity, How a run works, Layout, Quick start, superstate-eval, Tasks, What is measured (+1 more)

### Community 33 - "test_superstate_resilience.py"
Cohesion: 0.27
Nodes (7): FlakyGateDriver, Path, Tests for Superstate milestone retry loops and greenfield resilience., Verify that a greenfield workspace without .git does not crash when advancing…, Fails on turn 1 by not creating marker.txt, then creates it on turn 2 after…, test_greenfield_workspace_advances_without_git(), test_milestone_retry_loop_on_failed_gate()

### Community 34 - "Architecture Specification: Concurrent Evaluation Isolation & Universal Progress-Earned Budgeting"
Cohesion: 0.22
Nodes (8): 1. Executive Summary & Goals, 2. Dynamic Concurrency Governor, 3. Strict Docker Sandbox Quotas & Volume Isolation, 4. Universal Progress-Earned Budget Policy, 5. Blind Extraction and Grading Pipeline, 6. Verification and Efficacy Frontiers, Architecture Specification: Concurrent Evaluation Isolation & Universal Progress-Earned Budgeting, Core Objectives

### Community 35 - "2. Architectural Design"
Cohesion: 0.22
Nodes (8): 1. Context & Motivation, 2.1 EvaluationResult Dataclass Extension, 2.2 Metric Extraction Helper, 2.3 AblationRunner Telemetry Integration, 2.4 CLI Output Formatting, 2. Architectural Design, 3. Testing & Verification, Design Specification: Test Pass Fraction & Test Statistics Propagation

### Community 36 - ".check_disk_space_or_prune"
Cohesion: 0.25
Nodes (5): Container, Path, Copy the task repository out of `image` into the host directory `dest`. A bind…, Check available disk space. Prune docker if below min_free_gb; raise if below…, Run a container with guaranteed teardown upon context exit. Guarantees that the…

### Community 37 - "Proposed File Changes"
Cohesion: 0.25
Nodes (7): Concurrent Evaluation Isolation & Universal Progress Budgeting Implementation Plan, Proposed File Changes, Task 1: Dynamic Machine-Aware Concurrency Governor, Task 2: Container Resource Constraints & Volume Isolation, Task 3: Universal Progress-Earned Budget Tracker, Task 4: Blind Extraction & Verification Pipeline, Task 5: End-to-End Concurrent Runner & Integration

### Community 38 - "Global Constraints"
Cohesion: 0.25
Nodes (7): Global Constraints, Superstate Resilience and Diagnostic Retry Loop Implementation Plan, Task 1: Implement Greenfield Git Handling in `lab/engine/adapters/superstate.py`, Task 2: Implement Milestone Diagnostic Retry Loop in `lab/engine/adapters/superstate.py`, Task 3: Unit Tests for Retry Loop & Greenfield Handling, Task 4: Native Git Initialization in Rust `superstate`, Task 5: Verification & Checkpoint

### Community 39 - ".__init__"
Cohesion: 0.29
Nodes (4): Path, Query current HEAD commit hash from workspace git repository., Parse completed task count from .agent-state/state.json if present., Check for forward progress signals and trigger lease extension on advancement.

### Community 40 - "ImageBuildError"
Cohesion: 0.29
Nodes (5): ImageBuildError, Build an image from `context_dir` and return its tag. Used for the held-out…, Build an image from an inline Dockerfile with no build context., Stop docker-py invoking every configured credential helper on build. docker-py…, Raised when an image (typically the held-out verifier) cannot be built.

### Community 41 - "paired_run.py"
Cohesion: 0.33
Nodes (5): Any, Render summary as a formatted text table for reports., render_summary_table(), main(), Run one or more tasks across all arms and report control-plane lift. The…

### Community 42 - "Global Constraints"
Cohesion: 0.33
Nodes (5): Antigravity CLI Driver (`AgyCliDriver`) Implementation Plan, Global Constraints, Task 1: Implement `AgyCliDriver` Core and Container Execution Bridge, Task 2: Verify Baseline and System Integration, Task 3: Execute Live Single-Task Smoke Run

### Community 43 - "Global Constraints"
Cohesion: 0.33
Nodes (5): Dynamic Container Workspace Switching Implementation Plan, Global Constraints, Task 1: Runner Mount Decoupling & Container Symlink Setup, Task 2: Worktree Turn Repointing in Superstate Adapter, Task 3: Live Verification on `db-wal-recovery`

### Community 44 - "Design Spec: Dynamic Container Workspace Switching for Worktree Isolation"
Cohesion: 0.33
Nodes (5): 1. Problem Statement, 2. Proposed Architecture, 3. Benefits & Performance, Design Spec: Dynamic Container Workspace Switching for Worktree Isolation, Dynamic `/app` Symlink via `/workspace_root` Mount

### Community 45 - "test_agent_failure_is_diagnosed_before_the_grading_symptom"
Cohesion: 0.33
Nodes (5): A result from a driver with a host shell carries a weaker guarantee. It must…, An agent that times out leaves a bad patch; the timeout is the cause. Reporting…, test_agent_failure_is_diagnosed_before_the_grading_symptom(), test_run_telemetry_records_whether_execution_was_isolated(), fake_sandbox()

### Community 46 - "Global Constraints"
Cohesion: 0.40
Nodes (4): Global Constraints, Task 1: Extend EvaluationResult and Implement compute_test_metrics, Task 2: Integrate Test Metrics into Runner Telemetry and CLI Output, Test Pass Fraction & Test Statistics Implementation Plan

### Community 47 - ".clean_workspace"
Cohesion: 0.50
Nodes (3): Path, Sanitize workspace by removing all guidance, rule files, and skills., Ensure pristine unguided workspace before execution.

### Community 48 - "Feature Implementation Plan"
Cohesion: 0.40
Nodes (4): Feature Implementation Plan, Task 1: Setup database schema, Task 2: Implement repository methods, Task 3: Expose REST endpoint

### Community 49 - "superstate-eval Local Assessment Repository Implementation Plan"
Cohesion: 0.50
Nodes (3): superstate-eval Local Assessment Repository Implementation Plan, Tasks, Verification & Completion Gates

## Knowledge Gaps
- **74 isolated node(s):** `superstate-eval`, `What is measured`, `What is reported`, `How a run works`, `Quick start` (+69 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 387 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TaskSpec` connect `TaskSpec` to `SuperstateAdapter`, `AgyCliDriver`, `extract_and_grade`, `ClaudeCliDriver`, `test_superstate_resilience.py`, `test_ablation_runner.py`, `InContainerClaudeDriver`, `AblationRunner`, `test_agent_failure_is_diagnosed_before_the_grading_symptom`, `.run_task`, `test_runner.py`, `TurnBasedAdapter`, `BaseCliDriver`, `load_task_from_dir`, `base.py`, `test_state_engine_loop.py`, `AgentDriver`?**
  _High betweenness centrality (0.160) - this node is a cross-community bridge._
- **Why does `AblationRunner` connect `AblationRunner` to `SuperstateAdapter`, `AnswerKeyGuard`, `ConcurrencyGovernor`, `TaskSpec`, `test_ablation_runner.py`, `DockerManager`, `paired_run.py`, `BudgetPolicy`, `RunRecorder`, `test_agent_failure_is_diagnosed_before_the_grading_symptom`, `.run_task`, `test_runner.py`, `test_ablation_runner_execution_and_cleanup`, `AgentDriver`, `SuperpowersAdapter`, `HeldOutVerifier`?**
  _High betweenness centrality (0.112) - this node is a cross-community bridge._
- **Why does `SuperstateAdapter` connect `SuperstateAdapter` to `test_superstate_resilience.py`, `TaskSpec`, `AblationRunner`, `RunRecorder`, `base.py`, `test_state_engine_loop.py`, `AgentDriver`?**
  _High betweenness centrality (0.096) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `SuperstateAdapter` (e.g. with `TaskSpec` and `AgentDriver`) actually correct?**
  _`SuperstateAdapter` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `TaskSpec` (e.g. with `AgentAdapter` and `AgentDriver`) actually correct?**
  _`TaskSpec` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `DriverTelemetry` (e.g. with `AgyCliDriver` and `BaseCliDriver`) actually correct?**
  _`DriverTelemetry` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `AblationRunner` (e.g. with `TaskSpec` and `AgentAdapter`) actually correct?**
  _`AblationRunner` has 14 INFERRED edges - model-reasoned connections that need verification._