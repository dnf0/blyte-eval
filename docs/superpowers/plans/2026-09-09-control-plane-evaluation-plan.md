# Control-Plane Evaluation — Plan

**Date:** 2026-09-09
**Status:** Stream 1 in progress

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

`agent-rules` (Python) implements all 18 state commands and runs the reference
loop today. `superstate` (Rust) implements 5 and cannot run the reference loop at
all — no `ready`, `checkpoint`, `rollback`, `prompt --with-graph`, or `sync`.

**Decision: evaluate the Python engine now; build Rust parity separately.**
Neither stream blocks the other.

> **Open question for the owner:** if the intended subject is specifically the Rust
> engine, Stream 1 cannot produce a meaningful number until Stream 2 completes.
> This plan assumes the subject is the control-plane *architecture*, for which the
> Python engine is a faithful implementation.

---

## Stream 1 — Produce a credible measurement

### Task 1: Pin the engine explicitly and record it
- **Files:** `lab/engine/adapters/superstate.py`
- `find_superstate_binary()` uses `shutil.which("superstate")`, and that name on
  PATH is a shim into the agent-rules Python package. Runs labelled Rust have been
  driving Python.
- Resolve by explicit configuration (env var, then known paths), never by bare
  PATH lookup. Record the resolved path and implementation in provenance so every
  `run.json` states which engine produced it.

### Task 2: Drive the real state-engine loop
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

### Task 3: Decide where the plan comes from
- **Decision required from the owner. Blocks a fair comparison.**
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

## Stream 2 — Rust parity (independent, not blocking)

Gated by the differential suite, which is now honest and failing (it previously
compared the Python implementation with itself and passed vacuously).

1. **Schema divergence first** — Rust emits a `notes` key on `init` that Python
   does not, and the flags differ (`--state` vs `--out`/`--from-plan`). Every
   other command reads this state.
2. `ready` — DAG-unblocked computation
3. `checkpoint` / `rollback`
4. `prompt --with-graph`
5. `sync`
6. **Roborev gate** — roborev is an out-of-band reviewer on a `post-commit` hook
   that consumes zero chat tokens, with a hard gate: no advancement until the
   commit is reviewed and findings fixed. Architecturally this is a **third gate
   on `next`**, alongside tests and git-clean: a way to query review state for the
   current task's commit, plus `--verify-review-clean`.

Each command is done when its parity test passes against the Python engine.

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

Defect 4 is the pattern to guard against: the arm degraded to baseline behaviour
while still being labelled superstate. `require_decomposition` now fails such runs
rather than recording them.
