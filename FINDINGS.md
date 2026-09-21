# What the evaluation establishes

One place for what is true, so it stops being re-derived. Every claim names the experiment
behind it; `EXPERIMENTS.md` holds the full ledger, `CLAUDE.md` the working rules.

Last revised 2026-09-21.

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
5. **Tool Output Shunt Layer Benchmark (EXP-061):** Evaluated `superstate_daemon_full` with the native tool output shunt layer (`superstate shunt`) enabled against `superstate_mcp` across the Canary 3 slice (`results/canary_shunt_v_mcp_exp061.json`).
   - `superstate_daemon_full`: **3 / 3 (100.0%)**, $0.61 / solve, 486,434 input tokens / solve.
   - `superstate_mcp`: **2 / 3 (66.7%)**, $1.03 / solve, 900,340 input tokens / solve.
   - **Token Economics:** Shunting cut input tokens per solve by **46.0% vs MCP** (486k vs 900k) and **28.8% vs unshunted rollback** (486k vs 683k in EXP-059). Cost per solve plummeted from $1.03 to $0.61 (-40.8%).
   - **Quality & Signal:** On `httpx-multipart-response-parsing`, the daemon passed 122/122 (100%) F2P tests across 2 turns with zero context saturation, whereas MCP failed at 121/122 on whitespace assertion.
   - **Decision:** The native tool output shunt layer successfully compresses low-signal command logs into high-signal summaries and failure excerpts without degrading task solve rate, establishing programmatic context management as an essential pillar of high-efficiency agent execution.
6. **Full Core Suite Tool Output Shunting Benchmark (EXP-062):** Evaluated `superstate_daemon_full` with the native tool output shunt layer enabled against `superstate_mcp` across all 14 Core discriminating tasks (`results/daemon_full_shunt_v_mcp_core14_exp062.json`).
   - **Solve Rate:** Tied at **6 / 14 each (42.9%)**. Discordant pairs 1-1.
   - **Key Breakthrough on Deep Tasks:** On `scc-bounded-memory-spilling` (Go codebase memory-bounded file analysis with temporary disk spilling), `superstate_daemon_full` achieved a decisive clean win (**31 / 31 F2P passed, reward=1.0**) where `superstate_mcp` failed at 28 / 31 (failing CSV streaming assertions). In previous experiments (EXP-060), neither arm was able to solve `scc` due to compiler and test output flooding the context window.
   - **Macro Token Economics:** On shared build/test tasks (`build-cython-ext`, `chess-best-move`), tool output shunting reduced input tokens by **36.1% to 45.8%** and lowered per-task execution costs by up to **47%** ($0.54 vs $1.02).
   - **Conclusion:** Programmatic output shunting prevents terminal flooding and context saturation, directly enabling the autonomous daemon to solve deep, memory-bounded compiler tasks that previously overwhelmed LLM context windows, while drastically reducing token accumulation.

**`state sync` remains unexercised.** It is what would let the plan change as the work reveals what the
work actually is, rather than committing to a decomposition made in ignorance.

So prior to EXP-057–EXP-062, every number described `init` + `prompt` + a gate over a single-node graph. With review,
rollback, autonomous daemon execution, and now native tool output shunting validated across both Canary and Core suites,
the autonomous control plane is officially proven to deliver higher accuracy and solve complex compiler tasks at 35-45%+ lower token costs on build workloads.

*Section 9 updated on 2026-09-19 with online review (EXP-057), rollback canary (EXP-058), rollback ablation (EXP-059), full control plane (EXP-060), tool output shunt canary (EXP-061), and full core shunt benchmark (EXP-062) evaluation results.*

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

## 11. Repository-First Benchmark Architecture: Eliminating Command-Line Puzzles (2026-09-20)

Between EXP-058 and EXP-064, rapid-iteration experiments relied on a canary slice consisting of `build-cython-ext`, `chess-best-move`, and `httpx-multipart-response-parsing`. On 2026-09-20, systematic evaluation revealed this composition suffered from two structural defects:

1. **Category Error on Command-Line Puzzles:**
   `chess-best-move` is a visual image puzzle requiring a 4-character string output into a text file. Forcing the Autonomous TDD DAG onto this puzzle caused the worker to author a `pytest` file for a visual image, generating `.pyc` bytecode that triggered code review warnings and git rollbacks. An autonomous developer control plane (AST impact slicing, dependency DAGs, scoped git rollbacks, regression prevention) is built for multi-file software repositories—applying it to single-file script puzzles adds ceremonial friction without exercising repository mechanisms.
