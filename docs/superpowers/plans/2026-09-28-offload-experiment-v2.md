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

1. A plan-first mode in the runner: a planning run per task whose final message is the plan,
   stored with the results; `--plan-from <file>` to reuse a stored plan; the plan appended to the
   task text for both arms.
2. `--disallowedTools Agent ScheduleWakeup` for both claude arms (with a test).
3. Repeats and interleaving in `paired_run.py` (`--repeats 3`), and within-arm range in the
   comparison table.

## Cost (user's usage, needs approval)

2 planning runs + 12 arm runs on Sonnet, about $2–4 notional each: roughly $30–55 of usage, plus
about $5 of Gemini. A smaller first step: 1 task, 2 repeats per arm (1 + 4 runs, about $10–20),
then decide whether to run the rest.

## Limits, to state with the result

Two tasks; one orchestrator model; one implementer model; the plan comes from Sonnet, so a weak plan
limits both arms equally. It measures offloading implementation, which is the pattern blyte's docs
promote, not whether Claude should delegate unprompted.
