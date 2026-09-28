# Offload Experiment v2: Same Plan, Who Implements — Plan

**Status:** proposed 2026-09-28; needs the user's approval before any run (it spends Claude usage).

## Why v1 cannot answer its question

v1 ([plan](2026-09-27-offload-experiment.md)) gave both arms a raw issue and a cold repository:
Claude alone, against Claude planning and reviewing with blyte implementing. Two faults, found
in its first runs (2026-09-27/28):

1. **The design removes what offloading saves.** The claim is that the frontier model spends less
   when blyte implements. That holds only when implementing is a large share of the frontier
   model's work. On a cold task most of it is understanding the repository (5–6 minutes of
   thinking in both arms on `httpx`, before any action), which cannot be handed off: Claude needs
   it to write the task and to review it. So v1 measured the case where offloading helps least.
   Real use is the reverse: the plan exists, several tasks go to blyte, and Claude reviews.
   On `httpx`, Sonnet alone cost $2.44; Sonnet delegating cost $2.08 of Sonnet plus $0.90 of
   Gemini, and was slower, because writing precise tasks and reviewing them replaced a cheap
   implementation.
2. **One run per arm is inside the noise.** Haiku alone on `python-statemachine-state-data-scoping`
   passed 25, 30 and 32 of 72 target tests in three runs; Haiku + blyte, 43 and 63. On `httpx`,
   blyte alone, Sonnet alone and Sonnet + blyte all missed the same one test: that task does not
   separate harnesses.