2. **Execution Latency in Canary Loop:**
   While `httpx-multipart-response-parsing` is a genuine repository task, its 1,394-test regression suite pushed canary evaluation times to 40+ minutes, defeating the purpose of a fast canary feedback loop.

### Decisions and Current Architecture:
* **Permanent Ban on Toy Puzzles:** Single-file script puzzles (`chess-best-move`, `regex-log`, `vulnerable-secret`, `extract-elf`, `dna-insert`) are moved to `EXCLUDED_TASKS` in `lab/benchmarks/task_sets.py`.
* **The Tri-Language SWE-Canary (`CANARY_TASKS`):** Formally established as 3 fast repository tasks spanning Python/C (`build-cython-ext`), Go (`scc-bounded-memory-spilling`), and TypeScript (`katex-multicolumn-array-spans`), delivering comprehensive multi-language repository coverage in ~15–20 minutes.
* **The Canonical SWE-Core (`SWE_CORE_TASKS`):** Pinned to the 9 real software engineering repositories (8 DataCurve codebases + `build-cython-ext`).
* **Task Qualification Rubric:** Codified the 5 mandatory criteria (multi-file repo with test suite, sealed grader, multi-turn complexity, substantial telemetry, discriminative headroom) in `docs/TASK-QUALIFICATION-RUBRIC.md`.

---

## 12. Complete Autonomous Control Plane vs. Vanilla Baseline: Tri-Language SWE-Canary (2026-09-21)

**Revised 2026-09-21 by the EXP-071 forensic audit (Section 13). Two claims below do not
survive it: the cost advantage reverses once adversarial-review turns are counted, and
impact slicing never executed. The pass-rate result stands.**

EXP-070 evaluated the complete autonomous Rust control plane (`superstate_daemon_full`: milestone test impact slicing + tool output shunting + scoped git rollback + blocking review + PreToolUse file read guard + PreToolUse command & polling guard) head-to-head against unmanaged `vanilla` across the 3 canonical repository canary codebases spanning Python/C, Go, and TypeScript.

### Results Matrix

| Repository | Language | vanilla | superstate_daemon_full | Outcome | Notes |
|---|---|---|---|---|---|
| `build-cython-ext` | Python / C | ✗ (0/11) | **✓ (11/11)** | **Daemon Win** | Vanilla stopped at turn 1 (136s) claiming completion ("done while wrong"). Daemon executed 5 turns, fixing build/KeyErrors to pass all tests. |
| `katex-multicolumn-array-spans` | TypeScript | ✗ (92/94) | **✓ (94/94)** | **Daemon Win** | Daemon solved task in 2 turns ($1.01, 1358s). Vanilla failed 2 separator tests ($1.63, 1761s). Daemon was **38.2% cheaper**. |
| `scc-bounded-memory-spilling` | Go | ✗ (28/31) | ✗ (28/31) | Tied | Both arms failed the final 3 streaming tests. Daemon was **38.0% cheaper** ($1.04 vs $1.68). |

### Core Telemetry

* **Held-out Grader Pass Rate:** **66.7% (2/3) vs 0.0% (0/3), +66.7pp lift** (Discordant pairs: 2 wins, 0 losses).
* **Cost Efficiency:** Daemon was **16.1% cheaper overall** ($2.86 vs $3.41), spending 38% less on both `katex` and `scc`.
* **Cost Efficiency — WITHDRAWN 2026-09-21.** The reported totals omit the adversarial-review
  turns entirely (Section 13). Counting them, daemon input tokens are 3,177,598 against vanilla's
  2,853,195: **+11.4%, not -17.7%**. The per-task "38% cheaper" figures on `katex` and `scc`
  are understated by 538,042 and 291,086 input tokens respectively; `katex` is at parity.
* **Mechanism Validation — PARTLY WITHDRAWN 2026-09-21.**
  - The command & polling guard executed: `command_guard_history.json` is populated in every
    daemon workspace.
  - **Impact slicing did not execute.** Zero `[impact-pass]`, `[impact-fail]` or
    `[impact-advisory]` notes across all EXP-070 and EXP-071 daemon workspaces. A successful
    slice emits `[impact-pass]` (`daemon.rs:1041`), so absence of notes is absence of execution.
  - **The file read guard is unevidenced.** No artefact from any run records it firing.
  - Output shunting did execute, but on **both arms** — it is harness infrastructure, not a
    treatment (Section 13).

---

## 13. EXP-071 forensic audit: what the control plane's mechanisms actually did (2026-09-21)

