# Working in superstate-eval

**[FINDINGS.md](FINDINGS.md) says what the evaluation establishes.** Read it before forming a
view, quoting a number, or proposing a run -- it exists because the same conclusions kept
being re-derived and re-litigated, including by me.

Two rules that follow from how this project has actually gone wrong:

* **Verify what produced a number before reporting it.** Every retraction here came from
  reading a result without checking what generated it: 40 runs that were 20, precision 60%
  that was 92%, +29pp that was +19pp.
* **Do not propose a run without naming the decision that changes on its outcome.** Chasing a
  p-value is not a decision.

## Terminology — use these exact words

Two different things are both called "contract" in conversation. They are not related, and
conflating them has produced wrong conclusions.

| Term | Means | In code |
|---|---|---|
| **verification command** | the shell command whose exit code decides whether a milestone is complete | `verify_cmd`, `TaskSpec.verification_cmd`, `GATE_FIXTURES` |
| **gated / ungated** | whether that command *can* fail. `true`, `:`, `exit 0` are **ungated** | `is_vacuous_gate()` (Rust), `NOOP_GATE_RE` |
| **prompt contract** | the injected behavioural rules ("zero global exploration", "hard stop upon passing") | `TARGETED_EXECUTION_CONTRACT`, `prompt_contracts.py` |
| **sealed grader** | the held-out verifier at container-root `/tests/` that decides pass/fail | `extractor.py` |

Never say "contract" unqualified. Say *verification command* or *prompt contract*.

A package's own suite at `/app/<pkg>/tests/` is **not** the sealed grader. Match the grader
by path position (`references_sealed_grader()`), never by substring.

### Gated vs ungated — why it decides what a run measures

A verification command is **ungated** when it cannot fail. `true`, `:`, `exit 0`, `/bin/true`
and the empty string all pass unconditionally, so they certify nothing.

This is not an edge case: it is the harness's *default*. Most benchmark tasks ship their real
verifier sealed at `/tests/`, which the agent must never run — it is the answer key. The
loader therefore strips it and falls back to `true`, so unless a task has an entry in
`GATE_FIXTURES` it runs **ungated**.

Ungating changes what each arm is even doing:

| Arm | Given an ungated verification command |
|---|---|
| `superstate_daemon` | iteration is **gate-driven**: the gate passes on turn one, the state machine records completion, and it commits and merges. Without the ungated turn floor it exits after a single turn and behaves like `vanilla` |
| `superstate_mcp` | iteration is **turn-driven** (`max_turns_per_milestone`, gate checked *after* the agent concludes), so it keeps working regardless and degrades gracefully |
| `vanilla` | unaffected — it has no gate either way |

Measured consequences, all from real runs:

- Ungated, the daemon scored 10/20 against `superstate_mcp`'s 14/20 **while running faster
  than `vanilla`** — not working harder, exiting on a gate that could not say no.
- 20 of 24 ungated daemon runs recorded two turn-floor notes and **zero** verify-fail: turns
  spent solely because nothing could refuse. On gated tasks the same daemon recorded genuine
  verify-fail/retry cycles.
- Of 12 ungated self-reported completions, **5 were wrong** and had already been committed and
  merged. Gated, 3 of 3 were correct.

So: **a result from ungated tasks measures the fallback, not the mechanism.** Before comparing
arms, check how many of the tasks are gated — `agent_gate_for(task_name)` — and say so in the
write-up. All 20 terminal-bench tasks are now gated; the DataCurve/tier1 set is only partly so.

## Three different things get called "the agent"

Say which one. They sit at different layers and confusing them makes a sentence unfalsifiable.

| Layer | What it is | Where |
|---|---|---|
| **orchestrator** | whoever decides the work and states the verification command — a human, or an agent in a chat session. Never measured by the benchmark; it is the thing being *replaced* by an arm | outside the harness |
| **arm** | the execution model under test: how turns are structured, when the gate is checked, whether state is external. This is what a benchmark number describes | `lab/engine/adapters/` |
| **driver** (worker) | the coding agent that actually edits files. Addressed in the turnkey prompt as *"You are an Implementer Subagent"*. Interchangeable — the arm is the treatment, the driver is held constant | `lab/engine/drivers/` |

An arm's score is **not** a statement about the driver. `superstate_mcp` scoring 70% against
`vanilla`'s 45% means the execution model differs, with the same driver on both sides.

