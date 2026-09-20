# Task Qualification Rubric for Superstate Evaluation

This document defines the formal admission requirements for any benchmark task evaluated in `superstate-eval`.

---

## 1. Scientific Rationale: Scoping the Operational Domain

Evaluating a software engineering control plane on single-file bash puzzles or visual riddles is a **category error**. 
In computer science:
* A database query optimizer is evaluated on complex relational schemas with joins and indexes—not on key-value lookups.
* A compiler optimizer is evaluated on deeply nested loops and AST trees—not on `print("hello world")`.

Likewise, [Superstate](https://github.com/climate-x-org/superstate) is not an LLM. It is an **autonomous software engineering operating system and control plane** designed to solve three concrete failures of raw LLMs working in real codebases:
1. **Context Bloat:** Massive compiler dumps and test tracebacks saturating the prompt window (solved by **Tool Output Shunting**).
2. **Iteration Latency:** Sluggish test feedback cycles re-running untouched suites (solved by **AST Test Impact Slicing**).
3. **Premature Completion & Hallucinated Fixes:** The LLM quitting early or compounding dirty working tree errors (solved by the **Autonomous TDD DAG** and **Scoped Git Rollback**).

If a task lacks a multi-file repository, has no existing test suite, or can be solved in a single turn by guessing a string, **none of Superstate's control-plane mechanisms are exercised.** Forcing a multi-milestone TDD state machine onto such puzzles adds overhead without testing the system.

Correctly scoping the benchmark problem space to genuine software engineering repositories is not "gaming the system"—it is the scientific foundation for measuring the control plane.

---

## 2. The Five Mandatory Task Qualification Requirements

Every task admitted to `SWE_CORE_TASKS` or `SWE_CANARY_TASKS` must satisfy all five criteria:

### Requirement 1: Multi-File Software Repository with Existing Test Suite
* **Requirement:** The task must operate within a real, multi-file software codebase containing internal packages, modules, and build configurations. It must possess an existing automated test suite (`pytest`, `go test`, `jest`/`npm test`, `cargo test`) that passes cleanly on untouched code.
* **Why Superstate Requires It:** AST impact slicing, dependency tracking, and regression prevention only function when modifying one file risks breaking another.
* **Immediate Disqualification:** Single-file scripts, standalone bash commands, or scratch directories with no existing tests to regress.

### Requirement 2: Sealed Held-Out Grader (`/tests/`)
* **Requirement:** The benchmark must ship a maintainer test suite sealed at container root (`/tests/`) that is never mounted into the workspace during the agent phase. The grader must evaluate both fail-to-pass (F2P) and pass-to-pass (P2P) assertions.
* **Why Superstate Requires It:** Protects the Anti-Cheating Invariant. Measuring an agent against tests it authored itself or relying on hand-authored synthetic fixtures distorts outcomes.
* **Immediate Disqualification:** Tasks lacking a held-out `/tests/` directory (`sqlite-db-truncate`, `sanitize-git-repo`).

### Requirement 3: Multi-Turn Architectural Complexity
* **Requirement:** The issue must require reading source code, understanding module contracts, and authoring an objective reproduction test before implementing a fix.
* **Why Superstate Requires It:** Evaluates the Autonomous TDD DAG (Milestone 1: reproduction test -> Milestone 2: fix).
* **Immediate Disqualification:** Tasks where the solution is stated verbatim in the issue prompt, simple 1-line syntax typos, or visual pattern riddles (`chess-best-move`).

### Requirement 4: Substantial Build / Test Telemetry
* **Requirement:** Executing the build or test suite must generate realistic compiler or test runner logs (>50 lines of stdout/stderr when failing).
* **Why Superstate Requires It:** Tests native Tool Output Shunting and context-window protection. If test failure outputs only a single word (e.g. `Fail`), shunting is vacuous.
* **Immediate Disqualification:** Tasks whose test runner produces no diagnostic tracebacks.

### Requirement 5: Discriminative Power (Anti-Ceiling & Anti-Floor)
* **Requirement:** The task must demonstrate discriminative headroom where the control plane can provide measurable lift.
* **Why Superstate Requires It:** Tasks where unassisted baselines solve them $\ge 90\%$ of the time (`openssl-selfsigned-cert` is 22/22 for vanilla) provide zero lift signal. Tasks where every arm fails at $0\%$ (`fastapi-deprecation-response-headers`) represent impossible tasks that consume compute without discriminating.
* **Immediate Disqualification:** Tasks at $\ge 90\%$ ceiling or $\le 5\%$ floor.

---

## 3. Candidate Task Admission Checklist

Before adding any task to `SWE_CORE_TASKS` in `lab/benchmarks/task_sets.py`, the author must verify:

```markdown
- [ ] 1. Repository: Is it a real multi-file codebase with existing passing tests?
- [ ] 2. Grader: Does it have a held-out, sealed verifier at /tests/?
- [ ] 3. Complexity: Does it require multi-turn source inspection and TDD reproduction?
- [ ] 4. Telemetry: Does running tests produce substantial stdout/stderr logs?
- [ ] 5. Headroom: Is baseline solve rate between 10% and 85% (not at ceiling or floor)?
```

---

## 4. Corpus Audit: FrontierHarness Eval Classification

Audit of the 30 tasks in `~/.cache/agent-rules/frontier-eval/tasks/`:

### Admitted: Canonical Repositories (`SWE_CORE_TASKS`, n=9)
All 9 satisfy Requirements 1–5:
1. `build-cython-ext` (Python/C — `SPOCKnots/pyknotid`) [Also in `SWE-Canary`]
2. `scc-bounded-memory-spilling` (Go — `boyter/scc`) [Also in `SWE-Canary`]
3. `katex-multicolumn-array-spans` (TypeScript — `KaTeX/KaTeX`) [Also in `SWE-Canary`]
4. `httpx-multipart-response-parsing` (Python — `encode/httpx`)
5. `expr-try-catch-errors` (Go — `expr-lang/expr`)
6. `anko-typed-variable-bindings` (Go — `mattn/anko`)
7. `meriyah-explicit-resource-declarations` (TypeScript — `meriyah/meriyah`)
8. `python-statemachine-state-data-scoping` (Python — `fgmacedo/python-statemachine`)
9. `arktype-json-schema-refs-dependencies` (TypeScript — `arktypeio/arktype`)

### Excluded: Toy Scripts & Command-Line Puzzles (Violate Req 1 & Req 3, n=5)
* `chess-best-move`: Visual image puzzle, 4-character answer, zero repository code.
* `regex-log`: Standalone script for parsing log timestamps.
* `vulnerable-secret`: Single-file string replacement.
* `extract-elf`: Reverse engineering binary extraction script.
* `dna-insert`: Single-file biological string manipulation script.

### Excluded: Ceilings & Floors (Violate Req 5, n=8)
* Ceilings ($\ge 95\%$ across arms): `openssl-selfsigned-cert`, `db-wal-recovery`, `git-leak-recovery`, `code-from-image`, `constraints-scheduling`, `gcode-to-text`, `kv-store-grpc`.
* Floor ($0\%$ across arms): `fastapi-deprecation-response-headers`.

### Excluded: Ungradeable (Violate Req 2, n=8)
Lack held-out `/tests/` directory: `sqlite-db-truncate`, `sanitize-git-repo`, `largest-eigenval`, `log-summary-date-ranges`, `merge-diff-arc-agi-task`, `modernize-scientific-stack`, `multi-source-data-merger`, `polyglot-c-py`.