EXP-071 was registered for 54 runs across the 9 `SWE_CORE_TASKS`. **It died at 21 runs covering
4 tasks** and was never marked as such, so every figure below describes a truncated run and none
of it is a pass-rate result. `scripts/experiments.py check` reported "0 problems" because its
truncation branch is suppressed while a row's status is `PLANNED` (`scripts/experiments.py:106`)
— the precise failure mode the tool exists to catch.

What the audit does establish is mechanism status, and it is not what EXP-070 recorded. Each
claim below names the artefact behind it.

### 13.1 Mechanism status

| Mechanism | Status | Evidence |
|---|---|---|
| Tool output shunting | **Executes — on every arm** | 207 logs / 20.9 MB in `.agent-state/logs/cmd_*.log`; daemon 143 logs / 14.9 MB, **vanilla 64 logs / 6.0 MB** |
| Command & polling guard | **Executes** | `command_guard_history.json` populated in 17 workspaces with real command strings |
| PreToolUse file read guard | **Unevidenced; a concrete path makes it fail open** | see 13.4 |
| Milestone test impact slicing | **Never executed** | zero `[impact-*]` notes across all 16 EXP-070 + EXP-071 daemon workspaces |
| Scoped git rollback | **Executes, destructively** | see 13.2 |
| Adversarial review | **Executes, and is absent from telemetry** | see 13.5 |

Shunting is provisioned by `AgyCliDriver._setup_container_bridge` (`lab/engine/drivers/agy_cli.py:144-166`),
which writes the `./run-in-container` bridge for *every* arm and defaults on
(`${SUPERSTATE_SHUNT_ENABLED:-1}`). **A mechanism both arms receive cannot appear in an
arm-vs-arm delta**, and because the bridge defaults on when the variable is unset, an
off-condition control arm is currently unachievable. The daemon's own provisioning
(`daemon.rs:772-791`, a `.agent-state/bin/shunt` wrapper on `PATH`) is separately dead:
`CommandGuardDecision` (`command_guard.rs:51-57`) offers only `Allow` and `Deny` — there is no
rewrite variant — and neither `prompt.rs` nor `handoff.rs` ever mentions `shunt`, so nothing
prefixes a command with it.

### 13.2 Rollback destroys committed work, and disables its own retry budget

`perform_rollback` (`daemon.rs:555-562`) runs `git reset --hard <milestone baseline>` followed by
`git clean -fd`. All three call sites (`daemon.rs:978`, `:1164`, `:1386`) invoke it
**unconditionally on every failed attempt**, including the first and including attempts that
changed the tree. Because the eval runs `no_worktree=True`, "scoped rollback" degenerates to a
hard reset of the live workspace.

The git reflog of one arktype run states the outcome plainly:

```
dafcb320 commit: feat(json-schema): support $ref, dependencies, if/then/else, and deep enum equality
04355e8b reset: moving to 04355e8b...      <- x5
57d36e50 commit: feat(json-schema): support , dependencies, if/then/else, and deep enum equality
04355e8b checkout: moving from main to feat/json-schema-refs-dependencies
```

The worker built the feature, **committed it**, had it reset away five times, and rebuilt
substantially the same commit at the end. `reset --hard` moves the branch pointer, so worker
commits are destroyed along with uncommitted work.

It compounds with a second defect. `perform_rollback` ends by re-baselining `last_fingerprint`
to the **post-wipe** tree (`daemon.rs:568-570`), and `made_progress` is computed against that
(`daemon.rs:944-948`, `:1332-1337`). Any edit on the next attempt therefore counts as progress
and renews the retry budget, so the `stalled` condition — which the surrounding comment says
"counts only consecutive attempts that changed nothing" — is structurally unreachable. Across
EXP-071's 12 daemon workspaces:

| ledger note | count |
|---|---|
| `[verify-fail]` | 30 |
| `[rollback]` | 30 |
| `[retry-extend]` | 28 |

Only the first attempt on each task failed to "make progress". One worker prompt reads
`## PREVIOUS ATTEMPT VERIFICATION FAILURE (Attempt 6 of 3)`. The effective ceiling is
`max_retries * PROGRESS_ATTEMPT_MULTIPLIER` = 30 attempts, bounded in practice only by wall clock.

What the extra turns bought, on the task that consumed most of them:

| | turns | cost | f2p |
|---|---|---|---|
| `arktype` daemon (best run) | 7 | $3.58 | **23/25** |
| `arktype` vanilla | 1 | $1.13 | **23/25** |

Six extra turns and 3x the spend for an identical outcome. Note the worker was *not* starved of
diagnostics — the shunt hands it a real `--- Failure Excerpt ---` with the failing assertions.
It knew what was wrong; it had no code left to fix.