### Drivers

| Driver | Runtime | Default model | Notes |
|---|---|---|---|
| `AgyCliDriver` | Google Antigravity (`agy`) | `gemini-3.8-flash-high` | used for nearly every run here. Effort suffixes `-low/-medium/-high/-xhigh/-max` change how many tokens are spent, not price per token |
| `ClaudeCliDriver` | Claude Code (`claude`) | `claude-opus-5` | |
| `InContainerClaudeDriver` | Claude, executing inside the sandbox | — | |

Pick the effort level deliberately. `-low` with a clamped budget floored every arm at 1/5 on
a task set where `-high` discriminated — fast, and measuring nothing.

Both CLI drivers receive `CONTAINER_GUIDANCE_TEMPLATE`, which tells the worker that
dependencies live in the sandbox and to reach them via `./run-in-container`. The daemon spawns
its worker itself, so that guidance has to be re-supplied through the wrapper — when it was
missing, the worker edited the host while its own gate ran inside the container.

## `superstate_mcp` is not superstate

The arm named `superstate_mcp` runs `zero_turn_planning=True`: **one milestone, one gate, no
dependency graph**. It is the plan-free fast path added on 2026-09-11 for *atomic* tasks, whose
own design spec says multi-milestone planning is **not** being discarded and remains for complex
work. That boundary was never enforced, and 253 of 309 recorded runs used the fast path.

So a result from `superstate_mcp` describes `init` + `prompt` + one shell gate. It is not a
measurement of the control plane, and must not be reported as one.

The arm that runs the design is **`superstate_mcp_planned`** (`zero_turn_planning=False`): the
driver writes a plan, milestones are parsed with their dependencies and file lists, each carries
its own verification command, and the adapter advances via `state_ready` — the DAG. It had never
been run until EXP-055.

**Before quoting any superstate number, check which of the two produced it.** See
`superstate/docs/SYSTEM-REVIEW.md` for how the two diverged.

## Arms — check the name before comparing anything

The benchmark's Condition labels map to specific arm names. Getting this wrong invalidates
a comparison silently, and has.

| Arm | Condition | Loop driven by | Turns |
|---|---|---|---|
| `vanilla` | Baseline 1 | nothing — single shot | conversational |
| `superpowers` | Baseline 2 | nothing | conversational |
| `superstate_agent_mcp` | **Condition A** | the *agent*, in-loop via JSON-RPC | conversational *by design* |
| `superstate_mcp` | **Condition B** — the arm that scored 76% | the *harness*, over stdio MCP | stateless, **single milestone, no graph** |
| `superstate_mcp_planned` | the design: decomposed DAG, per-milestone gates | the *harness*, over stdio MCP | stateless, **multi-milestone** |
| `superstate_daemon` | (post-ADR-0002) | the Rust `DaemonRunner`, detached | stateless |
| `superstate_solo` | alias of `superstate_rust_inplace`/`_fast` | Python turn loop over the CLI | stateless |

`superstate_solo` and `superstate_daemon` are **not** Condition B. Only `superstate_mcp` is.

Condition B arms must never thread `conversation_id` — zero-turn injection is the mechanism
the result rests on. See `lab/engine/condition_b.py`.

## Arm input parity — the single most common source of false findings

**Five times** an apparent architectural difference between arms turned out to be one arm
receiving something another did not:

| What differed | What it looked like |
|---|---|
| `--model` not pinned | the daemon "performing worse" — it was running a different model |
| `--output-format json` missing | the daemon "costing $0.00" — telemetry was never parsed |
| container guidance missing | the daemon "failing build tasks" — its worker edited the host while its gate ran in the container |
| `--print-timeout` missing | the daemon "unable to do long tasks" — every turn truncated at agy's 5-minute default |
| `agent_gate_for` missing | the daemon "losing 5-0" — it had a strict gate while `superstate_mcp` ran on `true` |

Every one produced a plausible finding that dissolved on inspection, and each cost a run.

**Before trusting any arm-vs-arm number, diff what the arms actually receive.**
`tests/test_arm_input_parity.py` enforces the known cases; it will not catch a new one.

The daemon is the recurring offender because it spawns its own worker and therefore bypasses
`AgyCliDriver`, which does this work for every other arm. Any new flag or prompt addition
there must be mirrored into `_write_driver_wrapper`.

