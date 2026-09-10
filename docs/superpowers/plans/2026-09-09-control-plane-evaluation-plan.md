# Control-Plane Evaluation — Plan

**Date:** 2026-09-09
**Status:** Stream 2 complete. Stream 1 blocked only on the planning prompt port.

## Why this exists

Six threads were live at once and were being worked reactively, whichever the last
run exposed. This separates them into two independent streams and fixes an order.

## What we are measuring

Superstate is a **control plane** for coding agents. The harness (Claude Code, agy)
is the **execution plane** — it owns the tools, runs commands, calls the model. The
control plane decomposes work into milestones, issues one bounded prompt per
milestone, gates advancement on verification, and carries state between turns.

The evaluation is therefore **paired**: the same harness, model and task run with
and without the layer. The headline is the delta — *control-plane lift* — not an
absolute pass rate. `vanilla` is the baseline arm; `superpowers` and `superstate`
are layers over it.

Because it is paired, effects identical across arms cancel, and absolute purity
(network isolation, sandboxing) is not required for internal validity. What is
required is **symmetry**: anything differing between arms other than the treatment
is a confound.

---

## The decision that separates the streams

When written, `agent-rules` (Python) implemented all 18 state commands while
`superstate` (Rust) implemented 5 and could not run the reference loop at all.
The decision was to evaluate Python first and build Rust separately, so neither
stream blocked the other.

**Superseded 2026-09-09:** Stream 2 is complete. Both engines now run the loop and
are verified equivalent by the differential suite, and the eval can select either
via `SuperstateAdapter(engine=...)`, recording which one ran in provenance. The
programme is therefore as originally intended: assess State Engine 3.0, then
replicate the result with the Rust engine — and both are now runnable.

---

## Stream 1 — Produce a credible measurement

### Task 1: Pin the engine explicitly and record it — DONE
- **Files:** `lab/engine/adapters/superstate.py`
- `find_superstate_binary()` uses `shutil.which("superstate")`, and that name on
  PATH is a shim into the agent-rules Python package. Runs labelled Rust have been
  driving Python.
- Resolve by explicit configuration (env var, then known paths), never by bare
  PATH lookup. Record the resolved path and implementation in provenance so every
  `run.json` states which engine produced it.

### Task 2: Drive the real state-engine loop — DONE
- **Files:** `lab/engine/adapters/superstate.py`
- The adapter uses 2 of 9 commands (`init`, `next`) and **hand-rolls the turnkey
  prompt in Python**. Generating that prompt is a core function of the control
  plane, so the arm currently measures a local string template, not superstate.
  No measurement taken before this task counts.
- Target loop, per `.agents/skills/stateful-execution/SKILL.md`:
  1. `state init --from-plan <plan>`
  2. `state ready` — DAG-unblocked tasks, replacing linear iteration
  3. `state prompt --with-graph` — the engine generates the turnkey prompt
  4. execute the turn
  5. `state note` — record discoveries into the epistemic ledger, so later
     milestones inherit earlier findings (this is what makes bounded context work)
  6. `state next --verify-cmd <cmd> --verify-git-clean`
- Keep `checkpoint`/`rollback` optional for now; add if runs prove flaky.

### Task 3: Port the reference planning prompt — NOT A DECISION AFTER ALL
- The reference already settles this: the state-engine arm *does* have a Phase 1
  planning turn (`generate_pre_assessment_prompt`), so option (c) below is what
  the reference does. What our adapter is missing is the content of that prompt.
- The reference takes a **pre-authored** plan; the state engine executes it. Our
  adapter invented a planning turn, which is why the agent was seen implementing
  during planning — the prompt conflated two phases the reference separates.
- Options:
  - **(a) All arms plan.** A shared planning phase precedes every arm. Symmetric,
    but adds a phase the baseline would not normally run.
  - **(b) Plan supplied per task.** Written once, given to every arm. Cleanest
    comparison; requires authoring 9 plans and risks leaking solution structure.
  - **(c) Only superstate plans, and the cost is counted.** Closest to real use;
    superstate pays a planning cost the baseline does not, which is arguably a
    true property of the control plane rather than a confound.
- Recommendation: **(c)**, with planning cost reported separately so it can be
  netted out.

### Task 4: Re-run and report
- One task × 3 arms to confirm the chain, then the 9 deep-swe tasks × 3 arms.
- Report `render_lift_report` (paired lift) plus tokens and wall-clock per solve.
- At n=9 one task is worth 11pp: treat the gained/lost task lists as the finding
  and the percentage as indicative only.