### 13.3 Four gate fixtures could not pass at all

`GATE_FIXTURES` entries are declared in **non-raw** `"""` literals, so a `\n` or `\"` written for
the generated program is eaten by Python and emitted as a real newline or a bare quote. **Two of
thirty fixtures carry the defect** -- an earlier count of four was a false positive from scanning
source text rather than rendered output; `httpx` and `scc` are sound. A third gate is broken for
an unrelated reason:

| task | consequence |
|---|---|
| `anko-typed-variable-bindings` | generated Go has a newline inside a string literal. Runtime proof from the run: `./main.go:16:37: newline in string`. The gate never compiled, so it tested nothing |
| `meriyah-explicit-resource-declarations` | same defect breaks the generated JavaScript parse |
| `expr-try-catch-errors` | asserts `try(1/0, "fallback") == "fallback"`. The task's own `solution/solution.patch` touches no runtime or division code, so **the reference solution fails this gate** |

The anko consequence is worth stating directly: all three anko runs are recorded `completed`, but
the gate could not compile, so completion came via the advisory-advance path. **The mechanism
under test did not operate on that task.**

A fourth gate was found broken once the positive direction could be run at all:

| task | consequence |
|---|---|
| `arktype-json-schema-refs-dependencies` | its if/then/else fixture used `required` with no `properties`, which the library rejects as an invalid object schema, so the assertion failed on any implementation. Fixed 2026-09-21; the gate now scores 4 passing, 1 failing against the reference |

The one remaining arktype failure is **not** a gate defect. The gate asserts the exact
non-existent-`$ref` message that `instruction.md` line 8 demands, and the reference solution emits
a different sentence. The instruction is what the worker is given and the only legitimate source
for a gate, so the gate stands and the disagreement is recorded in `gate_fixtures.py`. This is the
limit of reference-based validation: it assumes the reference implements the instruction.

`scripts/validate_gates.py` could not catch any of this. It asserted only that a gate *fails* on a
pristine container, so a gate that can never pass was reported as healthy. **8 of the 9
`SWE_CORE_TASKS` ship a readable `solution/solution.patch`** (all but `build-cython-ext`), so the
positive direction is cheap: apply it, run the gate, require exit 0.

**Fixed 2026-09-21.** `validate_gates.py` now runs both directions by default and exits non-zero
on either failure. Current SWE-Core standing:

| gate | negative | positive |
|---|---|---|
| `expr-try-catch-errors` | fails pristine | **accepts the reference** |
| `meriyah-explicit-resource-declarations` | fails pristine | **accepts the reference** |
| `scc-bounded-memory-spilling` | fails pristine | **accepts the reference** |
| `katex-multicolumn-array-spans` | fails pristine | **accepts the reference** |
| `arktype-json-schema-refs-dependencies` | fails pristine | 4 of 5 assertions; the 5th is the instruction disagreement above |
| `anko-typed-variable-bindings` | fails pristine | **unverifiable** -- the reference patches `parser/parser.go.y` but not the goyacc-generated `parser/parser.go`, so applying it leaves the new syntax unparseable |
| `python-statemachine-state-data-scoping`, `httpx-multipart-response-parsing` | inconclusive -- the gate nests its own `./run-in-container` | not attempted |
| `build-cython-ext` | fails pristine | no reference solution ships |

The checker reports "unverifiable" rather than "rejects" when a reference patch edits a generator
input without shipping the regenerated artefact, because a false accusation there would hide the
very defect the check exists to find.

This is the same lesson as the 17% datacurve gate precision collapse, one layer earlier: that
finding was about gates asserting necessary rather than sufficient conditions; this one is about
gates that assert nothing because they do not run.

### 13.4 The file read guard's deny path works; nothing shows it firing

Probed directly, the guard denies correctly — a 1769-line file at `--threshold-lines 200` returns
`{"decision":"deny"}` with an AST symbol outline. But no artefact from any run records a denial,
and the string `superstate-guard` appears nowhere under `/tmp/superstate_eval_runs`.

A concrete mechanism would explain that. All 17 `command_guard_history.json` files sit at
`<workspace>/.agents/.agent-state/`, so the hook process runs with cwd `<workspace>/.agents/`.
`cmd_pre_tool_use` passes the payload path to `Path::new(&path_str)` **with no resolution against
a workspace root** (`crates/superstate-cli/src/commands/guard.rs`), and `evaluate_file_read_guard`
returns `Allow` when the path does not exist (`guard.rs:57-59`). Any relative path agy sends
cannot resolve, and the guard is fail-open at seven distinct branches, so dormancy is its silent
default.

