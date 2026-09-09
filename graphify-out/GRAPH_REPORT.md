# Graph Report - superstate-eval  (2026-09-09)

## Corpus Check
- 53 files · ~25,248 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 600 nodes · 1280 edges · 34 communities (27 shown, 3 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 63 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ab5a9aa1`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- TaskSpec
- SuperstateAdapter
- AgyCliDriver
- ClaudeCliDriver
- handle
- BudgetPolicy
- ConcurrencyGovernor
- .execute
- task_loader.py
- .execute
- extract_and_grade
- RunRecorder
- test_docker_integration.py
- HeldOutVerifier
- DockerManager
- test_differential.py
- .build_image
- Architecture Specification: Antigravity CLI Driver (`AgyCliDriver`) & Container Execution Bridge
- Architecture Specification: Concurrent Evaluation Isolation & Universal Progress-Earned Budgeting
- Proposed File Changes
- docker_manager.py
- Global Constraints
- .prepare_workspace
- .clean_workspace
- Feature Implementation Plan
- superstate-eval Local Assessment Repository Implementation Plan
- superstate-eval
- benchmarks/__init__.py
- dag_plan.md
- superstate-eval

## God Nodes (most connected - your core abstractions)
1. `TaskSpec` - 49 edges
2. `DockerManager` - 36 edges
3. `SuperstateAdapter` - 34 edges
4. `AblationRunner` - 32 edges
5. `DriverTelemetry` - 30 edges
6. `AgentDriver` - 27 edges
7. `ClaudeCliDriver` - 24 edges
8. `AgyCliDriver` - 23 edges
9. `BudgetPolicy` - 21 edges
10. `ConcurrencyGovernor` - 21 edges

## Surprising Connections (you probably didn't know these)
- `MockDriver` --uses--> `TaskSpec`  [INFERRED]
  tests/test_adapters.py → lab/benchmarks/task_loader.py
- `test_load_task_from_dir_parses_task_toml_and_instruction()` --uses--> `TaskSpec`  [INFERRED]
  tests/test_task_loader.py → lab/benchmarks/task_loader.py
- `test_run_telemetry_serialization()` --calls--> `RunTelemetry`  [EXTRACTED]
  tests/test_budget_policy.py → lab/engine/budget_policy.py
- `test_held_out_verifier_builds_and_grades_in_its_own_container()` --uses--> `HeldOutVerifier`  [INFERRED]
  tests/test_docker_integration.py → lab/engine/verifier.py
- `test_check_disk_space_raises_on_emergency_limit()` --uses--> `DiskSpaceError`  [INFERRED]
  tests/test_docker_manager.py → lab/sandbox/docker_manager.py

## Import Cycles
- None detected.

## Communities (34 total, 3 thin omitted)

### Community 0 - "TaskSpec"
Cohesion: 0.05
Nodes (58): Specification of an evaluation benchmark task., TaskSpec, AgentDriver, Abstract driver interface communicating with an underlying agent runtime.…, Run an agent session or turn within the target workspace., Any, Auditable execution telemetry across an evaluation unit., RunTelemetry (+50 more)

### Community 1 - "SuperstateAdapter"
Cohesion: 0.10
Nodes (42): AgentAdapter, DriverTelemetry, Base interfaces and data structures for execution adapters and agent drivers., Outcome and telemetry metrics from a single driver invocation turn., Outcome and telemetry metrics for a complete task execution run., Abstract evaluation adapter configuring workspace guidance and managing turns., Base template adapter managing bounded turn execution and mechanical approval., TaskRunResult (+34 more)

### Community 2 - "AgyCliDriver"
Cohesion: 0.11
Nodes (35): Name of the evaluation arm., AgyCliDriver, AgyCliDriverError, estimate_cost_usd(), Any, Path, RuntimeError, Driver for running evaluation tasks against Google Antigravity CLI (agy).… (+27 more)

### Community 3 - "ClaudeCliDriver"
Cohesion: 0.12
Nodes (35): ClaudeCliDriver, ClaudeCliDriverError, estimate_cost_usd(), _first(), Any, Path, RuntimeError, A live AgentDriver backed by the Claude Code CLI. The agent process runs on the… (+27 more)

### Community 4 - "handle"
Cohesion: 0.13
Nodes (25): ContainerExec, _error(), handle(), log(), main(), Any, A minimal stdio MCP server exposing exactly one tool: exec in ONE container.…, Handle one JSON-RPC message. Returns a response, or None for notifications. (+17 more)

### Community 5 - "BudgetPolicy"
Cohesion: 0.11
Nodes (20): BudgetPolicy, Progress-earned budget policy and execution telemetry accounting. Allows…, Manages progress-earned execution timeouts., Record completed milestone and grant progress lease extension if within max…, ProgressTracker, Path, Universal progress tracker for granting runtime lease extensions across…, Monitors workspace state and awards progress-earned lease extensions to any arm. (+12 more)

### Community 6 - "ConcurrencyGovernor"
Cohesion: 0.12
Nodes (23): ConcurrencyGovernor, Path, Machine-aware dynamic concurrency governor for isolated evaluation execution., Block until an execution slot is available under live resource constraints., Release an active execution slot and notify waiting tasks., Context manager acquiring a dynamic concurrency slot., Hardware capacity snapshot used to determine safe concurrency bounds., Governs evaluation concurrency dynamically based on host machine resources. (+15 more)

### Community 7 - ".execute"
Cohesion: 0.10
Nodes (20): compose_turnkey_milestone_prompt(), _extract_plan_milestones(), find_superstate_binary(), Milestone, Any, BudgetHook, Path, Construct an O(1) bounded subagent turnkey prompt with negative constraints. (+12 more)

### Community 8 - "task_loader.py"
Cohesion: 0.11
Nodes (22): _extract_collect_commands(), load_benchmark_tasks(), load_task_from_dir(), Any, Path, Benchmark task specification and loader module. Parses SWE-bench / Harbor style…, Scan directory tree for benchmark task directories containing task.toml., Ingest collector command sequences used to extract test or run artifacts. (+14 more)

### Community 9 - ".execute"
Cohesion: 0.11
Nodes (20): Any, BudgetHook, Path, Configure or sanitize workspace prior to agent invocation., Provide initial instruction prompt for the task., Report arm-specific facts about how this run was actually configured., Execute task across sequential turns with bounded caps and autonomous approval., Execute a task in the given workspace using the provided driver. (+12 more)

### Community 10 - "extract_and_grade"
Cohesion: 0.14
Nodes (20): Directory holding the held-out verifier (Dockerfile, test.sh, grader.py)., EvaluationResult, extract_and_grade(), Any, Path, Blind patch extraction and held-out verifier scoring. Executes uniformly across…, Outcome of blind verification and patch extraction., Execute blind grading against the container and extract patches/telemetry. This… (+12 more)

### Community 11 - "RunRecorder"
Cohesion: 0.13
Nodes (15): _clip(), MilestoneRecord, Any, Path, Run trace capture: the diagnostic record an evaluation leaves behind. Pass/fail…, Capture one driver turn, including the prompt that produced it., Capture a milestone attempt and its gate verdict., Persist the full held-out verifier output, untruncated. (+7 more)

### Community 12 - "test_docker_integration.py"
Cohesion: 0.17
Nodes (19): Raised when the task repository cannot be materialized onto the host., WorkspaceSeedError, requires_docker, fixture, Path, Integration tests exercising a real Docker daemon. The unit suite mocks…, End-to-end: build the verifier image and have it write reward.json. Mirrors the…, reward.txt == -1 is an infrastructure failure, not a legitimate 0. (+11 more)

### Community 13 - "HeldOutVerifier"
Cohesion: 0.15
Nodes (14): HeldOutVerifier, Any, Path, Held-out verification in a separate container. The benchmark's own contract…, Build the verifier image for `task` and return its tag., Run the held-out verifier against the collected patch. `logs_dir` must already…, Result of running the held-out verifier., Strict gate: the verifier must have produced a reward of 1.0. (+6 more)

### Community 14 - "DockerManager"
Cohesion: 0.19
Nodes (12): DockerClient, DockerManager, Prune dangling images, stopped containers, and unreferenced volumes., Manages Docker containers and host disk resource reclamation., Tests for Docker Lifecycle and Disk Space Watchdog., test_check_disk_space_healthy(), test_check_disk_space_raises_on_emergency_limit(), test_check_disk_space_triggers_prune_when_below_min() (+4 more)

### Community 15 - "test_differential.py"
Cohesion: 0.21
Nodes (13): check_binaries(), fixture, Path, Differential parity testing between superstate (Rust) and agent-rules (Python).…, Dynamically resolve binary executable from env, PATH, or fallback locations., Both engines must parse a DAG plan and traverse every task identically., Recording an epistemic note must produce identical state on both engines., _resolve_binary() (+5 more)

### Community 16 - ".build_image"
Cohesion: 0.17
Nodes (7): Container, Path, Copy the task repository out of `image` into the host directory `dest`. A bind…, Build an image from `context_dir` and return its tag. Used for the held-out…, Stop docker-py invoking every configured credential helper on build. docker-py…, Check available disk space. Prune docker if below min_free_gb; raise if below…, Run a container with guaranteed teardown upon context exit. Guarantees that the…

### Community 17 - "Architecture Specification: Antigravity CLI Driver (`AgyCliDriver`) & Container Execution Bridge"
Cohesion: 0.17
Nodes (11): 1. Executive Summary & Context, 2. Core Objectives, 3.1 Class Definition (`lab/engine/drivers/agy_cli.py`), 3.2 CLI Binary Resolution, 3.3 Command Construction, 3.4 Telemetry & Pricing, 3. Architecture & Driver Implementation, 4. Container Execution Bridge (`./run-in-container`) (+3 more)

### Community 18 - "Architecture Specification: Concurrent Evaluation Isolation & Universal Progress-Earned Budgeting"
Cohesion: 0.22
Nodes (8): 1. Executive Summary & Goals, 2. Dynamic Concurrency Governor, 3. Strict Docker Sandbox Quotas & Volume Isolation, 4. Universal Progress-Earned Budget Policy, 5. Blind Extraction and Grading Pipeline, 6. Verification and Efficacy Frontiers, Architecture Specification: Concurrent Evaluation Isolation & Universal Progress-Earned Budgeting, Core Objectives

### Community 19 - "Proposed File Changes"
Cohesion: 0.25
Nodes (7): Concurrent Evaluation Isolation & Universal Progress Budgeting Implementation Plan, Proposed File Changes, Task 1: Dynamic Machine-Aware Concurrency Governor, Task 2: Container Resource Constraints & Volume Isolation, Task 3: Universal Progress-Earned Budget Tracker, Task 4: Blind Extraction & Verification Pipeline, Task 5: End-to-End Concurrent Runner & Integration

### Community 20 - "docker_manager.py"
Cohesion: 0.33
Nodes (6): DiskSpaceError, ImageBuildError, RuntimeError, Docker lifecycle and host disk space management. Ensures deterministic…, Raised when host disk space falls below the critical emergency threshold., Raised when an image (typically the held-out verifier) cannot be built.

### Community 21 - "Global Constraints"
Cohesion: 0.33
Nodes (5): Antigravity CLI Driver (`AgyCliDriver`) Implementation Plan, Global Constraints, Task 1: Implement `AgyCliDriver` Core and Container Execution Bridge, Task 2: Verify Baseline and System Integration, Task 3: Execute Live Single-Task Smoke Run

### Community 22 - ".prepare_workspace"
Cohesion: 0.50
Nodes (3): Path, Install markdown guidance and copy superpowers skills into workspace., Configure workspace with Superpowers guidance before execution begins.

### Community 23 - ".clean_workspace"
Cohesion: 0.50
Nodes (3): Path, Sanitize workspace by removing all guidance, rule files, and skills., Ensure pristine unguided workspace before execution.

### Community 24 - "Feature Implementation Plan"
Cohesion: 0.40
Nodes (4): Feature Implementation Plan, Task 1: Setup database schema, Task 2: Implement repository methods, Task 3: Expose REST endpoint

### Community 25 - "superstate-eval Local Assessment Repository Implementation Plan"
Cohesion: 0.50
Nodes (3): superstate-eval Local Assessment Repository Implementation Plan, Tasks, Verification & Completion Gates

### Community 26 - "superstate-eval"
Cohesion: 0.50
Nodes (3): Purpose, Quick Start, superstate-eval

## Knowledge Gaps
- **31 isolated node(s):** `superstate-eval`, `Purpose`, `Quick Start`, `Task 1: Implement `AgyCliDriver` Core and Container Execution Bridge`, `Task 2: Verify Baseline and System Integration` (+26 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 248 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TaskSpec` connect `TaskSpec` to `SuperstateAdapter`, `AgyCliDriver`, `ClaudeCliDriver`, `.execute`, `task_loader.py`, `.execute`, `extract_and_grade`?**
  _High betweenness centrality (0.178) - this node is a cross-community bridge._
- **Why does `DockerManager` connect `DockerManager` to `TaskSpec`, `SuperstateAdapter`, `task_loader.py`, `test_docker_integration.py`, `HeldOutVerifier`, `.build_image`, `docker_manager.py`?**
  _High betweenness centrality (0.111) - this node is a cross-community bridge._
- **Why does `AblationRunner` connect `TaskSpec` to `SuperstateAdapter`, `BudgetPolicy`, `ConcurrencyGovernor`, `task_loader.py`, `RunRecorder`, `HeldOutVerifier`, `DockerManager`?**
  _High betweenness centrality (0.101) - this node is a cross-community bridge._
- **Are the 11 inferred relationships involving `TaskSpec` (e.g. with `AgentAdapter` and `AgentDriver`) actually correct?**
  _`TaskSpec` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `DockerManager` (e.g. with `PilotShowdownRunner` and `AblationRunner`) actually correct?**
  _`DockerManager` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `SuperstateAdapter` (e.g. with `TaskSpec` and `AgentDriver`) actually correct?**
  _`SuperstateAdapter` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `AblationRunner` (e.g. with `TaskSpec` and `AgentAdapter`) actually correct?**
  _`AblationRunner` has 13 INFERRED edges - model-reasoned connections that need verification._