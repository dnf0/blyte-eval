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

### Why: superstate swaps the agent's stopping judgement for the gate's

The sign of the effect tracks **gate precision** — how often a passing gate agrees with the
sealed grader:

| family | gate precision | effect |
|---|---|---|
| terminal-bench | **92%** (12 of 13) | **+10pp** |
| datacurve | **17%** (2 of 12) | **-11pp** |

On datacurve the gate certifies work the grader rejects in 9 of 11 runs per arm. Superstate
obeys *"HARD STOP UPON PASSING"* and stops; vanilla, having no gate, carries on. Every effort
metric confirms it — superstate does about 20% less work:

| | wall | cost | output tokens |
|---|---|---|---|
| vanilla | 33.9m | $1.81 | 156k |
| superstate_mcp | 28.1m | $1.45 | 129k |
| superstate_daemon | 28.2m | $1.42 | 120k |

And on every task vanilla won, superstate had stopped earlier: 26.3m vs 30.9m, 28.4m vs 35.1m,
16.1m vs 22.5m.

This is the exact inverse of the terminal-bench result, where *vanilla* quit too early — at
$0.069 against the $0.187 it spends on tasks it solves — and the gate kept superstate working.

**So the mechanism is one thing, not two: superstate replaces the agent's own judgement about
when it is done with the gate's.** That is a gain when the gate is the better judge and a loss
when it is not. Gate quality is not a detail of the evaluation; it is the product.

The datacurve gates are not vacuous — all six testable ones fail on a pristine container — but
they assert necessary conditions rather than sufficient ones, the same defect fixed for the
terminal-bench gates on 2026-09-16 and never audited here.

*Arm parity was verified clean for this run: identical model, memory limit and CPU across all
three arms.*

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

## 6. Nothing in superstate builds the gate

The gate is the active ingredient — the sign of the effect tracks its precision — and it is
supplied entirely by the caller:

| where | who authors the gate |
|---|---|
| the Rust binary | **nobody.** `--verify-cmd` is an *input* to `state init` |
| this evaluation | us, by hand — `GATE_FIXTURES`, 30 gates read off the task instructions |
| `_derive_gate` (LLM-authored) | exists, **default OFF**, never enabled in any recorded run |

Derivation was disabled for cause. Asked to write a gate for the same task twice, an LLM
produced a full functional check on one run and, on the other,
`test -f fastapi/middleware/deprecation.py && [ branch != main ]` — **satisfiable by `touch`**.

**This is the central tension in the handoff-first posture.** If an agent hands work to
superstate, that agent writes the `verify_cmd`. The architecture would then replace the agent's
judgement about when it is done with a gate written by the same agent — and the only
observation of that path produced a gate `touch` satisfies.

Meanwhile even careful, container-validated, hand-authored gates ranged from **92% precision on
terminal-bench to 17% on datacurve**, both written by us.

### Measured (EXP-054): an agent writes gates nearly as well as we do

| gate author | precision | solved |
|---|---|---|
| hand-authored fixtures | **92%** (12/13) | 92% |
| driver-authored | **79%** (19/24) | 85% (22/26) |

Same 13 tasks, same arm, same model; the only difference is who wrote the gate. **No
`touch`-satisfiable gate appeared** — the fail-closed critique, which rejects any proposal that
already passes, refused them, and the earlier docstring observation appears to predate it. What
the driver produces is substantive:

```
chess-best-move:   test -s /app/move.txt && grep -qE '^[a-h][1-8][a-h][1-8][a-zA-Z]?\r?$'
vulnerable-secret: test -s /app/secret.txt && grep -qE '^secret\[.+\]' /app/secret.txt
```

So the central tension is weaker than feared, **on this family**. Terminal-bench instructions
state the success condition outright, making gate authoring close to transcription. Datacurve
tasks are "change the repo so held-out tests pass", where the success condition is precisely
what is withheld — and our own careful gates reach only 17% there. Driver-authored gates on
datacurve are unmeasured, and that is where the question is actually hard.

## 7. The gate is not an eval convention — it is ours

No task in the corpus ships an agent-facing verification command. All 29 loadable tasks supply
**only the sealed grader** (21 `bash /tests/test.sh`, 8 `pytest tests/`). The SWE-bench and
terminal-bench convention is: instruct the agent, let it judge when it is done, grade with
held-out tests.