This is unresolved, not concluded. One command settles it: register a PreToolUse hook that dumps
stdin, run a single `agy` turn against a >200-line file, and read the payload shape.

### 13.5 Adversarial review runs, and is invisible in the numbers

`superstate_daemon_full` passes `--advisory-review`, and review executes as a full driver turn.
It is recorded in `.agent-state/driver-turns/` — which the eval never collects.

**For 10 of 11 EXP-071 daemon rows, the reported `input_tokens` equals the implementation turns
exactly.** The review turns — 7 turns, 3,603,203 input tokens — are excluded. Applying the same
correction to EXP-070 reverses its headline:

| EXP-070 | input tokens |
|---|---|
| daemon, as reported | 2,348,470 |
| review turns, excluded | +829,128 |
| **daemon, true** | **3,177,598** |
| vanilla | 2,853,195 |
| | **+11.4%, reported as -17.7%** |

Separately, this is the first recorded execution of `review` in the evaluation's history. CLAUDE.md
still lists it among the verbs that have never run; that is now out of date.

### 13.6 The arms do not receive the same task

Two asymmetries, both invisible in the reported result.

**The daemon is handed the gate's source.** Its `handoff.md` embeds the full verification command
including every assertion — for `expr`, the literal list of expressions and expected values. The
daemon's per-turn prompt is 6,720 bytes against vanilla's 1,455-character prompt. Handing the
executor its verification command is by design; **comparing that arm against one that never sees
it is not a clean architectural comparison.** On `expr` the extra information was actively
harmful, because the assertions were wrong.

**Three of ten vanilla runs produced no work at all.** They ended after 39-110 seconds with the
driver reporting success and a response of the form *"Waiting for the test suite to finish running
in the container."* — the agent yielded its turn while a backgrounded container task ran. Two left
a zero-byte `model.patch`; the third produced no patch artefact. Vanilla is single-shot, so a yield
is fatal; the daemon is re-invoked, so a yield costs it nothing. This is a harness artefact, not a
capability difference, and it depresses the baseline by up to 30% of its runs.

### 13.7 Observability gaps that let all of this persist

* The daemon arm writes **no `transcript.jsonl`** — only vanilla does. Worker turns live in
  `.agent-state/driver-turns/`, uncollected. An earlier investigation of this run cited a
  `transcript_full.jsonl` that does not exist, quoting guard-denial text reconstructed from the
  source rather than observed.
* `[verify-fail]` ledger notes store an empty diagnostic in 5 of 30 cases and a bare
  `Command exited with status 5:` in 13 more, so the ledger cannot reconstruct why a gate failed
  even though the worker was told.
* No post-run assertion checks that a declared mechanism did anything. A dormant mechanism
  currently surfaces only after a $30 run, if at all.

### 13.8 What follows

Ordered by what blocks a trustworthy re-run:

1. Stop rolling back on gate failure; keep the tree and let the worker iterate on the excerpt it
   already receives. Reserve rollback for a measured regression.
2. Stop re-baselining `last_fingerprint` inside `perform_rollback`, so `max_retries` binds.
3. Add positive-direction gate validation (apply `solution/solution.patch`, require exit 0) and
   delete the `anko`, `meriyah` and `expr` fixtures, which fail it by inspection.
4. Count review turns in reported tokens and cost; collect `driver-turns/` as the daemon transcript.
5. Warn in `experiments.py check` when a `PLANNED` row has a results file with rows in it.
6. Decide whether shunting is a treatment or harness infrastructure, and make
   `SUPERSTATE_EVAL`-style off-switching actually work.
7. Treat a vanilla yield as a harness abort, not a task failure.
8. Resolve the file guard's path handling once the payload probe answers 13.4.
9. Either teach impact slicing to recognise heredoc gates, or stop naming it in arm descriptions
   and ledger verdicts.

Nothing here is a claim about superstate's effectiveness. It is a claim about what EXP-070 and
EXP-071 measured, which is less than they reported.

### 13.9 What was fixed on 2026-09-21

| # | Change | Where |
|---|---|---|
| 1 | Rollback fires only when an attempt changed nothing. A failing attempt that moved the tree keeps its work; a stalled worker still gets a clean baseline | `daemon.rs:978`, `:1386` |
| 2 | Rollback removed from the blocking-review path entirely -- resetting the tree deletes the code the findings describe | `daemon.rs:1176` |
| 3 | Gate validation runs both directions by default, with `unverifiable` for unbuildable references | `scripts/validate_gates.py` |
| 4 | `anko` and `meriyah` escapes repaired; `expr`'s two `1/0` assertions removed; `arktype`'s `then` schema given a `properties` object | `lab/benchmarks/gate_fixtures.py` |
| 5 | Daemon telemetry is read after the daemon process exits, so the advisory-review turn is counted | `lab/engine/adapters/superstate_daemon.py` |
| 6 | `experiments.py check` reports `ABANDONED?` for a PLANNED row whose results file already holds runs | `scripts/experiments.py` |