---

## Stream 2 — Rust parity — COMPLETE (2026-09-09)

All 16 state commands implemented; the differential suite passes against the
real Rust engine for the first time (it previously compared the Python
implementation with itself and passed vacuously).

Delivered: `ready`, `checkpoint`, `rollback`, `sync`, `exec`, `doctor`,
`validate`, `apply`, `resume`, `metrics`, `decompose`, plus `prompt --task`
/`--with-graph`, `status --json`, and `--from-plan`/`--out` aliases.

**Resolved by evidence, not decision:** the schema divergence stays. Rust stores a
structured `TaskSpec` and timestamped `LedgerEntry`; Python stores flat strings.
Rust's form carries `depends_on` in the state itself, so `state ready` works from
the state alone, while Python's must re-parse the plan every time. Rust's is
strictly more capable, so the parity suite compares *semantics* — which tasks, in
what order, with which notes — rather than representation.

**Still outstanding in Stream 2:** the roborev review gate. Roborev is an
out-of-band reviewer on a `post-commit` hook consuming zero chat tokens, with a
hard gate: no advancement until the commit is reviewed and findings fixed.
Architecturally a **third gate on `next`** alongside tests and git-clean — a way
to query review state for the current task's commit, plus
`--verify-review-clean`. The `superstate-review` crate already has `schema.rs`,
`prompt.rs` and `diff.rs` scaffolding.

---

## Parked, with reasons

- **Porting `agent_rules.eval`** — it is more complete (terminal-bench runner,
  leaderboard, scheduler), but `docs/eval-integrity-audit.md` found fabricated
  result records and arm-specific tuning. Worth taking the terminal-bench runner
  and `invariants.py` later; not the runners or result files.
- **terminal-bench integration** — unlocks the other 21 tasks and provides real
  sandboxing. Needed for statistical power, not for a first result.
- **Isolation work** (in-container agent, egress proxy) — built and available, but
  a paired comparison does not require it. The answer-key seal stays on as it is
  free.

---

## Harness defects found by running (all fixed)

None were catchable by the test suite; each was found by executing a real task.

| # | Defect | How it presented |
|---|---|---|
| 1 | Bridge/container context mismatch in gate commands | `exit 127` — loud |
| 2 | Hardcoded 600s planning cap killed runs with good plans | misleading message |
| 3 | Grading symptom reported before agent-side cause | plausible wrong diagnosis |
| 4 | Agent wrote `plan.md` outside the workspace; harness silently ran undecomposed | **plausible wrong result, no error** |
| 5 | Git-clean gate failed on the engine's own `.agent-state/`, so no milestone could ever pass | gate failure at milestone 1 |
| 6 | Stale release binary shadowed the fresh build, in two separate places | ran old code, reported the new engine |
| 7 | Relative state paths broke gate execution (three inline copies of one helper) | bare "No such file or directory" |

Defect 4 is the pattern to guard against: the arm degraded to baseline behaviour
while still being labelled superstate. `require_decomposition` now fails such runs
rather than recording them.


---

## Tomorrow — in order

1. **Port the reference planning prompt** (Stream 1, Task 3, now answered by the
   reference rather than open). `agent_rules.eval.adapters.state_engine.
   generate_pre_assessment_prompt` is the source: `<state-evaluation>` framing,
   `writing-plans` skill, 6-10 cohesive milestones, native test runner detection,
   the full plan format (Depends on / Files / Interfaces / Verification Command /
   Goal), and critically the directive *"This is a planning-only turn. Do NOT
   execute shell commands, do NOT run git, and do NOT explore files."* Ours omits
   that, which is why the agent was observed implementing during planning.
   Also port `decompose_instruction_to_fallback_plan` — a deterministic fallback
   beats the degenerate single milestone.

2. **Full dry run** — 9 tasks x 3 arms with a scripted driver. No model spend,
   but it pulls every image, builds every verifier and grades every task. This is
   the last place per-task surprises can hide.

3. **Concurrency check** — the runner's thread pool has never run two arms at
   once.

4. Then the real paired run, starting with
   `fastapi-deprecation-response-headers` (the whitepaper's own task).

## Standing lesson from today

Seven harness defects, every one found by running rather than by reading, none
catchable by the unit suite. Two were the *same mistake in a second place*
(relative path handling, stale binary resolution). When fixing something here,
check whether the pattern exists elsewhere before moving on.
