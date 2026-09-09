# Graph Report - superstate-eval  (2026-09-09)

## Corpus Check
- 57 files · ~28,395 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 660 nodes · 1399 edges · 37 communities (30 shown, 3 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 68 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `8147eedf`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- AblationRunner
- DriverTelemetry
- AgyCliDriver
- ClaudeCliDriver
- handle
- BudgetPolicy
- ConcurrencyGovernor
- .execute
- runner.py
- TurnBasedAdapter
- extract_and_grade
- RunRecorder
- DockerManager
- base_cli.py
- TaskSpec
- test_differential.py
- test_runner.py
- Architecture Specification: Antigravity CLI Driver (`AgyCliDriver`) & Container Execution Bridge
- Architecture Specification: Concurrent Evaluation Isolation & Universal Progress-Earned Budgeting
- Proposed File Changes
- 2. Architectural Design
- Global Constraints
- AgentDriver
- Global Constraints
- Feature Implementation Plan
- superstate-eval Local Assessment Repository Implementation Plan
- superstate-eval
- benchmarks/__init__.py
- dag_plan.md
- superstate-eval
- .run_cohort
- .run_task
- StubDriver

## God Nodes (most connected - your core abstractions)
1. `TaskSpec` - 55 edges
2. `DriverTelemetry` - 37 edges
3. `DockerManager` - 36 edges
4. `SuperstateAdapter` - 34 edges
5. `AblationRunner` - 34 edges
6. `AgentDriver` - 31 edges
7. `ClaudeCliDriver` - 24 edges
8. `AgyCliDriver` - 23 edges
9. `BudgetPolicy` - 21 edges
10. `ConcurrencyGovernor` - 21 edges

## Surprising Connections (you probably didn't know these)
- `MockDriver` --uses--> `TaskSpec`  [INFERRED]
  tests/test_adapters.py → lab/benchmarks/task_loader.py
- `StubDriver` --uses--> `TaskSpec`  [INFERRED]
  tests/test_runner.py → lab/benchmarks/task_loader.py
- `test_load_task_from_dir_parses_task_toml_and_instruction()` --uses--> `TaskSpec`  [INFERRED]
  tests/test_task_loader.py → lab/benchmarks/task_loader.py
- `StubDriver` --uses--> `DriverTelemetry`  [INFERRED]
  tests/test_runner.py → lab/engine/adapters/base.py
- `test_ablation_runner_default_execution_mounts_workspace_into_container()` --uses--> `AgentDriver`  [INFERRED]
  tests/test_ablation_runner.py → lab/engine/adapters/base.py

## Import Cycles
- None detected.

## Communities (37 total, 3 thin omitted)

### Community 0 - "AblationRunner"
Cohesion: 0.16
Nodes (17): AblationRunner, InsufficientResourcesError, Raised when the host cannot safely run even a single concurrent evaluation., Executes benchmark tasks across evaluation arms with resource and lease…, _fake_sandbox_factory(), Tests for Ablation Runner and Reporter., Build a run_sandbox stand-in that writes a passing verifier artifact., A cohort of 8 GB tasks must not be dispatched at the 4 GB default width. (+9 more)

### Community 1 - "DriverTelemetry"
Cohesion: 0.10
Nodes (38): DriverTelemetry, Outcome and telemetry metrics from a single driver invocation turn., Outcome and telemetry metrics for a complete task execution run., TaskRunResult, Any, Path, Adapter configuring markdown rules and vendored superpowers skills., Install markdown guidance and copy superpowers skills into workspace. (+30 more)

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
Cohesion: 0.06
Nodes (38): BudgetPolicy, Any, Progress-earned budget policy and execution telemetry accounting. Allows…, Manages progress-earned execution timeouts., Record completed milestone and grant progress lease extension if within max…, Auditable execution telemetry across an evaluation unit., RunTelemetry, ProgressTracker (+30 more)

### Community 6 - "ConcurrencyGovernor"
Cohesion: 0.12
Nodes (23): ConcurrencyGovernor, Path, Machine-aware dynamic concurrency governor for isolated evaluation execution., Block until an execution slot is available under live resource constraints., Release an active execution slot and notify waiting tasks., Context manager acquiring a dynamic concurrency slot., Hardware capacity snapshot used to determine safe concurrency bounds., Governs evaluation concurrency dynamically based on host machine resources. (+15 more)

### Community 7 - ".execute"
Cohesion: 0.10
Nodes (20): compose_turnkey_milestone_prompt(), _extract_plan_milestones(), find_superstate_binary(), Milestone, Any, BudgetHook, Path, Construct an O(1) bounded subagent turnkey prompt with negative constraints. (+12 more)

### Community 8 - "runner.py"
Cohesion: 0.06
Nodes (46): _extract_collect_commands(), load_benchmark_tasks(), load_task_from_dir(), Any, Path, Benchmark task specification and loader module. Parses SWE-bench / Harbor style…, Scan directory tree for benchmark task directories containing task.toml., Directory holding the held-out verifier (Dockerfile, test.sh, grader.py). (+38 more)

### Community 9 - "TurnBasedAdapter"
Cohesion: 0.20
Nodes (10): Any, BudgetHook, Path, Configure or sanitize workspace prior to agent invocation., Provide initial instruction prompt for the task., Report arm-specific facts about how this run was actually configured., Execute task across sequential turns with bounded caps and autonomous approval., Execute a task in the given workspace using the provided driver. (+2 more)

### Community 10 - "extract_and_grade"
Cohesion: 0.12
Nodes (29): compute_test_metrics(), extract_and_grade(), Any, Path, Blind patch extraction and held-out verifier scoring. Executes uniformly across…, Execute blind grading against the container and extract patches/telemetry. This…, Compute normalized test pass fractions and counts from verifier statistics.…, Result of running the held-out verifier. (+21 more)

### Community 11 - "RunRecorder"
Cohesion: 0.13
Nodes (15): _clip(), MilestoneRecord, Any, Path, Run trace capture: the diagnostic record an evaluation leaves behind. Pass/fail…, Capture one driver turn, including the prompt that produced it., Capture a milestone attempt and its gate verdict., Persist the full held-out verifier output, untruncated. (+7 more)

### Community 12 - "DockerManager"
Cohesion: 0.05
Nodes (55): Container, DockerClient, HeldOutVerifier, Any, Path, Held-out verification in a separate container. The benchmark's own contract…, Build the verifier image for `task` and return its tag., Run the held-out verifier against the collected patch. `logs_dir` must already… (+47 more)

### Community 13 - "base_cli.py"
Cohesion: 0.14
Nodes (16): BaseCliDriver, CliDriverError, estimate_cost_usd(), first(), Any, Path, RuntimeError, Shared plumbing for agent drivers that shell out to a CLI. Subclasses supply… (+8 more)

### Community 14 - "TaskSpec"
Cohesion: 0.20
Nodes (9): Specification of an evaluation benchmark task., TaskSpec, MockContainer, PilotMockDriver, Any, Path, Execute task across arms and return structured benchmark outcomes. With…, Predictable mock driver simulating agent behavior for pilot verification. (+1 more)

### Community 15 - "test_differential.py"
Cohesion: 0.21
Nodes (13): check_binaries(), fixture, Path, Differential parity testing between superstate (Rust) and agent-rules (Python).…, Dynamically resolve binary executable from env, PATH, or fallback locations., Both engines must parse a DAG plan and traverse every task identically., Recording an epistemic note must produce identical state on both engines., _resolve_binary() (+5 more)

### Community 16 - "test_runner.py"
Cohesion: 0.27
Nodes (12): EvaluationResult, Outcome of blind verification and patch extraction., Path, Tests for AblationRunner telemetry and metrics integration. Validates that…, Verify fallback to 1.0 pass fraction when verifier stats are None and task…, Verify fallback to 0.0 pass fraction when verifier stats are None and task…, Instantiate an AblationRunner configured with mocked docker and governor.…, Verify that granular verifier statistics populate test metrics in telemetry… (+4 more)

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

### Community 22 - "AgentDriver"
Cohesion: 0.33
Nodes (4): AgentDriver, Abstract driver interface communicating with an underlying agent runtime.…, Run an agent session or turn within the target workspace., Path

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
Cohesion: 0.50
Nodes (3): Purpose, Quick Start, superstate-eval

### Community 34 - ".run_cohort"
Cohesion: 0.50
Nodes (3): Any, Resolve a cohort entry into (task_id, image, base_budget_sec, task_spec)., Execute a matrix of tasks x arms concurrently using the dynamic governor.

### Community 35 - ".run_task"
Cohesion: 0.50
Nodes (4): NoDriverConfiguredError, RuntimeError, Execute a single task under the specified arm and budget policy. Guarantees: 1.…, Raised when a live evaluation is requested without an agent driver.

### Community 36 - "StubDriver"
Cohesion: 0.40
Nodes (4): Any, Stub driver providing dummy execution telemetry for runner tests., Simulate agent execution by writing a stub solution file. Parameters: task:…, StubDriver

## Knowledge Gaps
- **39 isolated node(s):** `superstate-eval`, `Purpose`, `Quick Start`, `Task 1: Implement `AgyCliDriver` Core and Container Execution Bridge`, `Task 2: Verify Baseline and System Integration` (+34 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 275 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TaskSpec` connect `TaskSpec` to `AblationRunner`, `DriverTelemetry`, `AgyCliDriver`, `ClaudeCliDriver`, `.run_cohort`, `.run_task`, `StubDriver`, `.execute`, `runner.py`, `TurnBasedAdapter`, `extract_and_grade`, `base_cli.py`, `test_runner.py`, `AgentDriver`?**
  _High betweenness centrality (0.183) - this node is a cross-community bridge._
- **Why does `DockerManager` connect `DockerManager` to `runner.py`, `AblationRunner`, `AgentDriver`?**
  _High betweenness centrality (0.101) - this node is a cross-community bridge._
- **Why does `AblationRunner` connect `AblationRunner` to `DriverTelemetry`, `.run_cohort`, `.run_task`, `BudgetPolicy`, `ConcurrencyGovernor`, `runner.py`, `RunRecorder`, `DockerManager`, `TaskSpec`, `test_runner.py`, `AgentDriver`?**
  _High betweenness centrality (0.097) - this node is a cross-community bridge._
- **Are the 13 inferred relationships involving `TaskSpec` (e.g. with `AgentAdapter` and `AgentDriver`) actually correct?**
  _`TaskSpec` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `DriverTelemetry` (e.g. with `AgyCliDriver` and `BaseCliDriver`) actually correct?**
  _`DriverTelemetry` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `DockerManager` (e.g. with `PilotShowdownRunner` and `AblationRunner`) actually correct?**
  _`DockerManager` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `SuperstateAdapter` (e.g. with `TaskSpec` and `AgentDriver`) actually correct?**
  _`SuperstateAdapter` has 6 INFERRED edges - model-reasoned connections that need verification._