## Verify before asserting

Every wrong claim in this repo's history came from inferring instead of checking. All are
one command.

- **A claim about a past run**: read the code *at that commit* (`git show <ref>:<path>`), not
  the current file. Several "confounds" found on 2026-09-14/15 were introduced those same days.
- **A flag's meaning**: read `--help`. `--timeout` on `state daemon` bounds each verification
  attempt, not the daemon's lifetime.
- **An arm's identity**: check the arm name against the report, not from memory.
- **A result**: read the results JSON, don't recall it.

## Running evaluations

- **Never request `--concurrency` above the governor's calculated max.** The surplus worker
  starves, times out at 300s, and is recorded as a *task* failure. Check the
  `Calculated concurrency:` log line and stay at or below it.
- **Clear orphan containers and `/tmp/superstate_eval_runs/*` between runs.** Stale workspaces
  consumed 51 GB and throttled the disk governor to 2 workers, producing spurious failures.
- **Watch for `Cost=$0.00` with a wall clock near the budget** — that is a driver turn that hit
  its timeout and lost its usage telemetry, not a cheap run. Raise `--budget-sec`.
- **`sqlite-db-truncate` is unmeasurable** — no verifier ships with it, so its grader exits 127
  for every arm. See `UNMEASURABLE_TASKS`.

## Switches (all default OFF)

| Env var | Effect |
|---|---|
| `SUPERSTATE_EVAL_PROMPT_CONTRACTS` | inject arm-specific prompt contracts (superstate arms only) |
| `SUPERSTATE_EVAL_GENERIC_RULES` | inject the portable discipline rules into baseline arms |
| `SUPERSTATE_EVAL_DERIVE_GATES` | let the daemon author its own verification command |

Defaults measure state management alone. Turning the first on makes any arm-vs-arm
comparison confounded, because baselines have no equivalent.

## Python environment

**Run everything through `.venv/bin/python`, never a bare `python3`.** The shell's `python3`
is a pyenv shim with a partial set of the project's dependencies, so `python3 -m pytest tests/`
aborts at collection on `ModuleNotFoundError: deepdiff` and silently omits
`tests/test_differential.py`. The suite is **297 tests**; a run reporting 292 was taken on the
wrong interpreter.

```
.venv/bin/python -m pytest tests/ -q       # 297 passed
```

## Shell

`paired_run.py` invocations belong in a `#!/bin/bash` script. The interactive shell is zsh,
which does **not** word-split unquoted variables, so `--tasks $TASKS` passes the whole list
as one filename.

## Run `--canary` or `--core`, not toy puzzles or the whole corpus

The 30-task corpus holds **9 genuine software engineering repositories** (`SWE_CORE_TASKS`). The rest cannot move an arm-vs-arm result or fail to test repository software engineering:

| Count | Classification | Detail |
|---|---|---|
| **9** | **Real Repositories (`SWE_CORE_TASKS`)** | 8 DataCurve open-source codebases + `build-cython-ext` (Python/C, Go, TypeScript) |
| 5 | Toy command-line puzzles | Excluded: single-file puzzles (`chess-best-move`, `regex-log`, `vulnerable-secret`, `extract-elf`, `dna-insert`) that do not test repository engineering |
| 7 | At ceiling | Excluded: every arm solves them every time (`openssl-selfsigned-cert` is 22/22 for vanilla alone) |
| 1 | At floor | Excluded: no arm has ever solved it (`fastapi-deprecation-response-headers`) |
| 8 | Ungradeable | Excluded: ship no held-out `tests/` directory (e.g. `sqlite-db-truncate`) |

Running the full corpus spends over half the budget on tasks that cannot teach anything, and dilutes the reported pass rate.

### Rapid Iteration: `SWE-Canary` (`--canary`)
For fast developer turns (~15–20 min total), run the tri-language repository canary:
```bash
scripts/run_canary.sh
# runs: build-cython-ext (Python/C), scc-bounded-memory-spilling (Go), katex-multicolumn-array-spans (TS)
```

### Full Benchmark: `SWE-Core` (`--core`)
For full releases and formal evaluation, run the 9 repository tasks:
```bash
scripts/paired_run.py --core ...      # the 9 canonical software repositories
```

