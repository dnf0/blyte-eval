# Design Specification: Repository-First Software Engineering Benchmarks

**Date:** 2026-09-20  
**Status:** Approved by User  
**Target Architecture:** Superstate Evaluation Harness (`superstate-eval`)

---

## 1. Executive Summary & Problem Diagnosis

### 1.1 The Category Error of Command-Line Puzzles
Past benchmark suites in this repository mixed two incompatible classes of work:
1. **Real Open-Source Repositories (DataCurve / Tier-1):** Multi-file codebases in Go, TypeScript, and Python with existing architectures, issue descriptions, and extensive test suites.
2. **Command-Line & Visual Script Puzzles (Terminal-Bench):** Single-file puzzles such as `chess-best-move` (reading a PNG image and writing a 4-character move string), `openssl-selfsigned-cert` (running a CLI utility), and `regex-log` (filtering a text file).

Evaluating Superstate on single-line script puzzles is a category error. Nobody needs an autonomous state engine, milestone DAGs, AST impact slicing, git commit checkpoints, or scoped rollbacks to solve a visual chess puzzle or run a bash command. Forcing an autonomous TDD state machine onto toy puzzles introduces ceremonial overhead (e.g., authoring pytest suites for a chess board, hitting review advisories on `.pyc` bytecode, rolling back git) that distorts evaluation metrics, inflates costs, and obscures real architectural lift.

### 1.2 The Canary Bottleneck
The historical `CANARY_TASKS` slice bundled:
* `chess-best-move` (a 1-turn toy puzzle)
* `build-cython-ext` (a real Python/C extension repository)
* `httpx-multipart-response-parsing` (a massive 90-minute repository task with 182 files and 122 tests)

Bundling a 90-minute task into a canary intended for 10–15 minute feedback loops caused runs to drag out over 45+ minutes while failing to test intermediate, cross-language repository engineering.

---

## 2. Core Principles & Invariants

1. **Repository-First Invariant:** Every evaluation task must be a genuine software engineering repository containing a multi-file source tree, an existing architecture, and an automated regression test suite. All single-file script puzzles and visual toys are permanently excluded.
2. **Tri-Language Representation:** The benchmark must reflect modern software engineering across the three dominant enterprise ecosystems:
   * **Python / C:** Dependency upgrades, C-extensions, package builds, and pytest suites.
   * **Go:** Systems programming, concurrency, memory management, and `go test` suites.
   * **TypeScript / JavaScript:** Frontend/compiler architecture, AST parsing, layout renderers, and Jest/npm suites.
3. **Anti-Cheating & Sealed Grader Integrity:** Held-out tests at container-root `/tests/` remain strictly sealed from the worker during the agent phase. Tasks must never leak the maintainer's reproduction test or answer key.
4. **Mechanical Justification:** The benchmark must specifically stress and evaluate Superstate's mechanical primitives:
   * **Tool Output Shunting:** Truncating large test and compiler outputs to prevent context saturation.
   * **AST Impact Slicing:** Slicing large test suites to only affected AST nodes for fast feedback.
   * **Scoped Git Rollback:** Deterministically rolling back failed attempts to milestone baselines.
   * **Autonomous TDD State DAG:** Enforcing reproduction tests (RED) before code modification (GREEN).

---

## 3. Two-Tier Suite Definition

### 3.1 Tier 1: `SWE-Canary` (Fast Tri-Language Loop, ~15–20 min total)
Designed for rapid iteration and PR gates. Exactly three tasks, each representing a distinct programming ecosystem:

| Task | Language | Upstream Repository | Scope of Engineering Work | Base Budget |
|---|---|---|---|---|
| **`build-cython-ext`** | Python / C | [`SPOCKnots/pyknotid`](https://github.com/SPOCKnots/pyknotid) | Upgrade C-extensions for NumPy 2.x C-API; build from source; fix pytest suite | 900s (15m) |
| **`scc-bounded-memory-spilling`** | Go | [`boyter/scc`](https://github.com/boyter/scc) | Implement disk-spilling aggregation pipeline for large repo walks | 1800s (30m) |
| **`katex-multicolumn-array-spans`** | TypeScript / JS | [`KaTeX/KaTeX`](https://github.com/KaTeX/KaTeX) | Add `\multicolumn` span parsing and math layout rendering in KaTeX engine | 1800s (30m) |

*Total Concurrency 2 Wall Clock:* ~15–20 minutes.  
*Guaranteed Coverage:* Python compilation, Go systems engineering, TypeScript AST layout.

### 3.2 Tier 2: `SWE-Core` (Canonical Real Repository Suite, 8 Repositories)
The canonical suite used for publishing lifts and evaluating complete system releases:
1. `build-cython-ext` (Python/C: `SPOCKnots/pyknotid`)
2. `scc-bounded-memory-spilling` (Go: `boyter/scc`)
3. `katex-multicolumn-array-spans` (TypeScript: `KaTeX/KaTeX`)
4. `expr-try-catch-errors` (Go: `expr-lang/expr`)
5. `anko-typed-variable-bindings` (Go: `mattn/anko`)
6. `meriyah-explicit-resource-declarations` (TypeScript: `meriyah/meriyah`)
7. `python-statemachine-state-data-scoping` (Python: `fgmacedo/python-statemachine`)
8. `httpx-multipart-response-parsing` (Python: `encode/httpx`)

---

## 4. Formal Exclusions

The following tasks from `terminal-bench` are formally excluded from the core evaluation suite:
* `chess-best-move`: Visual chess board image puzzle; not a repository software engineering task.
* `regex-log`: Single-file Apache log regex script; not a repository software engineering task.
* `vulnerable-secret`: Single-file string grep/removal; not a repository software engineering task.
* `extract-elf`: Reverse engineering binary extraction script; not a software engineering task.
* `dna-insert`: String manipulation script; not a software engineering task.
* `openssl-selfsigned-cert`, `code-from-image`, `constraints-scheduling`, `gcode-to-text`, `kv-store-grpc`, `db-wal-recovery`, `git-leak-recovery`: Trivial scripts at ceiling (100% solve rate across all arms).
* `sqlite-db-truncate`, `largest-eigenval`, `log-summary-date-ranges`, `merge-diff-arc-agi-task`, `modernize-scientific-stack`, `multi-source-data-merger`, `polyglot-c-py`, `sanitize-git-repo`: Ungradeable (ship no sealed test suite).

---

## 5. Harness Changes

1. **`lab/benchmarks/task_sets.py`:**
   * Update `CANARY_TASKS` tuple to `("build-cython-ext", "scc-bounded-memory-spilling", "katex-multicolumn-array-spans")`.
   * Update `DISCRIMINATING_TASKS` and `CORE_TASKS` to reflect the 8 canonical repositories.
   * Update `EXCLUDED_TASKS` dictionary with explanatory rationales for all excluded tasks.
2. **`tests/test_benchmark_task_sets.py`:**
   * Update test assertions to verify the new tri-language canary and repository-first core membership.
3. **`docs/EVALUATION-PHILOSOPHY.md` & `AGENTS.md`:**
   * Document the repository-first benchmark mandate and the justification for excluding toy puzzles.
4. **`scripts/run_exp065_canary.sh` & `EXPERIMENTS.md`:**
   * Re-point `EXP-065` to execute the tri-language `SWE-Canary` comparing `superstate_daemon_dag` against `superstate_mcp`.