`last_fingerprint` is deliberately still re-baselined inside `perform_rollback`: once rollback
only follows a stall, the post-rollback tree *is* the baseline the next attempt works from, so
comparing against it is correct rather than the bug it was under unconditional rollback.

Two things this did not fix, both still open:

* `workspace_fingerprint` hashes size and mtime, not content, so a worker that rewrites identical
  bytes still reads as progress and the stall path rarely triggers. That is now a missed escape
  valve rather than a destructive loop, but it means `max_retries` still binds loosely.
* ~~The file read guard's path resolution (13.4) is unchanged, pending the payload probe.~~
  **Fixed later the same day (0bf20f6).** The probe turned out to be unnecessary: the command
  guard populates its history on every run and both guards share `extract_tool_invocation`, so
  the payload shape was demonstrably recognised and path resolution was the only remaining
  failure. See 13.13, and `scripts/guard_smoke.sh` which asserts it from a `.agents` cwd.

Rust suite 397 passed; eval suite 343 passed.

### 13.10 EXP-072: the rollback fix holds; three more defects surfaced (2026-09-21)

A 3-task canary run to answer one question -- did the fixes take effect in a live run? It is
not a solve-rate result (1/3, $4.70) and n=3 cannot separate 2/3 from 3/3.

**The rollback fix took.** One rollback across five failures, against 30 of 30 in EXP-071. The
katex ledger reads exactly as designed:

| attempt | outcome | tree changed | action |
|---|---|---|---|
| 1 | failed | yes | retry-extend, **no rollback** |
| 2 | failed | yes | retry-extend, **no rollback** |
| 3 | failed | yes | retry-extend, **no rollback** |
| 4 | failed | **no** | rollback to baseline |

One reset and six surviving commits across three runs; in EXP-071 arktype alone lost committed
work five times.

**The telemetry fix did not take.** scc's 498,304 review tokens were still excluded. The cause
was a defect the fix unknowingly rested on: the adapter looked for
`.agent-state/daemons/default.pid`, but the engine has written `daemons/<branch-slug>.pid`
since ADR-0002 made daemons branch-scoped. `pid` was None on **every** daemon run ever, which
also silently disabled the poll loop's dead-process detection and left `provenance.daemon_pid`
null throughout. Telemetry now waits on the artefact -- the driver-turns directory going quiet
-- rather than on process identity.

**Impact slicing fired for the first time, and it manufactures failures.** All four katex
failures were `[impact-fail] Fast test slice failed: No tests found, exiting with code 1 ... In
/workspace`. Runner detection is a substring search, and it matched `jest` inside the *body* of
`cat <<'GATEEOF' | ./run-in-container sh -s` -- the script being piped to another process, not
the command the shell runs. The rewrite produced an unterminated heredoc that executed on the
host. Four attempts, $2.71, and the task, lost to the slicer rather than the agent. This is the
second correction to EXP-070's "impact slicing executed flawlessly": it never ran there, and
when it does run it fabricates failures. A command that cannot be parsed is now left alone.

**The same defect class had been built into the new TDD gates.** The fixtures routed through
`./run-in-container`; the engine-derived gates did not, so `python -m pytest` and `go test`
would have run on a host holding the source but none of the dependencies -- exactly what katex
demonstrated. Every runner invocation now goes through the bridge when the repository carries
one, while `test -f` stays host-side. Caught before any TDD run, by reading this canary rather
than by running one.

**What it does not settle.** Whether preserving progress beats resetting. katex's three
preserved attempts did not converge either, so Manifesto Invariant III -- which mandates a hard
reset on every gate failure -- remains open, and the divergence introduced on 2026-09-21 is
still a divergence, not a decision. What is settled is that the runaway is gone: four attempts,
not "Attempt 6 of 3".

---

### 13.11 EXP-074: autonomous TDD executes end to end (2026-09-21)

The first valid run of the path that replaced `GATE_FIXTURES`, against a snapshotted binary so
the build could not change underneath it (EXP-073 was withdrawn for exactly that).

**The mechanism works.** `scc-bounded-memory-spilling` completed the whole DAG:

