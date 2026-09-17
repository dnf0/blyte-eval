# What the evaluation establishes

One place for what is true, so it stops being re-derived. Every claim names the experiment
behind it; `EXPERIMENTS.md` holds the full ledger, `CLAUDE.md` the working rules.

Last revised 2026-09-16.

---

## The short version

`superstate` makes a coding agent finish work it would otherwise abandon. The effect is real
and consistent in direction, the mechanism is understood, and it is **smaller than earlier
numbers in this repo claimed** — those were inflated by defects since fixed.

**Revised 2026-09-17 after EXP-053, which did not support the earlier claim.**

| | |
|---|---|
| **Effect** | **+3pp** per task, 95% CI **[-9, +15]** — the interval straddles zero |
| **Direction** | 20 tasks, 8 informative: superstate ahead on **4**, vanilla ahead on **4** |
| **Cost** | **$1.01 → $0.90 per solve** — superstate is now the cheaper arm |
| **Mechanism** | still visible: the handoff prompt, one turn; premature "done" falls 26% → 18% of runs |
| **Conclusion** | **the lift claim is not supported.** The mechanism is real; the outcome benefit is not demonstrated |

### The split that matters

| family | tasks | informative | superstate ahead | vanilla ahead | mean |
|---|---|---|---|---|---|
| terminal-bench | 13 | 5 | 3 | 2 | **+10pp** |
| datacurve | 7 | 3 | 1 | 2 | **-11pp** |

The earlier positive figure came almost entirely from terminal-bench. On datacurve — repository
tasks, and the tasks chosen *before* any superstate result existed, so immune to selection on
the outcome — superstate is behind.

**Hypothesis, not established:** the handoff prompt helps where "done" is a checkable artefact
the worker produces (write a file, emit a value) and hurts where the task requires exploring an
unfamiliar codebase, because *"HARD STOP UPON PASSING"* discourages the exploration such a task
needs. Testable, and worth testing before any further investment.

Read `scripts/effect.py` output, not a p-value. A p-value asks whether the effect differs from
*exactly* zero, which is not a live hypothesis — the mechanism is identified and visible in
telemetry — and mostly reports whether the corpus is large enough, which is a fact about the
benchmark. The decision is whether an agent should hand work over, and that turns on how much
gets converted and what it costs.

---

## 1. The effect is real, and its size is +19pp

Paired runs, same driver and task on both sides, prompt contracts off.

| | n | vanilla | superstate_mcp | gap |
|---|---|---|---|---|
| gradeable tasks | 48 | 65% | 83% | **+19pp** |

The unit of analysis is the **task**. Five repeats of one task are one observation, and so are
the same task's runs appearing in three different results files. Pooling correctly
(`scripts/effect.py`, pre-specified) gives, after EXP-053:

| | |
|---|---|
| independent gradeable tasks | 20 |
| ties — both arms identical, nearly all at 100% | **12** |
| **informative tasks** | **8** — superstate ahead on 4, vanilla on 4 |
| mean per-task difference | **+2.8pp**, 95% CI [-9, +15] |
| exact permutation test | p = 0.664 |

**The effect is not distinguishable from zero, and the point estimate has collapsed toward it**
as clean tasks were added. The figure moved five times — +29pp, +19pp, +15pp, then +3pp — and
every move but the last came from how runs were counted. The last came from new, unbiased data,
which is the only kind of move that should change a conclusion.

**The binding constraint is the number of independent discriminating tasks.** Ten of sixteen
are ceiling ties both arms always solve; more repeats of those cannot help. Only new
discriminating tasks can, and 8 of the 14 in the core set remain unmeasured — all of them
datacurve.

*Evidence: EXP-041, EXP-049, EXP-052 (partial).*

## 2. The mechanism is the handoff prompt, not the control loop

Four candidate explanations, all eliminated on telemetry:

* **Not more turns.** `turns=1` in 69 of 70 MCP runs on terminal-bench.
* **Not decomposition.** `milestones_planned=1` in 70 of 70.
* **Not more time.** On tasks it wins and vanilla loses, superstate uses 23% of its granted
  budget where vanilla uses 36%.
* **Not the gate.** The verification command was literally `true` for 22 of 30 tasks, and the
  margin holds there.

What remains is the text `superstate state prompt` emits: role framing, the goal restated, the
verification command, and five rules including *"HARD STOP UPON PASSING"*. Vanilla's dominant
failure mode is declaring done while wrong — 15 of 18 losses — at **$0.069 median spend against
the $0.187 it spends on tasks it solves**. It quits early and confidently. The handoff prompt
is what stops that.