So the gate is superstate's own requirement, not a benchmark one, and the question "who writes
it" has no established answer to borrow. It matters because **the gate is superstate's stopping
rule** — without one it has no rule distinct from the agent's own judgement, which is vanilla.

Whether replacing that judgement is the right design is genuinely open. Vanilla's own judgement
is poor on terminal-bench (it quits at a third of the spend it uses on tasks it solves) and
better than the gate on datacurve (43% against superstate's 23-27%).

## 8. Decomposition may be the mechanism that does not need a gate

Decomposition has run — 56 recorded runs at 2-5 milestones via the `plan.md` path, against 253
single-milestone `direct_state_handoff` runs. On the 20 tasks run both ways it splits 8-8, and
**they are the opposite 8**:

| decomposition wins | decomposition loses |
|---|---|
| anko 100% vs 33%, httpx 100% vs 44%, arktype 50% vs 11% | chess 0% vs 89%, openssl 33% vs 100%, build-cython 0% vs 91% |
| db-wal, dna-insert, extract-elf, gcode-to-text, git-leak-recovery | expr, fastapi, katex, kv-store-grpc |

It wins on the hard repository tasks where gates score **17%** precision, and loses badly on the
artefact tasks where gates score **92%**. That is the inverse of the gate result, and it suggests
a complementary mechanism: where "done" cannot be stated up front, splitting the work so each
step is validated by the next one attempting to build on it beats writing a gate you lack the
information to write.

**Not established.** Those runs pool different eras and configurations, some likely with prompt
contracts on, and the overall means are 52% multi against 66% single. It is a hypothesis
generator, not evidence — but it is the first mechanism identified that does not depend on
somebody authoring a good gate.

Testable: decomposition on datacurve with a deliberately weak gate. If it recovers what the gate
destroyed, the answer to "who writes the gate" becomes "nobody needs to".

## 9. The evaluation exercises a small fraction of superstate

`superstate --help` lists a control plane with a dependency graph, checkpointing, rollback,
replanning, decomposition and adversarial review. Prior to EXP-057, the eval called four of those verbs.
In EXP-057 and EXP-058, `review` and `rollback` were integrated and evaluated.

| status | capability | what it does |
|---|---|---|
| **evaluated (EXP-057)** | `review` | **adversarial code review over git diff** — judges the work by inspecting it, not by a command written before the work existed |
| **evaluated (EXP-058)** | `state checkpoint` / `rollback` | **deterministic rollback on retry** — undo broken milestone modifications and recover clean baseline |
| unexercised | `state sync` | **reconcile state with a revised plan, preserving completed tasks** — the process adapting as work proceeds |
| unexercised | `state decompose` | split coarse tasks into atomic child micro-tasks |
| unexercised | `state resume` | executive briefing after context loss |
| unexercised | `state metrics`, `validate`, `apply`, `list` | telemetry and state management |

Used: `init`, `prompt`, `next`, `ready`, `exec`, `status`, `note`, `doctor`, `daemon`, `handoff`, `review`, `rollback`.

**`review` matters most**, because it is a determination of "done" that is *not* a gate. Every
result in this document concerns a mechanism where the success criterion must be written before
the work exists — which is why it scores 92% where the instruction states that criterion and 17%
where it does not. Reviewing the diff has no such requirement.

An offline evaluation of adversarial code review (`scripts/eval_offline_review.py`) against the
67 harvested run diffs from 2026-09-17 (29 false passes where gate passed but sealed grader failed,
and 38 true-pass controls) measures this directly:

| family | false passes caught (recall) | true passes blocked (false alarm) | base gate prec | gate+review prec |
|---|---|---|---|---|
| datacurve | **16/18 (88.9%)** | 5/5 (100.0%) | 21.7% | 0.0% |
| terminal-bench | **6/11 (54.5%)** | 18/33 (54.5%) | 75.0% | 75.0% |
| **overall** | **22/29 (75.9%)** | **23/38 (60.5%)** | **56.7%** | **68.2%** |

*Findings from the offline review measurement:*
1. **Review solves the 17%-gate blind spot:** On datacurve, adversarial review caught **16 of the 18 (88.9%)**
   runs where the vacuous/weak gate passed but the sealed grader failed (e.g. spotting unhandled edge cases
   in `expr-try-catch-errors`, broken scoping in `anko-typed-variable-bindings`, and incorrect syntax
   rules in `meriyah`).
2. **Review as a hard gate over-blocks:** Because the reviewer evaluates against general production
   standards rather than minimal synthetic benchmark test suites, it flagged 60.5% of genuine passing
   runs (e.g. noticing that `build-cython-ext` only committed a dirty submodule pointer, that `regex-log`
   captures internal subgroups, or that `katex-multicolumn-array-spans` left intermediate spanned indices
   undefined). Gating completion strictly on `ReviewReport::has_blocking_issues` would trap workers in
   rejection loops.
3. **Design implication:** Review is effective as an **advisory feedback channel** that feeds actionable
   findings back to the implementer subagent during retry loops, not as an uncalibrated binary pass/fail gate.

### Online evaluation of review and deterministic rollback (EXP-057 & EXP-058)

On 2026-09-18, both online code review and deterministic git rollback were evaluated in paired runs:

1. **Online blocking review (EXP-057):** Tested `superstate_daemon_review` against `superstate_mcp` across all
   14 core discriminating tasks (`results/daemon_review_v_mcp_core14_exp057.json`). Daemon review scored
   **7 / 14 (50.0%)** vs MCP's **6 / 14 (42.9%)** (**+7.1pp**). Discordant pairs were **3-2** in favor of the daemon
   (wins on `build-cython-ext`, `httpx-multipart-response-parsing`, and `katex-multicolumn-array-spans`; losses on
   `anko-typed-variable-bindings` and `scc-bounded-memory-spilling`). Review successfully caught incomplete or broken
   milestone submissions and guided workers to valid solutions on 3 tasks where MCP stopped prematurely.
2. **Deterministic git rollback on canary slice (EXP-058):** Tested `superstate_daemon` with `--auto-rollback`
   against `superstate_mcp` on the 3-task Canary slice (`build-cython-ext`, `chess-best-move`, `httpx-multipart-response-parsing`).
   Both arms tied at **2 / 3 (66.7%)**, but the rollback-enabled daemon achieved this with **17% fewer input tokens**
   and lower solve cost (**$1.03 vs $1.19 / solve**). On `httpx`, both arms reached 121 / 122 (99.2%) F2P tests.
   Crucially, the canary evaluation finished in **~37 minutes**, validating rapid-cycle signal chasing without 12-hour sweeps.
3. **Pure deterministic rollback ablation (EXP-059):** Tested `superstate_daemon_rollback` (`--auto-rollback`)
   directly against `superstate_daemon_review` (no rollback, dirty tree retained across retries) on the Canary 3
   slice (`results/canary_rollback_ablation_exp059.json`).
   - `superstate_daemon_rollback`: **3 / 3 (100.0%)**, $0.79 / solve, 683k input tokens / solve.
   - `superstate_daemon_review`: **2 / 3 (66.7%)**, $1.06 / solve, 915k input tokens / solve.
   - **Mechanism validation:** On `httpx-multipart-response-parsing`, `superstate_daemon_rollback` solved all
     **122 / 122 (100%)** F2P tests (1394/1394 total), whereas `superstate_daemon_review` failed at 121 / 122
     on a header whitespace formatting assertion caused by accumulated dirty state from its first turn.
   - **Cost & Token Impact:** Rollback achieved a **+33.3pp lift in solve rate**, **25.3% reduction in input tokens / solve**,
     and **25.5% lower cost per solve** ($0.79 vs $1.06).
   - **Decision:** Deterministic git rollback to milestone baseline on verification failure (`--auto-rollback`) is
     conclusively verified to prevent retry corruption and will become the permanent default in `DaemonRunner`.
4. **Full Autonomous Control Plane Benchmark (EXP-060):** Evaluated `superstate_daemon_full` (native default git rollback
   + blocking code review) against `superstate_mcp` across all 14 core discriminating tasks (`results/daemon_full_v_mcp_core14_exp060.json`).
   - `superstate_daemon_full`: **7 / 14 (50.0%)**, 2,388,954 input tokens/solve, $2.68/solve.
   - `superstate_mcp`: **6 / 14 (42.9%)**, 1,900,144 input tokens/solve, $2.15/solve.
   - **Discordant pairs (2-1 for Daemon):**
     - Daemon won `httpx-multipart-response-parsing` (122/122 F2P tests passed, 1394/1394 total, reward=1.0 vs MCP 121/122 F2P fail on dirty whitespace drift).
     - Daemon won `vulnerable-secret` (passed cleanly in 4 turns, reward=1.0 vs MCP failing on prompt policy/missing output).
     - MCP won `expr-try-catch-errors` (passed reward=1.0 vs Daemon solving 79/79 held-out feature tests but failing 11 pre-existing fuzz regression seeds).
   - **Partial Credit Generalization:** On `arktype-json-schema-refs-dependencies`, the daemon reached **24 / 25 F2P passed (96.0%, 1,703 / 1,704 total assertions)** while MCP scored **0 / 25 F2P (0.0%)** due to syntax corruption. On `katex-multicolumn-array-spans`, both reached 92 / 94 F2P (97.9%).
   - **Conclusion:** The fully autonomous, detached Rust background daemon (`DaemonRunner`) with native rollback and blocking advisory review outperforms the legacy synchronous MCP harness across the full diverse multi-language repository suite (+7.1pp lift, 7 vs 6 solves). This provides the conclusive empirical evidence to crown the Rust background daemon as our single production execution engine and retire the Python MCP harness.

**`state sync` remains unexercised.** It is what would let the plan change as the work reveals what the
work actually is, rather than committing to a decomposition made in ignorance.

So prior to EXP-057–EXP-060, every number described `init` + `prompt` + a gate over a single-node graph. With review,
rollback, and autonomous daemon execution now validated across the entire core benchmark, the control plane is officially
proven to surpass the legacy interactive harness.

*Section 9 updated on 2026-09-18 with online review (EXP-057), rollback canary (EXP-058), rollback ablation (EXP-059), and full control plane (EXP-060) evaluation results.*

## 10. The +20pp routing lift was an in-sample artifact

Commit `42cfa79` suggested that superstate's value lay in oracle routing between single-milestone
and multi-milestone execution (+20pp on datacurve, +6pp on terminal-bench).

A reproducible verification (`scripts/eval_routing_split.py`) shows that this was an in-sample
max-selection artifact over small-$n$ cells and confounded historical data:

1. **Terminal-bench collapses out-of-sample.** On the 13 gradeable tasks, a 1000-trial Monte Carlo
   split-half test (train on 50% of runs to pick the arm, score on held-out 50%) turns the in-sample
   oracle lift (+4.4pp) into a **-3.1pp held-out loss** (single 86.0% vs routed 84.2%). Picking the
   historical winner performs worse than a fixed single policy.
2. **The datacurve "multi" data is an era confound.** The "always-multi" runs on repo tasks were not
   produced by `superstate_mcp_planned` (which had 0 completed runs). They were 100% sourced from
   pre-09-15 arms (`superstate_rust` and `superstate_agent_mcp`) from the September 12–14 era with
   prompt contracts injected. With only $n=4$ to $12$ runs per cell, the oracle selected whichever
   historical arm was favored by small-sample variance.
3. **Verdict:** Withdrawn. There is no evidence of a routing signal to predict; training a classifier
   on these task labels would be fitting historical noise.

---

## Withdrawn

Fourteen ledger rows and findings are `WITHDRAWN`. They are kept, because the withdrawal is the finding.

| claim | why it fell |
|---|---|
| +20pp routing lift | in-sample max-selection artifact over n=4-12 cells; collapses to -3.1pp held-out on terminal-bench; multi data was pre-09-15 confounded arms |
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
* **Gate authorship, measured.** Run `SUPERSTATE_EVAL_DERIVE_GATES=1` against the tasks whose
  hand-authored gate precision we already know, and compare. This is the question the product
  rests on: if an agent cannot write a gate better than its own stopping judgement, handoff-first
  has no mechanism. Currently rests on two runs of one task.
* **Repair the datacurve gates** to assert sufficient conditions, then re-run at concurrency 2.
  Separates "superstate is not effective" from "we wrote bad gates for this family".
* **EXP-050** — vanilla plus the state prompt, no engine. Sizes how much of the effect is the
  text. Changes the framing of the claim, not what gets built.
* **daemon vs mcp where the loop fires.** The one genuinely untested architectural question.

None of these change what to build next. The daemon works, it is cheaper, and the mechanism is
understood well enough to act on.