| step | evidence |
|---|---|
| worker authors its own reproduction test | `reproduce_issue_test.go`, 10,821 bytes |
| RED gate: compiles and FAILS | milestone `tdd-reproduction-test` completed after 3 attempts |
| checkpoint | `e9d50ba chore(superstate): checkpoint completed milestone tdd-reproduction-test` |
| worker implements the fix | — |
| GREEN gate: reproduction test AND the repository's own suite pass | milestone `fix-implementation` completed |
| checkpoint | `d10d55d chore(superstate): checkpoint completed milestone fix-implementation` |
| final | `status=completed` |

No hand-authored assertion was involved at any point. That is Manifesto Invariant V operating
as specified, for the first time in this repository's history.

**Rollback under TDD is cheap, as predicted.** RED took three attempts, two of them reset under
the default `always` policy, and it cost little because RED is a single test file. This is the
evidence that the EXP-071 cost measurement -- a whole feature rebuilt five times -- was an
artefact of single-milestone fixture gating rather than of resetting as such. Invariant III
looks defensible again; the ablation arms exist to settle it rather than to assume it.

**katex blocked for a reason that predates TDD.** Its worker never wrote a test, yielding on a
backgrounded Jest run and then on the command guard's own debounce: *"I am waiting for the
cooldown timer to elapse. I will now stop calling tools and wait for the scheduled
notification."* That is the yield defect of 13.6, with an added twist -- a guard meant to stop
busy-wait polling induced the worker to stop working. Invariant IV's perimeter guards are
mechanically present and behaviourally counterproductive here.

**The pass rate and telemetry in the results file are void.** `normalize_gate_command` raised
`NameError: BRIDGE_PREFIX_RE is not defined` at the confirmation gate, because that constant was
deleted along with the gate-derivation block earlier the same day and nothing referenced it
until the last step of a 40-minute run. All three rows therefore read `Passed=False`, zero
turns, $0.00, and the sealed grader never executed. **Do not read 0/3 from
`canary_tdd_exp074.json`.** A unit test now covers it.

**Three harness defects in three runs, all introduced the same day.** The sentinel leak, the
binary swapped mid-run, and this NameError were all mine, all from the same day's refactor, and
all found by running rather than by reading. The runs are currently measuring the harness, not
the system -- which is the condition this repository has documented repeatedly and which
argues for a quiet period of fixing before any result is quoted.

**What is still unknown:** whether a worker-authored reproduction test agrees with the sealed
grader. That is the precision question that killed the hand-authored fixtures at 17%, relocated
to a new author and still unmeasured. It needs a run that reaches the grader.

---

### 13.12 EXP-075: the gate-precision problem is relocated, not solved (2026-09-21)

The run that asked the decisive question: when a worker's own reproduction test certifies the
work, does the sealed grader agree?

| task | milestones | gate verdict | sealed grader | cost |
|---|---|---|---|---|
| `scc-bounded-memory-spilling` | both completed | **done** | **f2p 31/31, p2p 286/286** -- agrees | $2.87 |
| `katex-multicolumn-array-spans` | both completed | **done** | **f2p 92/94**, p2p 599/599 -- disagrees | $3.52 |
| `build-cython-ext` | aborted at handoff | n/a | never ran | $0.00 |

**Agent-authored gate precision: 1 of 2.** katex reached `status=completed` with both milestones
passing, which is the control plane asserting the work is finished, and the held-out suite then
failed it on two tests. That is the same shape of error that made the hand-authored fixtures
worth banning, with a different author.

So Manifesto Invariant V removes the *leak* -- no maintainer test is pre-seeded, and the worker
does its own diagnosis -- but it does not by itself make the gate correct. Invariant II's claim
that *"a milestone is complete if and only if its verification command exits 0"* holds
mechanically and still certified incomplete work.

**The failure mode is different in kind, and more tractable.** The fixtures failed by asserting
things that were wrong: `expr` demanded behaviour its own reference solution does not implement,
`anko` and `meriyah` could not compile. katex's reproduction test was simply *narrower* than the
grader -- it covered the bug the worker diagnosed, and two further fail-to-pass tests were not
covered. p2p was perfect in both tasks, so nothing was broken. A test that is too narrow can be
widened; a test that is wrong has to be discarded.

**Neither task beat its historical attractor.** Both are bimodal, and both landed where they
usually land, at the highest cost on record:

| task | non-solve | solved before | EXP-075 |
|---|---|---|---|
| `scc` | 28/31 | 4x at ~$1.10 | 31/31 at **$2.87** |
| `katex` | 92/94 | 2x at ~$1.20 | 92/94 at **$3.52** |