**Why Toy Puzzles are Excluded:**
Superstate is an autonomous software engineering control plane (DAG state machine, AST impact slicing, scoped git rollback, TDD). Forcing Superstate to author pytest suites and execute git checkpoints for a visual chess puzzle (`chess-best-move`) or a log filter is a category error that adds ceremonial overhead. Real repository engineering is where Superstate's mechanical primitives provide measurable lift.

See [docs/TASK-QUALIFICATION-RUBRIC.md](docs/TASK-QUALIFICATION-RUBRIC.md) for the 5 mandatory qualification requirements (multi-file repository, sealed grader, multi-turn complexity, build telemetry, discriminative headroom).

## A task with no sealed grader cannot be scored

Seven terminal-bench tasks ship no `tests/` directory. `task_loader` falls back to
`pytest tests/`, and the harness used to run that **inside the agent's own container** --
grading the agent against tests it wrote itself.

It was not symmetrical. Over 55 paired runs those tasks went **vanilla 0/7,
`superstate_mcp` 7/7**, because superstate's handoff prompt asks the worker to produce and
run a verification command while the baseline gets no such instruction. They supplied 7 of
the 18 discordant pairs behind the headline lift, which is +18pp once they are removed, not
+29pp. Where the agent wrote no `tests/`, the same fallback exited 127 and scored zero for
every arm -- spurious passes and spurious failures from one defect.

`extractor.py` now records such a task `UNMEASURABLE` instead of grading it, and
`test_tasks_without_a_sealed_grader_are_marked_unmeasurable` fails if one is missing from
`UNMEASURABLE_TASKS`. **Before quoting any pass rate, check how many of its tasks were
gradeable** -- `TaskSpec.tests_dir is None` means no.

## The eval exercises a fraction of superstate

`superstate --help` lists checkpointing, rollback, replanning (`state sync`), decomposition
(`state decompose`) and adversarial review (`review`). **None of those have ever run** in 309
recorded runs. The adapters call `init`, `prompt`, `next`, `ready`, `exec`, `status`, `note`,
`doctor`, `daemon` and `handoff`.

Before attributing a result to "superstate", check which verbs the arm actually invokes. Every
number in FINDINGS.md describes `init` + `prompt` + a gate over a single-node graph.

`review` is the notable omission: a determination of "done" that inspects the diff rather than
running a command someone wrote before the work existed. That is a different mechanism from
everything measured so far, and it is unevaluated.

## A bad gate is worse than no gate

Superstate replaces the agent's own judgement about when it is done with the gate's. That is a
gain only when the gate is the better judge. Measured 2026-09-17, the sign of the effect tracks
gate precision:

| family | gate precision | effect vs vanilla |
|---|---|---|
| terminal-bench | 92% | **+10pp** |
| datacurve | 17% | **-11pp** |

At 17% the gate says "done" on work the sealed grader rejects, superstate stops, and vanilla --
which has no gate to mislead it -- keeps working and wins. Superstate did ~20% less work on
every effort metric.

So **audit a family's gates before running it**, with `scripts/gate_precision.py` on any prior
run and `scripts/validate_gates.py` for discrimination. A gate that is merely non-vacuous is not
enough: these all fail on a pristine container and still only reach 17%, because they assert
necessary conditions rather than sufficient ones.

## Gate precision — read it after every run

The gate tells the worker it is done. When it passes on work the sealed grader rejects, the
worker stops early and the retry loop never engages, so *no* architectural difference between
arms can show up. EXP-047 measured this: the gate ran 20 times and **passed 20 times**. Of the 8 it got
wrong, 7 were tasks with no sealed grader at all (see above), so true precision on gradeable
tasks was **92%, not 60%** -- the gate is not a rubber stamp. Count only gradeable tasks
when reading this metric, or a corpus defect will look like a gate defect.

```
scripts/gate_precision.py /tmp/superstate_eval_runs/<stamp> results/<run>.json
scripts/validate_gates.py [task ...]    # every gate must FAIL on a pristine container
```

Both arms now write a `MilestoneRecord` carrying the verdict, so precision is computable for
each. The daemon did not until 2026-09-16, and its empty `gates_failed` meant either "gate
passed" or "gate never ran" with no way to tell them apart -- treat any daemon run from before
that date as unscoreable rather than as a pass.

A gate must assert the **sufficient** condition, not a necessary one. Eight gates checked that
an artefact existed and concluded the task was done; `sanitize-git-repo` passed when the agent
deleted the file it was meant to sanitise.

