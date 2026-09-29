# Parallel Offload Comparison — Plan

**Status:** build task below (no spend); the runs need the user's approval (they spend Claude usage).

## Why (2026-09-29)

Offload v2 ([plan](2026-09-28-offload-experiment-v2.md)) found that Sonnet handing a shared plan
to blyte used 67% less Sonnet than Sonnet implementing it, but was about 2.5× slower. Part of that
was the eval: the dispatch tool ran a turn's parallel dispatches one after another. Since #83 each
dispatch works in its own copy and they run at the same time. The claim to test: with the work split
into independent parts, Sonnet + parallel blyte keeps the Sonnet saving and closes the time gap.

## Design

As v2, with a plan that splits the work, and non-Python tasks (a Python project installed editable
from `/app` would test `/app`'s code from a dispatch's copy; see #83).

- **Plan, once per task, shared** (`--plan-only` with the new `--plan-parallel`): the planner is also
  asked to put shared groundwork in part 1 and make the other parts independent, each with its own
  files and check. Both arms get the same plan.
- **Arm A: Sonnet implements the plan** in Claude Code (container tools; no subagents, as in v2).
- **Arm B: Sonnet dispatches the plan to blyte**, part 1 first, then the independent parts in
  parallel (the tool description invites it; nothing forces it), and reviews.
- **Tasks:** `scc-bounded-memory-spilling` (Go; blyte alone passed it on Gemini) and
  `katex-multicolumn-array-spans` (TypeScript). Both images are local.
- **Repeats:** 2 runs per arm per task, interleaved.

## Measures

Per run: Sonnet cost (notional under the CLI login) and wall time — the two primary measures;
Gemini cost; target tests passed; how many dispatches ran at the same time (from the dispatch
reports' timestamps); merge conflicts. Decision rule as v2: claim a difference only beyond the
larger within-arm range.

## Cost (needs approval)

Per task: 1 planning run + 4 arm runs on Sonnet, about $2–5 notional each, plus about $2–5 of
Gemini. First step: **scc only**, about $12–25 of Sonnet usage; katex after, if the first step is
worth extending.

## Build task (no spend; dispatched as usual)

> **For agentic workers:** Execution is delegated to headless `blyte` (with a sampled A/B against `agy`), one task per dispatch; Claude reviews each task before the next is sent. Steps use checkbox (`- [ ]`) syntax for tracking. Do NOT `git push` or open PRs; commit locally only. Do NOT start any benchmark or paid run, or call any model API. Do not edit `FINDINGS.md`, `EXPERIMENTS.md`, `CLAUDE.md`/`AGENTS.md`, `results/`, `traces/` or `data/`. Base branch `feat/parallel-offload`. Existing tests pass unmodified. Checks: `make lint && make test`. Commit with `--no-gpg-sign` and the exact message below.

### Task 1: `--plan-parallel`

**Files:** `lab/engine/plan_first.py`, `scripts/paired_run.py`, `tests/test_plan_first.py` (one test appended).

- [ ] **Step 1: test.** Append to `tests/test_plan_first.py`:

```python
def test_a_parallel_plan_asks_for_independent_parts(tmp_path: Path) -> None:
    from lab.engine.plan_first import PARALLEL_PLAN_PROMPT

    t = planning_task(_task(tmp_path), parallel=True)
    assert t.instruction == f"{PLANNING_PROMPT} {PARALLEL_PLAN_PROMPT}\n\n## Task\n\nAdd a feature."
    assert planning_task(_task(tmp_path)).instruction == f"{PLANNING_PROMPT}\n\n## Task\n\nAdd a feature."
```

  Run: `.venv/bin/python -m pytest tests/test_plan_first.py -q`. Expected: the new test fails (no `PARALLEL_PLAN_PROMPT`).

- [ ] **Step 2: `lab/engine/plan_first.py`.** Add after `PLANNING_PROMPT`:

```python
# The parallel offload comparison (2026-09-29): a plan whose parts can be dispatched at once.
PARALLEL_PLAN_PROMPT: str = (
    "Divide the work into numbered parts. Put everything the other parts depend on (shared types, "
    "interfaces, the core logic) in part 1. Make the remaining parts independent of one another: "
    "each changes different files and can be implemented and checked on its own, at the same time "
    "as the others, once part 1 is done. For each part give its files, its behaviour and its own "
    "check command."
)
```

  and replace `planning_task` with:

```python
def planning_task(task: TaskSpec, parallel: bool = False) -> TaskSpec:
    prompt = f"{PLANNING_PROMPT} {PARALLEL_PLAN_PROMPT}" if parallel else PLANNING_PROMPT
    return dataclasses.replace(task, instruction=f"{prompt}\n\n## Task\n\n{task.instruction}")
```

- [ ] **Step 3: `scripts/paired_run.py`.** After the `plan_group` block (after the `--plan-from`
  argument), add:

```python
    ap.add_argument(
        "--plan-parallel",
        action="store_true",
        help="With --plan-only: ask the planner for a shared first part and independent parts that can be dispatched at once",
    )
```

  and change `ptask = planning_task(tasks[0])` to `ptask = planning_task(tasks[0], parallel=args.plan_parallel)`.

- [ ] **Step 4: run the checks and commit.** Run: `make lint && make test`. Expected: both pass.

```bash
git add lab/engine/plan_first.py scripts/paired_run.py tests/test_plan_first.py
git commit --no-gpg-sign -m "feat(eval): --plan-parallel asks the planner for independent parts"
```

## Result (2026-09-29), scc only

**Changed from the design (user, 2026-09-29):** no arm A (Sonnet implements) runs; instead arm B
with parallel dispatch against arm B with serial dispatch (eval `ac2ae9f`, before #83). Then, after
the first four runs showed no overlap, two more with start-then-wait dispatches (#85). Same shared
plan (Sonnet, 4 min, $0.32; 3 parts, part 1 the core). Results:
`results/parallel-offload-scc-bounded-memory-spilling-20260929-1340/`.

| run | dispatch | how Sonnet split it | target tests | Gemini | Sonnet | wall |
|---|---|---|---|---|---|---|
| ser-1 | serial (old eval) | 1 dispatch | 28/31 | $1.70 | $0.16 | 16 min |
| ser-2 | serial (old eval) | 1 dispatch | 28/31 | $1.64 | $0.16 | 15 min |
| par-1 | parallel (#83) | 2, one after the other | **31/31 (passed)** | $2.21 | $0.16 | 21 min |
| par-2 | parallel (#83) | 3, one after the other | 28/31 | $4.14 | $0.16 | 33 min |
| par-3 | start-then-wait (#85) | 3: part 1, then parts 2 and 3 **at once** | 30/31 | $4.25 | $0.23 | 36 min |
| par-4 | start-then-wait (#85) | 1 dispatch | 28/31 | $1.86 | $0.12 | 14 min |

- **Parallelism now works end to end:** in par-3, parts 2 and 3 started together (15:53:10) and
  both applied without a conflict. Before #85, Claude Code ran the MCP server's calls one after
  another, so #83's server-side parallelism was never used (par-2: dispatch 3 started 2 s after 2).
- **On this task, one dispatch was fastest and cheapest** (14–16 min, $1.6–1.9 of Gemini). Splitting
  cost 30–160% more Gemini and was slower even with overlap: each dispatch re-reads the code, and
  the overlap saved only the shorter part (par-3: part 3 took 6 min beside part 2's 18).
- **Splitting may help quality** (31, 28, 30 target tests against 28, 28, 28 for one dispatch; the
  only pass was split) — three runs each, so a hint, not a result.
- **Sonnet's cost is small in every run** ($0.12–0.23): with a full plan, blyte does the work.
- **Limits:** one task, whose parts are uneven and coupled through part 1; Sonnet chose the split
  itself (twice one dispatch, four times several), so the arms differ in splitting as well as in
  parallelism. A task with several independent parts of similar size is the fair test.

## Result (2026-09-29), katex

Two experiments on `katex-multicolumn-array-spans` (TypeScript), run one after the other.
blyte `b965bb1`, eval `14e25a3`. The user's measure is Claude usage (Gemini is an acceptable cost).

### 1. The Sonnet saving, v2 on a second task

Results: `results/offload-v2-katex-20260929-1654/`. One shared plan (3 min, $0.30).

| run | who implements | target tests | Sonnet | Gemini | total | wall |
|---|---|---|---|---|---|---|
| a-1 | Sonnet | 94/94 (passed) | $0.96 | – | $0.96 | 8 min |
| b-1 | Sonnet hands off to blyte | 94/94 (passed) | $0.12 | $2.05 | $2.17 | 21 min |
| a-2 | Sonnet | 92/94 | $0.84 | – | $0.84 | 6 min |
| b-2 | Sonnet hands off to blyte | 94/94 (passed) | $0.13 | $3.31 | $3.44 | 27 min |

- **The Claude saving holds: 86% less Sonnet** ($0.13 against $0.90, means), beyond the within-arm
  ranges. v2's task: 67% less.
- **Quality:** blyte's arm passed 2/2, Sonnet's 1/2 (two target tests short). Small numbers.
- **Total cost and time go the other way on this task:** Sonnet alone was cheap and quick here, so
  the Gemini spend made the hand-off arm about 3× dearer in total and about 3.5× slower. On v2's
  task, where Sonnet implementing cost $5.56, the hand-off was also cheaper in total.

### 2. A fair parallel test: not achieved

Results: `results/parallel-fair-katex-20260929-1654/`. A shared parallel plan (3 parts: the core;
unit tests; styles and docs), with a closing "How to dispatch" section: part 1, then the others at
once (PAR), or the parts one after another (SEQ).

| run | told to | what Sonnet did | target tests | Sonnet | Gemini | wall |
|---|---|---|---|---|---|---|
| par-1 | parts 2–3 at once | 3 dispatches; parts 2 and 3 **ran together** (18:24:28) | 94/94 (passed) | $0.17 | $4.42 | 31 min |
| seq-1 | one after another | 1 dispatch | 92/94 | $0.12 | $2.49 | 21 min |
| par-2 | parts 2–3 at once | 1 dispatch (ran out of budget) | 92/94 | $0.16 | $3.15 | 25 min |
| seq-2 | one after another | 1 dispatch | 94/94 (passed) | $0.13 | $3.02 | 22 min |

- **Sonnet ignored the dispatch instructions in 3 of 4 runs** and sent the whole plan as one
  dispatch, so the two arms are not comparable; only par-1 used the split.
- **The parts were not of similar size:** part 1 (the core) took 15 min, parts 2 and 3 about 7 min
  each. Overlapping them saved about 6 minutes, less than the extra dispatches cost.
- **As on scc, one dispatch was quicker and cheaper** for one feature (21–25 min, $2.5–3.2 of Gemini,
  against par-1's 31 min and $4.42), with the same pass rate here.

### What the two tasks together say

- Handing off to blyte cuts Claude usage by two thirds to 86% on both tasks, with equal or better
  quality. That is the saving the user is after.
- Within one feature, splitting into parallel dispatches does not pay: the parts are rarely
  independent and of similar size, and each dispatch re-reads the code. Parallelism pays across
  separate tasks (the dispatch ledger: about 2× wall time with several at once).
- A fair within-feature parallel test would need a task built of several independent parts of
  similar size; none of the benchmark tasks is. Not worth building for now.