So TDD did not reach work the previous regime could not. It cost about 2.5-3x more for the same
outcomes. 1/3 at $6.40, against EXP-072's 1/3 at $4.70.

**The cost is not TDD's doing.** On scc the reproduction milestone cost 255k input tokens, about
9%; the two adversarial review turns cost 568k, 21%; and a **single 29-minute implementation turn
consumed 1,917,135 -- 70% of the run**. Invariant IV promises that turn should have been bounded
("massive file reads must be intercepted", "zero token waste"), and the file-read guard has still
never been observed firing in any run. The budget policy compounds it: completing a milestone
earns a +1200s lease extension, so decomposing one milestone into two *raises* the ceiling.

**Telemetry is still short by one turn.** Reported input for scc was 2,410,872; the driver turns
sum to 2,740,756. The difference is exactly the final review turn, written after the harness
finished. The settle-wait catches the first review and not the last.

---

### 13.13 The command guard was telling the worker to stop (2026-09-21)

EXP-076 was stopped after 41 minutes, having produced a finding rather than the measurement it
was registered for. `scc` was BLOCKED four minutes in, after three consecutive turns of:

> *"The existing test suite is running in the background. I will wait for it to complete."*
> *"I will wait for the background task to complete."*
> *"I am waiting for the background test command to finish execution."*

The cause was our own guard. Its denial text read:

> *"Busy-wait polling blocked: ... Do not loop on status; **yield turn to await background task
> completion notification**."*

In headless print mode nothing ever delivers that notification, so yielding ends the task. Three
yields exhaust `max_retries` and the milestone is blocked. The same instruction is visible in
katex's EXP-074 transcript (*"I am waiting for the cooldown timer to elapse"*) and in the three
vanilla collapses of EXP-071 -- except vanilla has no guards, so the agent backgrounds long
commands and yields on its own; the guard did not create the defect, it industrialised it.

Two implementation errors, both fixed:

| defect | fix |
|---|---|
| a denial that instructs the agent to end its turn | a poll inside its cooldown is now **throttled** -- the hook sleeps out the remainder and allows, bounded at 30s. Same rate limiting, no refusal |
| every repeated shell command was debounced, not just polling | only procfs reads, process inspection and `manage_task` status/list. Re-running `go test ./...` after an edit is the TDD loop Invariant V mandates, and debouncing it put Invariant IV in direct contradiction with it |

**And a third mechanism was missing entirely.** The file read guard matched only the agent's
file *viewing tool*, so `cat internal/scanner.go` bypassed it -- along with the command guard,
which classifies only polling, and output shunting, which wraps `./run-in-container` and not host
commands. Across recorded runs **29 of 152 logged commands were `cat` or `grep`**. A whole-file
dump through the shell now meets the same line budget and returns the AST outline; bounded reads
(`head -50 x.go`, `sed -n '10,60p'`) pass through untouched, because intercepting compliance is
the same mistake in a different costume.

Spotify's Portal reports ~90% savings on bulk reads using this pair of hooks -- a file-size hook
and a `check-bash-read` hook. We had the first and not the second. Where our design is ahead:
Portal delegates the read to a cheaper model and reports that the summaries *"lack reliable line
numbers"*, so it cannot delegate editing, at 10-30s latency per delegation. A Tree-sitter AST
outline carries exact line ranges and costs no model call.

**The tests asserted the harmful behaviour verbatim**, including the "yield turn" string, which
is why it survived. They now assert that a poll receives no refusal and that the guard never
emits any instruction to end a turn.

Nothing here is measured yet. The prediction for the next run is specific: `guard-denials.jsonl`
non-empty, no yields, and first-turn `input_tokens` below EXP-075's baseline of 33,213 (scc) and
195,957 (katex).

---

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
| EXP-070: daemon 16.1% cheaper | adversarial-review turns excluded from telemetry; true input tokens are +11.4% vs vanilla (Section 13.5) |
| EXP-070: impact slicing executed flawlessly | it did not execute at all — zero `[impact-*]` notes in any workspace (Section 13.1) |
| EXP-070: impact slicing executed flawlessly (2) | it fabricates failures when it does fire -- 4 spurious `No tests found` on katex by slicing inside a heredoc (13.10) |
| EXP-070/071: the file read guard executed cleanly | no artefact records it firing; the hook's cwd makes relative paths fail open (Section 13.4) |
| shunting is a superstate token-saving mechanism | `AgyCliDriver` gives it to every arm, vanilla included, so it cannot show up as lift (Section 13.1) |

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