## Evaluation Philosophy: Autonomous TDD vs. Answer-Key Cheating

See [docs/EVALUATION-PHILOSOPHY.md](docs/EVALUATION-PHILOSOPHY.md) for the full architectural manifesto.

Three non-negotiable rules govern all evaluation tasks in this repository:

1. **Never leak the maintainer's reproduction test (Anti-Cheating Invariant).**
   Pre-seeding the maintainer's reproduction test into the repository up front is **cheating** in SWE benchmarks. It leaks the exact function names, argument shapes, and assertion values, transforming an open-ended diagnosis into a narrow test-passing game. The maintainer's test suite (`test_patch`) remains strictly sealed at `/tests/` and executes only during post-run grading.

2. **Never use hand-authored synthetic gate fixtures (Ban on `GATE_FIXTURES`).**
   Synthetic 10-line string fixtures (`cat <<'EOF' | python -`) are deprecated. They caused the 17% DataCurve gate precision collapse. In `httpx`, a hand-authored fixture checked basic multipart parsing and exited 0, causing the daemon to halt after passing 1,393 of 1,394 tests, only to fail the sealed grader on a single tab-folding edge case. Synthetic fixtures measure the human author's oversights, not the agent's capability.

3. **Autonomous TDD is the canonical mechanism for bug resolution.**
   When a repository is clean on Turn 0, the daemon executes via a deterministic 2-node DAG:
   - **Milestone 1 (`tdd-reproduction-test`):** The agent reads the raw issue description and authors its own reproduction test in `tests/test_reproduce_issue.py`. The gate mechanically verifies that the test compiles and **fails (asserting RED)** against the unfixed code. Upon passing, a git checkpoint commit is created.
   - **Milestone 2 (`fix-implementation`):** The agent implements the fix. The gate requires `pytest tests/test_reproduce_issue.py && pytest tests/` to exit 0 (GREEN). AST Test Impact Slicing accelerates intermediate turns, Tool Output Shunting bounds log size, and Scoped Rollback cleanly reverts broken edits to Milestone 1 if a turn fails.
   - **Post-Run Grader:** The sealed grader executes at `/tests/` to compute the official benchmark score.

## Before running anything: check the ledger

`EXPERIMENTS.md` holds one row per evaluation run — the question, the arms, the switches,
the results file and the verdict. **Query it before proposing a run.**

```
scripts/experiments.py list <query>   # has this been run?
scripts/experiments.py check          # orphans, ghosts, truncated files
scripts/experiments.py scan           # tallies straight from results/, ledger ignored
```

Register the row *before* the run starts, not after. Three things this exists to stop, each
of which has already happened:

- **A run proposed that had already happened.** Answering "have we run this?" took ten
  minutes of grepping git history and 59 result files.
- **A run believed to have happened that had not.** `vanilla + state_prompt` was thought to be
  EXP-039 — but EXP-039 injected `GENERIC_EXECUTION_RULES`, a different text with no content
  in common. `vanilla.py` has never referenced `state_prompt` in any commit.
- **A truncated results file read as a finished one.** `paired_run.py` saves incrementally, so
  a killed run leaves a plausible partial file. A 31-of-40-row snapshot reached main showing
  10/16 vs 15/15 for a comparison whose real outcome was 12/20 vs 12/20. `check` compares row
  count against the declared `n`.

**Never delete a `WITHDRAWN` row.** Thirteen rows are withdrawn, nine of them to one cause --
the missing `--print-timeout`. The withdrawal is the finding, and deleting the row invites
rediscovery.

### Do not run `vanilla` by default

It is 26% of all spend ever recorded ($90 of $341), and it does less diagnostic work than was
once claimed: of the 13 withdrawn rows, **2** included a vanilla arm. The rest were caught by
reading code. A floor or ceiling effect is visible in any arm without a baseline.

Run it only when (1) the task set is new, (2) the driver or model changed, or (3) a lift is
about to be claimed. Its unique contribution is showing a treatment is *worse than nothing* --
EXP-020, where vanilla beat `superstate_rust` and exposed the prompt-contract confound.

Gate-strength and daemon-vs-mcp questions are settled within the superstate arms; `vanilla` has
no gate and contributes nothing to either. The lift is banked at EXP-049 (67.5% vs 45%, n=40,
p=0.037) and does not need re-measuring.