**Consequence worth stating plainly:** `SUPERSTATE_EVAL_PROMPT_CONTRACTS=0` does not remove
prompt engineering from a run. It removes the *harness's* copy. Superstate's own prompt is a
behavioural contract shipped inside the Rust binary. So the supported claim is *"a structured
handoff beats a bare instruction"*, not *"state management beats no state management"*.

The control that would separate those — vanilla given the state prompt, no engine — has never
been run (EXP-050, registered, unrun).

## 3. The daemon is a legitimate default

| arm | solved | cost/run |
|---|---|---|
| `superstate_daemon` | 12/20 | **$0.25** |
| `superstate_mcp` | 12/20 | $0.33 |

Across 20 paired tasks they disagreed on **none**. Every deficit the daemon previously appeared
to have was a harness defect: a missing `--print-timeout` truncating every turn at agy's
5-minute default, and a missing gate lookup leaving it strictly gated while the MCP arm ran on
`true`.

**Caveat that matters:** this equivalence was measured on a task set where the iteration loop
never fired — 1 real worker invocation in 19 of 20 runs. The two arms differ precisely in *how
they respond to a gate failure*, so agreement in a regime with no gate failures is weak
evidence. Untested where it counts.

*Evidence: EXP-047.*

## 4. The loop does fire — on hard enough tasks

On `anko-typed-variable-bindings`: vanilla **0/2**, superstate_mcp **2/2**, with the gate
rejecting and the worker iterating to **3 turns**.

This had not happened once across 70 terminal-bench runs. The machinery is not inert by
design; terminal-bench was too easy to exercise it. One task only — suggestive, not
established.

*Evidence: EXP-052 (partial, 7 of 36 runs; stopped deliberately).*

## 5. The benchmark corpus is a third the size it appears

Of 30 tasks, **14 can carry signal**:

| | |
|---|---|
| 8 | ungradeable — ship no held-out `tests/` |
| 7 | at ceiling — every arm solves them every time |
| 1 | at floor — no arm has ever solved it |
| **14** | **usable** |

By family: **datacurve 8 of 9 usable, terminal-bench 6 of 21.** The tier-1 repository tasks
carry nearly all the discriminating power. Most of terminal-bench is a ceiling for this driver
— which is why both superstate arms scored 12/13 on its gradeable subset, and why no
architectural difference could show up there.

Use `paired_run.py --core` to decide where to spend a run. **Never for a headline claim:** the
set is selected on the dependent variable — membership reads how the arms performed — so it
inflates the gap by construction, +19pp becoming +31pp.

A published claim must come from every gradeable task with no outcome-based filtering, which is
what `scripts/effect.py` analyses. The cleanest new evidence comes from tasks holding **no
superstate result at all**, since they cannot have been chosen for their outcome — six of the
nine datacurve tasks qualify. Run a whole family, not a pick from within it, and register the
list before the run.

---

## Withdrawn

Thirteen ledger rows are `WITHDRAWN`. They are kept, because the withdrawal is the finding.

| claim | why it fell |
|---|---|
| lift is +29pp | 7 of 18 discordant pairs were self-graded |
| p=0.037 | run-level counting treated repeats as independent |
| gate precision 60%, "a rubber stamp" | 7 ungradeable tasks counted as gate errors; true figure is 92% |
| gate strength is the binding constraint | it isn't — the corpus is |
| daemon 2x cost premium | missing `--print-timeout` |
| daemon loses 5-0 on gated tasks | the MCP arm was running on `true` |
| in-loop MCP state tools are an anti-pattern | applies to `superstate_agent_mcp` only; the harness-driven arm is fine |

**The self-grading defect is the one to remember.** Seven tasks ship no sealed verifier, so the
harness ran `pytest tests/` inside the agent's own container — grading the agent against tests
it wrote. It was not symmetrical: **vanilla 0/7, superstate_mcp 7/7**, because superstate's
prompt asks the worker to build a verification command and the baseline gets no such
instruction. `extractor.py` now refuses to grade such a task.

---

## What would change the picture

* **The clean significance test.** 9 datacurve tasks, contracts off, 2 repeats. Would move
  8-2 to roughly 14-16 task-pairs — enough to reach p<0.05 if the effect is real at the
  apparent size, and enough to show it is not if it is not. *Only worth running if a claim is
  going to be published.*
* **EXP-050** — vanilla plus the state prompt, no engine. Sizes how much of the effect is the
  text. Changes the framing of the claim, not what gets built.
* **daemon vs mcp where the loop fires.** The one genuinely untested architectural question.

None of these change what to build next. The daemon works, it is cheaper, and the mechanism is
understood well enough to act on.