What v1 did establish: delegation works end to end (Sonnet's two dispatches on `httpx` both passed
their gates first time), and it surfaced four setup faults, now fixed (#65, #66, #69).

## Design

Take out of both arms the part that cannot be offloaded, so the only difference is who writes the
code.

- **Plan, once per task, shared.** A planning run (Sonnet, container tools, no dispatch) reads the
  task and repository and writes a plan: the files to change, the behaviour, the tests to add, and
  a gate command. Its cost is reported separately and charged to neither arm. Both arms receive the
  same plan text with the task.
- **Arm A: Sonnet implements the plan** in Claude Code (container tools).
- **Arm B: Sonnet dispatches the plan to blyte** (`dispatch_blyte`, Gemini 3.8 Flash), reviews the
  result, and may dispatch follow-ups; it writes only one-line fixes itself.
- **Same conditions for both:** the operator's setup left out (#65); one appended prompt (#66);
  Claude Code's `Agent` and `ScheduleWakeup` tools disabled in both, because in v1 arm B waited
  about 120 s on its own background subagent, which is harness noise, not delegation.
- **Repeats:** 3 runs per arm per task, interleaved (A1 B1 A2 B2 A3 B3), so a difference can be
  compared with the spread inside each arm.
- **Tasks:** 2 implementation-heavy DeepSWE tasks where the target tests are not all-or-nothing:
  `python-statemachine-state-data-scoping` (72 target tests, already set up) and
  `scc-bounded-memory-spilling` (blyte alone passed it on Gemini).

## Measures and decision rule

Per run:
- frontier cost (Claude Code's `total_cost_usd`, notional under the CLI login) — the primary measure;
- implementer cost (blyte reports), total cost;
- target tests passed (a fraction, not only pass/fail), existing tests kept;
- wall time; dispatches and their outcomes.

Claim a frontier saving only if arm B's mean frontier cost is below arm A's by more than the larger
within-arm range on that task, with target tests not lower by more than their within-arm range.
Otherwise, report "no difference detected at this size". A null or negative result is reported too.

## Build tasks (no spend; A/B dispatched as usual)

> **For agentic workers:** implement exactly one task. Do NOT `git push`, open PRs, start any benchmark or paid run, or call any model API; commit locally only. Do not edit `FINDINGS.md`, `EXPERIMENTS.md`, `CLAUDE.md`/`AGENTS.md` or `results/`. Existing tests must pass unmodified. Checks: `make lint && make test`. Commit with `--no-gpg-sign` and the exact message given.

`paired_run.py --repeats` already interleaves arms (A1 B1 A2 B2), so no repeats work is needed.

### Task 1: plan-first mode

**Files:** `lab/engine/plan_first.py` (new), `scripts/paired_run.py`, `tests/test_plan_first.py` (new).

`lab/engine/plan_first.py`:

- `PLANNING_PROMPT: str`, exactly:
  `"This run only plans; it does not implement. Explore the repository as much as you need, but do not create, modify or delete any file. Your final message is the plan, and it goes to an engineer who has not seen the repository. Include: the files to change and what to change in each; the required behaviour, including every edge case the task describes; the tests to add or update; and one shell command, run from the repository root, that checks the work. Be precise and complete. Do not ask questions."`
- `PLAN_HEADER: str`, exactly: `"## Plan\n\nA plan for this task has already been written. Follow it."`
- `def planning_task(task: TaskSpec) -> TaskSpec`: `dataclasses.replace(task, instruction=f"{PLANNING_PROMPT}\n\n## Task\n\n{task.instruction}")`.
- `def with_plan(task: TaskSpec, plan: str) -> TaskSpec`: `dataclasses.replace(task, instruction=f"{task.instruction}\n\n{PLAN_HEADER}\n\n{plan.strip()}")`.
- `def final_response(logs_dir: Path) -> Optional[str]`: reads `logs_dir / "transcript.jsonl"` (one JSON object per line); returns the last non-empty `"response"` value, stripped, or `None` when the file is missing or has none.

`scripts/paired_run.py`, two new options:

- `--plan-only PATH`: requires exactly one task and exactly one `--harnesses` entry, else log an error and return 2. Runs `planning_task(task)` once (`--repeats` ignored), then reads `final_response(Path(tel.extra["logs_dir"]))`; if it is `None`, log an error and return 1; otherwise write it to PATH (creating parents) and log the path. The grader's verdict is irrelevant to a planning run and is not printed as a result table.
- `--plan-from PATH`: requires exactly one task, else error and return 2. Reads PATH and applies `with_plan` to the task before building jobs; the run then proceeds as usual.
- The two options are mutually exclusive (argparse group).

- [ ] **Step 1: tests.** `tests/test_plan_first.py`:

```python
"""Offload v2 gives both arms the same plan, written once by a planning run (2026-09-28)."""

import json
from pathlib import Path

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.plan_first import PLAN_HEADER, PLANNING_PROMPT, final_response, planning_task, with_plan


def _task(tmp_path: Path) -> TaskSpec:
    return TaskSpec(id="org/t", name="t", instruction="Add a feature.", docker_image="img", task_dir=tmp_path)


def test_planning_task_prefixes_the_prompt(tmp_path: Path) -> None:
    t = planning_task(_task(tmp_path))
    assert t.instruction == f"{PLANNING_PROMPT}\n\n## Task\n\nAdd a feature."
    assert "do not create, modify or delete any file" in PLANNING_PROMPT


def test_with_plan_appends_the_plan(tmp_path: Path) -> None:
    t = with_plan(_task(tmp_path), "  1. change x\n")
    assert t.instruction == f"Add a feature.\n\n{PLAN_HEADER}\n\n1. change x"


def test_final_response_is_the_last_non_empty_one(tmp_path: Path) -> None:
    lines = [{"turn": 1, "response": "first"}, {"turn": 2, "response": "  the plan  "}, {"turn": 3, "response": ""}]
    (tmp_path / "transcript.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    assert final_response(tmp_path) == "the plan"


def test_final_response_missing(tmp_path: Path) -> None:
    assert final_response(tmp_path) is None
```

- [ ] **Step 2:** run them; they fail (no module). **Step 3:** implement. **Step 4:** `make lint && make test`.
- [ ] **Step 5: Commit.** `git add lab/engine/plan_first.py scripts/paired_run.py tests/test_plan_first.py && git commit --no-gpg-sign -m "feat(eval): plan-first mode: one planning run, and the same plan for every arm"`

### Task 2: no subagents or wake-ups in the claude arms

**Files:** `lab/engine/drivers/claude_cli.py`, `tests/test_offload_harness.py`.

In `_build_command`, both arms always get one `--disallowedTools` flag followed by `Agent` and `ScheduleWakeup`, plus `Bash` when a container is active (keep the existing comment about Bash). Replace the current container-only `--disallowedTools Bash` so the flag appears exactly once. Add a module-level constant `DISALLOWED_TOOLS = ("Agent", "ScheduleWakeup")` with a comment: in the offload v1 run (2026-09-28) arm B spent about 120 s waiting on its own background Explore subagent through repeated ScheduleWakeup calls; that is harness noise, not delegation.

- [ ] **Step 1: test** (append to `tests/test_offload_harness.py`):

```python
@pytest.mark.parametrize("implementer", [None, "gemini-3.8-flash-high"])
def test_both_arms_disallow_subagents_and_wakeups(tmp_path: Path, implementer: str | None) -> None:
    stub = _make_stub(tmp_path, {"result": "ok", "total_cost_usd": 0.1})
    driver = ClaudeCliDriver(cli_path=str(stub), model="claude-sonnet-5", implementer_model=implementer)
    driver.run(task=_task(tmp_path), workspace_path=tmp_path, container=FakeContainer())
    argv = _argv(tmp_path)
    assert argv.count("--disallowedTools") == 1
    i = argv.index("--disallowedTools")
    assert argv[i + 1 : i + 4] == ["Agent", "ScheduleWakeup", "Bash"]
```

- [ ] **Step 2–4** as above. **Step 5: Commit.** `git add lab/engine/drivers/claude_cli.py tests/test_offload_harness.py && git commit --no-gpg-sign -m "feat(eval): the claude arms get no subagents or wake-ups"`

## Cost (user's usage, needs approval)

2 planning runs + 12 arm runs on Sonnet, about $2–4 notional each: roughly $30–55 of usage, plus
about $5 of Gemini. **Approved 2026-09-28: the smaller first step only**: 1 task
(`python-statemachine-state-data-scoping`), 1 planning run and 2 repeats per arm (5 Sonnet runs,
about $10–20), then the user decides whether to run the rest.

## Limits, to state with the result

Two tasks; one orchestrator model; one implementer model; the plan comes from Sonnet, so a weak plan
limits both arms equally. It measures offloading implementation, which is the pattern blyte's docs
promote, not whether Claude should delegate unprompted.

## First-step result (2026-09-28)

Task `python-statemachine-state-data-scoping`, Sonnet (Claude Code login, so Claude cost is
notional), Gemini 3.8 Flash for blyte, one shared plan (16 min, $2.50), 2 runs per arm, interleaved.
Results: `results/offload-v2-sonnet-20260928-1028/` (`plan.md`, `ab-1`, `c-1`, `ab-2`, `c-2`).

| arm | passed | Sonnet | Gemini | total | time |
|---|---|---|---|---|---|
| A: Sonnet + plan | 2/2 | $5.63, $5.49 | – | $5.56 mean | 17, 21 min |
| B: Sonnet + plan + blyte | 2/2 | $1.22, $2.42 | $2.56, $2.19 | $4.20 mean | 37, 60 min |
| C: pure Sonnet, no plan | 0/2 (69/72, 67/72 target tests) | $7.03, $5.27 | – | $6.15 mean | 38, 26 min |

- **B vs A (offloading implementation):** Sonnet 67% lower ($1.82 vs $5.56), total 24% lower,
  about 2.5× slower; the ranges do not overlap on any of the three. Quality equal (all passed).
- **End to end:** planning first decided quality (4/4 with the plan, 0/2 without). Sonnet spent:
  plan + B $4.32, pure Claude Code $6.15 (failed), plan + A $8.06. Pure Claude Code was cheapest in
  total ($6.15 vs plan + B $6.70) but did not complete the task.
- **Limits:** one task, two runs per arm; a very detailed plan (the best case for offloading);
  B has a review layer A lacks (B's quality includes Sonnet reviewing blyte's work: attributable to
  the workflow, not to blyte alone); some runs restored the repository's `AGENTS.md`, which the eval
  strips (model's choice, either arm: noise, not bias); the eval's MCP server runs dispatches one at a
  time, so dispatches Sonnet issued together queued (B1: about 7 minutes), which inflates B's time;
  B's gates each ended with the full suite (about 2 minutes each), which Sonnet chose.
- **Found along the way:** Gemini's implicit cache misses about 23% of blyte's turns (block-aware),
  and Gemini made one tool call per turn on nearly every turn; see blyte's
  `2026-09-28-gemini-cache-hits.md` and `2026-09-28-gemini-vertex.md`.
- **Next, if approved:** 2 tasks × 3 runs per arm (about $30–55 of Sonnet usage).

## blyte arms (2026-09-28): who writes the plan matters most

Same task, Gemini 3.8 Flash only (no Claude usage), 2 runs each, interleaved. Results: `results/offload-v3-blyte-20260928-1754/`.

| arm | passed | cost each | time |
|---|---|---|---|
| E: blyte alone, raw task | 2/2 | $4.10, $3.83 | 29, 31 min |
| D: blyte writes the plan ($1.03, 8 min), blyte implements | 0/2 (65/72, 68/72) | $2.91, $3.39 | 25, 20 min |
| F: Sonnet's plan, blyte implements, no Claude review | 2/2 | $1.80, $2.18 | 15, 17 min |

Against the Claude arms above: pure Sonnet 0/2; Sonnet's plan + Sonnet 2/2 at $5.56; Sonnet's plan +
blyte + Sonnet review (B) 2/2 at $1.82 Sonnet + $2.38 Gemini, 48 min.

- **A frontier plan with blyte implementing is the best combination:** F was the cheapest and
  fastest pass (about $2 of Gemini per implementation, 16 min), on top of a one-off plan.
- **A weak plan is worse than none:** blyte from its own plan failed both runs; blyte with no plan
  passed both.
- **Sonnet's review added no quality here:** B and F had the same result; B cost about twice as much
  and took three times as long. The gate did the checking.
- **blyte alone beat Sonnet alone on this task** (2/2 vs 0/2). In FrontierHarness it passed 5 of 9
  DeepSWE tasks, so this is task-dependent.
- **Limits:** one task, two runs per arm, an unusually detailed Sonnet plan.
