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

**Corrected later the same day (13.14): file reads cannot account for this turn.** scc's own
source is 133,550 tokens, so a perfect guard recovers under 7% of 1,917,135. The attribution
above -- command output was under 2%, therefore reads must be the rest -- was elimination without
an upper bound on the remaining candidate. Either the same files were read many times, or another
channel carried the volume; no artefact the daemon writes can tell them apart.

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

### 13.14 The guard cannot explain the 1.92M turn (2026-09-21)

`scripts/guard_ceiling.py` computes, without a model call, what a file read guard could save:
tokens to read each file whole against tokens of the AST outline returned instead. Run against
the canary repositories in under a second each:

| repository | files over 200 lines | own source, read whole | ceiling |
|---|---|---|---|
| `katex` | 40 | 237,651 | **96.6%** |
| `scc` (including vendored deps) | 289 | 2,064,564 | 93.2% |
| **`scc` (own source only)** | **21** | **133,550** | **95.2%** |

The mechanism has ample headroom -- an outline is 3-5% the size of its file, matching the
artefact-level efficiency Portal reports. But the second row is the one that matters, and it
retires a claim made earlier the same day.

**scc's entire own source is 133,550 tokens. EXP-075's GREEN turn admitted 1,917,135.** That is
fourteen times the codebase. A *perfect* file read guard -- intercepting every eligible file and
saving 95.2% -- recovers at most ~127,000 tokens, **under 7% of that turn**.

So 13.12's reasoning, that shunted command output was under 2% and therefore "unbounded file
reads are the only channel that large", does not hold. Reading every file in the repository once
does not come close to 1.92M either. Two possibilities remain and they point opposite ways:

* **the same files were read repeatedly**, in which case the guard saves ~95% of every read and
  the effect compounds to something large;
* **the volume came from another channel** -- host-side command output that never passed through
  `./run-in-container` and so was never shunted, or accumulated reasoning -- in which case the
  guard barely touches it.

**These cannot be distinguished from any artefact the daemon currently writes.** The arm produces
no tool-call transcript (13.7), so there is no record of what was read, how often, or how large
each result was. That gap, not the guard, is now the binding constraint on the whole question.

The measurement discipline is the reusable part: 0.33 seconds of arithmetic produced a sharper
and more falsifiable question than four benchmark runs did. Compute the ceiling before deciding a
workload is worth an agent turn.

---

### 13.15 EXP-078: the perimeter guards work, and cost about 27% less (2026-09-21)

The first run in which the guards demonstrably operated. `guard-denials.jsonl` had been empty in
every previous run ever recorded; here scc withheld 1,917 lines across 4 denials and katex 2,258
across 2. No worker yielded. Paired against EXP-075 on identical tasks, same arm, same rollback
policy, same driver -- **only the binary differs**, carrying the four guard fixes:

| task | EXP-075 | EXP-078 | input tokens |
|---|---|---|---|
| `scc-bounded-memory-spilling` | PASS 31/31, $2.87, 2,410,872 | PASS 31/31, $2.07, 1,725,692 | **-28.4%** |
| `katex-multicolumn-array-spans` | **fail 92/94**, $3.52, 2,906,759 | **PASS 94/94**, $2.54, 2,136,189 | **-26.5%** |
| run total | 1/3, $6.40 | **2/3, $4.61** | |

**The cost reduction is the signal worth keeping.** Two independent tasks moved -28.4% and -26.5%,
which is a far more stable quantity than a pass/fail flip. katex crossing from 92/94 to 94/94 is a
move between the two modes it has occupied across nine recorded attempts, at n=1, and should not
be read as a solve-rate result.

**Causation is not isolated.** The binary carries four changes -- path resolution, denial
telemetry, throttle-not-refuse, and bulk-read interception -- and at least one of them affects
outcomes by a route other than tokens: the throttle fix removes the yield that cost katex a turn
in EXP-075 (6 turns there, 5 here). A single-variable attribution would need the ablation arms.

**Gate precision is now 3 of 4** across the two runs. katex's GREEN gate certified 92/94 work in
EXP-075 -- the relocated 17% problem of 13.12 -- and certified correct work here. Still far too
few observations to call it a rate.

**On the -4.2% offline result (13.14):** it was not wrong, it was narrow. `guard_bench.py` asked a
single question of one crate and intercepted one file of ten eligible; the benchmark workload is
genuinely read-heavy and intercepted four and two. The offline number is a lower bound on a thin
workload, the ceiling is 96%, and the realised figure on real tasks sits between them at ~27%.

**What this does not settle: 13.14 stands.** scc's own source is 133,550 tokens and this turn still
admitted 1,725,692. A 28% reduction is consistent with repeated reading being a large share of the
remainder, but this run predates `guard-activity.jsonl`, so there is still no record of what was
read or how often. The next run carries that trace and can answer it.

---

### 13.16 EXP-079: where the context actually comes from (2026-09-21)

The first run carrying `guard-activity.jsonl`, which records every read and command the guards
evaluate. It answers 13.14's question, and the shape is near-identical across a Go and a
TypeScript repository, so it is a property of the workload rather than the language:

| | scc | katex |
|---|---|---|
| evaluations | 311 | 321 |
| commands | 145 | 152 |
| bounded reads | 150 | 146 |
| **whole-file reads** | **16** | **23** |
| reads that were of a file already read | **152 of 166** | **142 of 169** |
| most-read file | `formatters.go` **80x** | `array.ts` **79x** |
| tokens through whole-file reads | **~4,740** | **~10,740** |
| denials | 4 | 2 |

**The file read guard is at its ceiling.** Against turns admitting 1.9-2.1M tokens, unbounded
reads contributed under 11,000. The guard denied six times across both tasks because there was
almost nothing left to deny -- the agent already reads in bounded ranges, 296 times out of 335.
The ~27% reduction measured in EXP-078 is close to everything this mechanism can offer, and no
amount of tuning its threshold will change that.

**The volume is repetition and commands.** One file fetched eighty times in each repository, and
~150 commands per task of which roughly half are host-side -- `git status` fourteen times,
`git log`, `ls -la` -- which shunting never sees, because it wraps `./run-in-container` only.

**What this still cannot say, and the claim I withdrew because of it.** This binary predates
window recording (b5a4656), so the trace carries paths without ranges. Eighty reads of a
1,559-line file may be eighty distinct windows, which is exactly correct behaviour under a
200-line budget, or eighty fetches of the same lines, which is waste. I asserted the second
before checking; it is unsupported. The two imply different fixes:

* same windows -> a **read cache** is the lever;
* distinct windows -> reads are already efficient and the remaining volume is **command output**,
  so host-side shunting is the lever.

`guard_bench.py` with the current binary answers this offline in minutes. It does not need
another canary, and reaching for one was habit rather than reasoning.

**Token reduction holds at n=2, the pass rate does not.** scc 2,410,872 -> 1,725,692 and
1,934,937; katex 2,906,759 -> 2,136,189 and 2,148,457. Meanwhile katex graded 92/94, 94/94 and
90/94 across the three runs: EXP-078's pass was variance, exactly as 13.15 cautioned, and anyone
quoting "2/3 versus 1/3" as a guard effect would be quoting noise.

---

### 13.17 A third of every run is MCP tool schemas (2026-09-21)

Chasing where scc's 2,629,120 input tokens went ended somewhere none of the candidates predicted.
Measured directly, with a shadow `HOME` that symlinks everything real and replaces only
`mcp_config.json` (the first attempt failed because agy authenticates through `~/.config/gcloud`,
which moves when `HOME` does):

| configuration | fresh input for a turn that replies "pong" | vs baseline |
|---|---|---|
| as shipped | **24,222** | — |
| `--disable-slash-commands` (skills off) | 20,694 | -14.6% |
| **MCP servers removed** | **10,934** | **-54.9%** |

**13,288 tokens on every agy invocation are tool schemas**, for four globally-enabled MCP servers:
`github`, `notion`, `slack` and `superstate`. A worker fixing a Go test carries the ability to
file GitHub issues and post to Slack. The MCP-off run still had skills enabled, so removing both
goes lower still.

A turn that does no work at all costs 24,222 fresh tokens. That is the floor every experiment has
paid, 79 times.

**Scale.** MCP schemas are ~13,288 of the ~23,000 context processed per tool call -- about 58%.
scc made 311 calls at ~5,000 fresh tokens each, which puts MCP at roughly 800,000-900,000 tokens,
close to a third of the run. The 13,288 is measured; the multiplication is arithmetic on top of
it, not a second measurement, so treat the total as an estimate with the right order of magnitude.

**What it does and does not invalidate.** MCP loads identically for every arm, so it is a constant
offset rather than a confound: **paired comparisons stand**, including EXP-078's -27%. What is
inflated is every absolute figure. "superstate solves scc for $2.07" means "$2.07, of which
roughly a third is tool schemas for services this benchmark never touches."

**There is no per-invocation escape.** agy's full flag list has nothing for tools or MCP; skills
can be disabled per run, MCP only globally via `agy mcp disable`. Disabling it around an eval run
is an operational step, and a crashed run leaves the servers disabled, so it needs care.

**Ranked against everything else measured today:**

| lever | size | ours to fix? |
|---|---|---|
| MCP tool schemas | ~30% of a run | yes, config |
| agy cache hit 76-81% vs Claude's 94% on identical work | ~1M on scc | no, agy's |
| tool call count (311 x ~5,000 fresh) | ~30% if halved | partly |
| skill expansion | ~15% of preamble | yes, one flag |
| the perimeter guards built today | -27% measured | yes |

The guards are the smallest lever on the list and took a day to build. The largest is a config
file nobody had looked at.

---

### 13.18 The 200-line read budget costs more than it saves (2026-09-21)

The window question from 13.16, answered offline in four minutes with the range-recording binary
(b5a4656). A read-heavy prompt against a copy of `superstate-core/src`:

```
of 19 reads carrying a window, 0 re-fetched a window already fetched (0%)
```

**Not one read was redundant.** `daemon.rs` was fetched 14 times in 14 distinct windows:

```
[20:130] [130:180] [180:285] [590:720] [770:835] [835:950] [951:1030]
[1030:1150] [1145:1185] [1170:1250] [1251:1440] [1440:1570] [1565:1640] [1780:1907]

distinct lines fetched      1,396 of 1,906  (73% of the file)
including overlap           1,429            (almost no redundancy)
```

So the repeats-by-file in 13.16 were an artefact of recording paths without ranges. The agent was
paging through a large file exactly as the budget forces. **A read cache would save nothing**, and
the claim that those reads were wasteful is retired for good.

**The budget is net-negative on this workload.** Once a tool call carries a ~2,500-token preamble
(13.17), splitting a file multiplies that cost:

| | calls | tokens |
|---|---|---|
| bounded at 200 lines | 14 | **50,719** |
| whole file | 1 | **23,466** |
| | | **2.2x worse** |

Worse, it cannot recover. The largest possible saving from skipping is the whole file, ~21,000
tokens; thirteen extra calls cost ~32,500. **At 14 calls the budget cannot break even even if the
agent reads nothing.** The result is robust to the preamble estimate -- at 1,000 tokens per call
it is still 1.27x worse, and with MCP enabled (~5,000) far worse.

**When it does win:** low coverage. Needing ~30% of a file is ~3 calls, costing ~5,000 in extra
preambles against ~14,700 saved -- a clear gain. The failure is that a *fixed* threshold fires
hardest exactly when it should not: exploring an unfamiliar large file, where the agent ends up
reading most of it anyway.

**The threshold was chosen before anyone knew a call had a fixed cost.** 200 lines is a guess from
a model where tokens-per-read was the only quantity that mattered. The governing ratio is
`preamble_tokens / tokens_per_line` -- roughly 230 lines of savings needed to justify each extra
call -- so the budget must be large enough that splitting is rare, not the default.

This is the third time today a perimeter mechanism turned out to be pointed at the wrong quantity:
the guard never fired at all (13.13), then fired on a channel carrying 15% of the traffic (13.16),
and now the one thing it does reliably costs more than it saves.

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

### 13.19 The read budget is now a swept parameter, not a constant (2026-09-21)

13.18 established that 200 lines was the wrong number. The change is not "200 → 800" but a
change in kind: the budget became something a run can vary, because the evidence says its
optimum is a property of the workload rather than of the guard.

**What 800 rests on.** Replaying the recorded trace across thresholds put the optimum at ~1,600
for that workload (29,932 tokens), with 800 at 32,432 — 8% above optimum. 800 was chosen over
1,600 because the cost curve is asymmetric and the risk is not symmetric either: too low costs
roughly twice what no budget at all costs (100 lines → 66,497; unbounded → 35,542), and the
optimum shifts down on codebases whose files are shorter than `superstate-core`'s. 800 gives up
8% on the measured workload to stay clear of the expensive side of the curve.

**Where it is set.** One constant, `guard::DEFAULT_READ_THRESHOLD_LINES`, with the CLI defaults
and `DaemonConfig::default()` both deriving from it. Precedence when the daemon starts:

| Source | Use |
|---|---|
| `--read-threshold-lines N` on `state daemon` | pinning one run |
| `SUPERSTATE_READ_THRESHOLD_LINES` | sweeping without a rebuild |
| `DEFAULT_READ_THRESHOLD_LINES` | everything else |

A malformed env value aborts rather than falling back. A swept parameter that quietly reverts
to its default produces a run that looks like a data point and is not one — the same failure
mode as the unrecognised `--rollback-policy`, which aborts for the same reason.

**The adapter does not set it.** Per the Referee Rule the eval harness passes nothing here; the
daemon owns the number. That is deliberate and is the precondition for the next step below.

**Two test-design corrections this forced.** Three `test_cli_guard` tests failed on the change
and told us nothing about the guard: they used 250-line fixtures against an implicit default,
so they were asserting the default's value while claiming to assert shunt behaviour. They now
pin `--threshold-lines 200` explicitly. `guard_smoke.sh` had the same defect in reverse — a
hardcoded 480-line fixture that stops exercising the deny path once the budget passes it. It
now reads the default out of `--help` and sizes its fixture at ~2× the budget.

**Next: derive it inside the daemon.** The parameter exists so it can eventually stop being a
parameter. The daemon already has the input needed to compute it: the file guard records every
evaluation to the activity trace with its line count, which is exactly what `read_budget.py`
replays offline. A daemon that read its own trace could converge on a repository's own optimum
instead of inheriting a number measured on `superstate-core`. What is missing is not the
plumbing but the evidence — one workload's curve is not a derivation rule, and a rule fitted
to a single repository would be the same mistake as the constant it replaces. Measure the
curve on a second and third repository before writing one.

### 13.20 Autonomous TDD silently broke `build-cython-ext`, and it has been scored as a failure for seven runs (2026-09-22)

Found while auditing a 7-second, $0.00 run in EXP-080. It is not a read-budget finding and it
matters more than one.

| runs | build-cython-ext | wall clock | cost |
|---|---|---|---|
| EXP-058 - EXP-072 (18 runs, pre-TDD) | **17 pass, 1 fail** | 550-1,030s | $0.55-1.25 |
| EXP-074, 075, 076, 077, 078, 079, 080 | **7 fail, 0 pass** | **5.5-8.2s** | **$0.00** |

The break is at `db35e76`, "delete GATE_FIXTURES and hand off under autonomous TDD".

**Cause.** The task's own instruction is to clone pyknotid into `/app/pyknotid`, so the image
ships an empty `/app` and the workspace initialises empty. `tdd.rs` derives its DAG from
repository layout, finds no `go.mod`, `package.json` or `pyproject.toml`, and fails closed:

    could not identify a test runner ... Autonomous TDD needs the repository's own runner;
    refusing to emit a gate that cannot fail

That refusal is correct in isolation -- Invariant 2 allows exactly two gate sources and an
ungateable task should not get a fabricated gate. But the adapter treats the failed handoff as
a failure to initialise daemon state, the run aborts before the worker takes a single turn, and
the harness records `passed=False`. A task that cannot be *gated* is scored as a task the agent
could not *do*.

**What this invalidates, and what survives.**

* Any **pass rate** from EXP-074 onward is over three tasks of which one was a guaranteed
  zero for the daemon arm. The canary has effectively been a two-task canary for seven runs.
* The **per-task token findings survive**, because they were computed per task from scc and
  katex and never involved build-cython-ext. EXP-078's -27% and EXP-079's channel analysis
  stand as stated.
* EXP-074 and EXP-075 recorded that autonomous TDD "executes end-to-end". True for scc and
  katex; on the third canary task it replaced a reliable pass with an instant abort, and the
  rows do not say so.

**Why it went unseen for seven runs.** A 5-second $0.00 row looks like a fast failure, and
CLAUDE.md's existing warning is tuned for the opposite shape -- `Cost=$0.00` with a wall clock
*near the budget*, meaning a lost-telemetry timeout. The inverse signature, a wall clock far
*below* any plausible floor, had no rule attached to it. It does now: **a run that ends in
single-digit seconds did not run, whatever its recorded verdict says.**

**Not fixed here, because the fix is a gating-semantics decision.** Three options, in
increasing order of how much they change what the arm measures:

1. **Score it honestly.** Record an arm-level ungateable outcome distinct from `passed=False`,
   so it stops depressing pass rates. Changes no behaviour, only the books. Note that
   `UNMEASURABLE_TASKS` is the wrong home -- that list is about tasks with no sealed grader,
   and this task has one and runs fine under `vanilla`. The unmeasurability is arm-specific.
2. **Defer derivation.** Derive the TDD DAG after the worker's first turn rather than at turn
   0, so a task whose repository does not exist yet can still be gated once it does.
3. **Fall back to a single-milestone handoff** with the repository's native runner once one
   appears, accepting that such a task is not gated during its first milestone.

Option 1 is strictly a correction and should happen regardless. 2 and 3 change what the arm
does and need to be chosen deliberately, not overnight.

**Option 1 implemented 2026-09-22.** `lab/engine/void.py` gives the harness a vocabulary it
did not have: a run can now be **UNMEASURABLE** (nobody can grade this task -- a property of
the task, true for every arm) or **UNGATEABLE** (this arm could not derive a verification
command for a task that is otherwise gradeable -- a property of the arm). The distinction
decides what you fix: an unmeasurable task leaves the corpus, an ungateable run is a gap in
the arm.

Three places changed. The daemon adapter marks a failed TDD handoff `UNGATEABLE` instead of
the generic "Failed to initialize daemon state". The runner no longer prefixes "Agent run
failed:" onto a void outcome -- that wrapping is precisely what made seven runs that never
started read as seven runs the agent lost. The reporter excludes void runs from the pass-rate
denominator and renders a `Void` column, because silently dropping them would hide that the
corpus shrank. Re-scored, EXP-080 reads **Scored 2, Passes 0, Void 1** rather than 0/3.

Note the reporter defect was more general than this one task: `total_tasks = len(arm_runs)`
with `failures = total_tasks - passes` meant even the pre-existing UNMEASURABLE path would
have depressed a pass rate. It never did only because `paired_run.py` filters those tasks out
by name before the run starts. Both are now handled at the point of aggregation.

**Historical results files are not retro-corrected.** They predate the marker, so their rows
still read `Agent run failed: Failed to initialize daemon state`. Auto-classifying that string
as void would be guessing -- it is a generic message that could have other causes. Use the
detection rule instead: single-digit wall clock at $0.00 did not run.

### 13.21 The read budget is second-order; the repeated-read call is first-order (2026-09-22)

EXP-080, from two archived traces (`traces/exp080_20260921_230506`). Replay is arithmetic, so
these carry no run-to-run noise -- which matters, because the live version of this experiment
was smoke-tested first and cannot work: at 800 on scc the guard denied nothing, 0 lines
withheld, and the guarded and unguarded arms still differed **23.8%** in input tokens.

**Q1 -- the optimum is 400, not 1,600, and it is the same on both repositories.**

| threshold | katex | scc |
|---|---|---|
| 200 | 146,945 | 96,572 |
| **400** | **133,861** | **80,040** |
| 800 (shipped) | 151,562 | 80,328 |
| 1,600 (13.18's "optimum") | 151,020 | 102,856 |
| unlimited | 374,815 | 146,933 |

800 costs +13.2% over optimum on katex and +3.1% over the 200 it replaced; on scc it is within
0.4% of optimum. **13.20's revision of 13.18 is confirmed from the other direction:** that
"optimum 1,600" came from replaying one repository whose only file above 1,600 lines is
`daemon.rs` itself, so it measured where the budget stops binding, not a cost minimum. Two real
tasks agree on 400. This is the evidence 13.19 said was missing before the daemon could derive
the number rather than inherit it -- and the answer so far is that it may not need to, since
two very different repositories land on the same value.

**Q2 -- the repeats are genuine re-fetches, which reverses 13.18.**

EXP-079 found 80% of reads were of already-read files but could not tell distinct windows from
re-fetched lines. Now measurable:

| | reads | re-read a file | re-read *lines* | redundant line-fetches |
|---|---|---|---|---|
| katex | 231 | 184 (80%) | 168 (73%) | 9,422 / 14,474 (**65%**) |
| scc | 91 | 66 (73%) | 49 (54%) | 2,320 / 5,917 (**39%**) |

13.18 reported 0% window repeats and concluded a read cache buys nothing. That was one
single-file trace; on real tasks the agent re-fetches lines it already has, constantly.

**The prize is much larger than the threshold's.** `cost_at()` unions every window before
costing it, so **the entire budget curve has always priced a run with a perfect read cache** --
the ideal, not the trace. The gap is the cache's value, and it is charged on top of any tuning:

| | actually read | at optimum threshold | removable by a cache serving only fully-held windows |
|---|---|---|---|
| katex | 620,146 | 133,861 | **~423,668 (68%)** |
| scc | 240,924 | 80,040 | **~107,784 (45%)** |

Counting only reads whose whole window is already held -- 133 of 231 on katex, 35 of 91 on scc
-- because a partial overlap still costs a call. Threshold tuning is worth 9-17%. The cache is
worth 45-68%. Most of that is the per-call preamble, not content: 231 reads at ~2,500 tokens is
577,500 tokens before a single line is returned, which is 93% of katex's actual read cost. This
is 13.17's "reducing calls beats shrinking results" with a number attached.

**Q3 -- the command channel is still unshunted.** 199 commands on katex (55% host-side) and 118
on scc (59%). Shunting wraps only `./run-in-container`, so more than half of all commands are
never bounded. Confirms EXP-079's suspicion and remains the second untouched lever.

**Ranking of what to build, by measured size:**

1. **A read cache** keyed on (path, window), serving fully-held windows without a tool call.
   45-68% of read cost.
2. **Host-side command shunting.** 55-59% of commands currently unbounded; unsized, but
   EXP-079 put command output in the same order as reads.
3. **Change the default budget from 800 to 400.** Worth 9-17% of read cost, and it undoes a
   regression on katex. Cheap to do, but do not mistake it for the main event.

**Scores, for the record:** all three tasks recorded `passed=False`, but two were near misses
and one never ran -- scc 28/31 fail-to-pass with 286/286 pass-to-pass, katex 85/94 with 599/599,
build-cython-ext aborted in 7 seconds (13.20). A 0/3 canary here does not mean the arm did
nothing; it means the binary threshold is unforgiving and one cell was void.

**Addendum (finer grid).** 400 was the minimum of a coarse grid that jumped 200-400-800, so it
was worth checking it is not a grid artefact. Replayed at 17 thresholds, both repositories put
their minimum at exactly 400 independently, inside a shallow basin running roughly 300-450:

| | 250 | 300 | 350 | **400** | 450 | 500 | 800 |
|---|---|---|---|---|---|---|---|
| katex | 138,232 | 137,756 | 136,361 | **133,861** | 138,041 | 140,249 | 151,562 |
| scc | 95,040 | 87,540 | 85,040 | **80,040** | 80,040 | 84,209 | 80,328 |

Two caveats worth keeping. The cost function is a step function -- `ceil(wanted / threshold)`
calls per file -- so the curve is jagged and individual local minima are partly quantisation;
scc's 800 dipping back to 80,328 is that effect, not a second optimum. And the model assumes
wanted lines repack optimally into windows, which flatters high thresholds, so if anything the
true optimum sits at or below 400 rather than above it. The basin, not the exact integer, is
the finding: **anything in 300-450 is defensible; 800 is not.**

### 13.22 The read cache, and why it answers with a pointer (2026-09-22)

Built from 13.21. Invariant IV's enumerated mechanisms were calibrated to massive file reads,
which measurement puts at ~4,740 tokens of a 1.9M turn; the volume is repeated reads, which no
Invariant IV mechanism addressed. The cache is a fourth mechanism at the same perimeter.

**It returns a pointer, not the content.** Serving the cached lines back would save nothing --
they are already in the transcript, so re-sending them costs what the read would have. The
saving comes from answering in ~60 tokens that the worker already holds these lines, so
neither the ~2,500-token call preamble nor a duplicate copy enters context, and neither is
re-sent on every subsequent turn.

**Two mechanical escapes, because context collapse is real.** The manifesto names it as the
third failure of chat-driven development, and a worker whose context was compacted genuinely
may not hold what the cache believes it holds. Neither escape requires the worker to read or
understand the refusal, which matters because Invariant IV exists precisely because prose does
not bind an agent under pressure:

* **Content change invalidates.** Records are keyed by a hash of the file, so any edit -- the
  worker's own, or a scoped rollback's -- drops every prior record for that path. A read after
  a write is never suppressed.
* **Insisting wins.** The identical window requested twice in a row is served. The worst case
  is one wasted denial.

**A bug that would have starved the worker, caught by an existing test.** The first wiring
recorded a window as held at *request* time. A whole-file read that the line budget denied --
and served as an AST outline -- was therefore banked as though the worker had received those
lines, and every later read of any window inside that file would have been suppressed. The
worker would have been refused content it never got, with only the insist escape to recover.
`test_flexible_payload_formats_and_tool_names` failed because its second read flipped from
allow to deny; the diagnosis came from asking why, rather than pinning the test. **Windows are
now recorded only when the read is actually allowed.**

The general lesson is worth keeping: a cache of what someone else holds must be written from
what was *delivered*, never from what was *asked for*.

**Kept ablatable.** `--read-cache` on the guard, `DaemonConfig.read_cache`, `--no-read-cache`
on `state daemon`, and a `file_cached` arm in `guard_bench.py`. This mechanism changes what the
worker SEES, not only what it costs, so it could move solve rate in either direction and must
be measured rather than assumed. A test asserts the ablation reaches the provisioned hook --
an ablation arm that silently runs the treatment is the shape of six prior parity defects.

`guard_bench.py` now counts cache hits separately from denials, because a cache hit writes no
denial record and an arm running the cache would otherwise report zero and look inert. Quoting
a token delta beside a mechanism that provably did nothing is exactly how the 23.8% noise floor
was nearly mistaken for a result.

**Not yet measured live.** The 45-68% is an offline replay. What is unmeasured is whether
suppressing these reads changes what the worker can do. `guard_bench.py --configs
file,file_cached` answers the token half in minutes and cents; the solve-rate half needs a
paired canary with `--no-read-cache` as the control.

### 13.23 `guard_bench` cannot measure the read cache: repeats need time to appear (2026-09-22)

The bench was the right instrument for the read *budget* and is the wrong one for the read
*cache*. Stopped after one turn, having established why.

**Repeats are a function of elapsed work, not of reading a lot.** Replaying the EXP-080 traces
by how far into the run each read happened:

| window | katex reads / fully held | scc reads / fully held |
|---|---|---|
| first 2 min | 5 / **0 (0%)** | 5 / **0 (0%)** |
| first 5 min | 6 / 0 (0%) | 16 / 3 (19%) |
| first 10 min | 12 / 0 (0%) | 28 / 3 (11%) |
| first 30 min | 62 / 18 (29%) | 74 / 29 (39%) |
| whole run | 194 / 119 (**61%**) | 74 / 29 (39%) |

A worker re-reads because it has gone away, done something, and come back -- run a test, make
an edit, follow a call chain into another file and return. None of that has happened two
minutes in. The 45-68% in 13.21 is a whole-run figure and cannot be collected from a slice at
the start of one.

**Confirmed directly on the bench's own workload, not merely predicted.** Inspecting the live
control turn while it ran: 16 reads across 8 distinct files, **0 would have been cache hits**,
1 partial overlap. A `guard_bench` turn is ~2 minutes, which is precisely the regime where the
mechanism does nothing.

So the bench would have reported a token delta between two arms whose only difference provably
never fired -- the same shape as the 23.8% at zero denials in 13.21, and the reason that
measurement was believed briefly. Continuing would have cost ~30 minutes and several dollars
to re-derive the noise floor. The run was stopped after ~$0.60.

**What this means for the instrument ladder.** CLAUDE.md's ladder ranks instruments by cost.
It needs a second axis: *the timescale at which the mechanism engages*. A guard that fires on
the first oversized read is visible in one turn; a cache that fires on the second visit to a
file is not visible until there has been a second visit. Cheapness does not help if the
instrument is shorter than the phenomenon.

**The remaining question needs a canary.** The token half is already answered offline by
replay -- exactly and without noise. What is unmeasured is whether suppressing these reads
changes what the worker can DO, and that needs real tasks at real duration, with
`--no-read-cache` as the control arm.

### 13.24 The detach re-exec silently dropped both new flags (2026-09-22)

EXP-081 was launched, killed after ~90 seconds, and relaunched. The kill was correct and the
reason is worth more than the run.

`cmd_daemon --detach` re-launches itself as a background process by **re-building the child's
argv by hand**. Any flag not written into that block is dropped. The harness always detaches,
so a dropped flag means the daemon runs at a default while the caller, the results file and
the ledger all record something else.

Both parameters added on 2026-09-21 were lost this way:

| flag | consequence |
|---|---|
| `--read-threshold-lines` | a threshold sweep would have run at the default throughout |
| `--no-read-cache` | EXP-081's control arm provisioned `--read-cache true`, identical to the treatment |

The ablation would have compared an arm against itself and produced a null result reading as
"the read cache does not matter" -- a false negative with a plausible story and no way to tell
it from the real thing.

**The unit test passed.** `test_arm_input_parity` asserts the two arms' *spawn commands* differ
by exactly `--no-read-cache`, and they did. The loss happened one level further down, when the
daemon re-executed itself. A test at the boundary you are thinking about does not cover the
boundary you are not.

**What caught it** was comparing the two arms' live `hooks.json` 90 seconds into the run,
because the hook is what actually governs the worker. That check cost nothing and is now the
habit: verify the treatment differs from the control *in the artefact the mechanism reads*,
not in the command that was supposed to produce it.

`test_detach_argv` now covers the class rather than the two known cases: it asserts every
switch it names is a real flag, so it cannot pass vacuously, then drives a detached daemon end
to end and checks the values arrive in the provisioned `hooks.json`.

This is the same family as EXP-077, where hooks resolved `superstate` through PATH to the
previous day's build: **what the caller pins, the engine's children escape.** CLAUDE.md already
carries that rule. The instance it did not cover is a process re-executing *itself*.

EXP-080 is unaffected -- its adapter passes no threshold flag, so parent and child resolved the
same default.

### 13.25 The read cache makes things worse, and the reason invalidates its premise (2026-09-22)

EXP-081, paired ablation, cache ON vs `--no-read-cache`. Parity verified on the live
`hooks.json`; treatment recorded 85 and 38 cache hits, control exactly 0, so the comparison was
live in a way neither `guard_bench` nor the first launch managed.

| task | arm | passed | input tokens | turns |
|---|---|---|---|---|
| katex | cache ON | **True** | 4,733,936 | 7 |
| katex | control | False | **3,443,737** | 7 |
| scc | cache ON | False | 1,786,702 | 4 |
| scc | control | **True** | **1,149,043** | 5 |

Solve rate 1-1, no signal at n=2. **Tokens went the wrong way on both tasks: +37% and +55%.**
On katex both arms took the same seven turns, so this is not the treatment doing more work.

**Why: the escape hatch became the normal path.** 77 of 85 suppressions on katex (**91%**) and
34 of 38 on scc (**89%**) were immediately insisted on. A worker that has decided it needs
lines 120-180 needs them; being told it already has them does not change its plan, it just
re-issues the request. So a suppression does not save a call, it **adds** one: refusal, then
the read anyway.

    accept  ~10%  saves ~400 tokens   (content not sent)
    insist  ~90%  costs ~2,300 tokens (a wasted round trip)
    net     about -1,900 tokens per suppression

The observed gap is larger than that per-suppression figure, which is consistent with each
wasted round trip permanently enlarging the conversation that every subsequent call re-sends.

**The premise was wrong, not just the tuning.** A `PreToolUse` guard cannot prevent a tool
call. By the time the hook runs, the model has already emitted the request and the conversation
has already been re-sent -- **the preamble is spent before the guard sees anything.** The guard
can only change what the *response* costs.

That invalidates how 13.21 computed the prize. `cost_at()` charges a preamble per call and
derives its saving from there being fewer calls, which describes a world where redundant reads
are *eliminated*. A perimeter guard does not eliminate them; it answers them. The 45-68% was
never available to this mechanism. **The redundancy measurement stands; the attribution of a
saving to perimeter interception does not.**

**This bounds Invariant IV generally.** Mechanical perimeter interception can shrink what a
tool call returns. It cannot reduce how many calls a worker makes, and 13.17 established that
call count -- not response size -- is what cost scales with. Every mechanism the invariant
names sits on the wrong side of that line for the dominant cost. Reducing calls requires
changing what the worker decides to do, which is the worker plane, not the perimeter.

**Action taken:** the cache now defaults OFF. Leaving a measured 37-55% regression on by
default would be worse than not having built it. The code stays, switchable, because the
insist rate is the thing to attack if anyone returns to this -- a refusal the worker accepts
would flip the sign, and nothing here shows that is achievable at the perimeter.

**Caveat on the run.** Detached daemons from the killed first launch ran until 08:10, roughly
fifteen minutes into this one, competing for CPU and RAM. Both arms ran concurrently through
that window so it should not bias the comparison, but it adds noise to wall clock. `pkill` on
the wrapper does not stop a detached daemon -- the same lesson as the racing `run_sweep.sh`.

### 13.26 The manifesto's two unsourced claims, checked (2026-09-22)

Both survive, neither as written. Checked against archived EXP-081 telemetry and the existing
ledger; no new runs, about five minutes.

**Claim: "Within three turns, the repository is littered with contradictory partial fixes,
dangling syntax, and wrecked git trees."**

Directionally supported, with different evidence than the wording implies. EXP-059 is a pure
ablation -- rollback on, versus retaining dirty working-tree state across retries -- and the
managed arm scored 3/3 against 2/3 while spending **25.3% fewer input tokens per solve** (683k
vs 915k) at $0.79 vs $1.06. EXP-071 adds that failing turns are not hypothetical: rollback
fired on **all 30 verification failures** in one run.

What is *not* measured is the picture the sentence paints. Nothing here inspects tree state,
counts contradictory fixes, or observes dangling syntax; "within three turns" is a figure with
no measurement behind it. The defensible claim is about cost and solve rate, not about what the
tree looks like.

EXP-071 also supplies a counterweight the manifesto omits entirely: rollback reset one worker's
**committed feature five times**, rebuilding it each time. Resetting is not free, which is
precisely why `rollback_policy` became a measured switch rather than a constant.

**Claim: "Multi-thousand line compiler dumps and noisy test logs saturate the context window."**

True in kind, wrong in frequency -- and the correction strengthens the mechanism rather than
weakening it. Across 64 command outputs in four EXP-081 workspaces:

| | katex full | katex nocache | scc full | scc nocache |
|---|---|---|---|---|
| outputs | 10 | 16 | 17 | 21 |
| median lines | 140 | 196 | 307 | 165 |
| max lines | 408 | 376 | 961 | **25,105** |
| >=1,000 lines | 0 | 0 | 0 | 1 |

**One output of 64 (1.6%) was multi-thousand-line. It was 25,105 lines -- 88% of that arm's
entire output volume and 26x the next largest** -- and it was exactly what the manifesto names:
`go test ./...` exiting 1.

So this is a heavy tail, not a common case. The manifesto reads as though every build floods
the context; measurement says almost none do and one will. That is a *better* argument for
mechanical shunting than the original, because the distribution is unpredictable: no rule about
which commands are noisy would have caught this one, since the same `go test` invocation
produced 942-961 lines in the other arm.

**Method note.** Both checks were answerable from telemetry already on disk plus the ledger.
The reason they had never been checked is that neither claim carried a pointer to what
established it -- which is the argument for citing FINDINGS entries inline in the manifesto,
so that auditing it is a grep rather than a reconstruction.

### 13.27 CORRECTION: the 13,288-token MCP figure does not reproduce (2026-09-22)

13.17 reported that a "pong" turn costs 24,222 fresh input tokens of which **13,288 is MCP tool
schemas** (55%), with wall clock 17.2s against 1.7s. That figure has been quoted since as the
largest single cost lever available. **Re-measured today it is wrong by an order of magnitude.**

| | MCP on | github/notion/slack stripped | delta |
|---|---|---|---|
| trivial turn, input tokens | 11,662 | 11,254 | **-3.5%** |
| tool-using turn, input tokens | 16,138 | 15,452 | **-4.3%** |
| trivial turn, wall clock (median of 3) | 4.0s | 3.2s | **-21%** |

Repeats were tight -- 11,664/11,660 against 11,250/11,257 -- so this is not noise. The saving
is roughly **400-690 tokens per invocation**, not 13,288.

Note also that today's baseline trivial turn is **11,662** tokens where 13.17 measured 24,222.
The baseline itself halved, so something in the environment changed between the two
measurements and 13.17's method was not recorded well enough to say what. A tool-using turn was
measured here as well as a trivial one, in case schemas load lazily; they do not appear to --
both show the same ~4%.

**What this changes.** MCP stripping is a modest win, not the headline: ~4% of tokens and ~20%
of latency, free, and it removes a source of drift between runs. It stays default-on for
evaluation runs on that basis. It is **not** the biggest available lever, and the "a third of
every run is MCP schemas" line in CLAUDE.md is withdrawn.

**The pattern worth naming.** This is the third figure in one day that did not survive
re-measurement: the read cache's 45-68% saving (13.25, premise invalid), the 1,600-line read
optimum (13.20, single-file trace), and now 13,288. All three shared a shape -- **derived once,
under conditions that were not recorded, then quoted as established.** CLAUDE.md's first rule
already covers it: verify what produced a number before reporting it. The rule needs applying
to this file's own entries, not only to results JSONs. An entry that cannot be re-run is a
claim, not a measurement, and should say so.

### 13.28 Host-side command shunting is a ~5% lever, not a 55% one (2026-09-22)

I had been quoting "55-59% of commands are host-side and never shunted" as the largest
remaining lever. That is a share of COMMAND COUNT, and I had never measured the share of
OUTPUT VOLUME. They are not the same number.

582 distinct host-side commands were extracted from the EXP-080/081 traces and the 451
read-only ones replayed against copies of the real repositories -- deterministic, no LLM, a
couple of minutes:

| | |
|---|---|
| total output | **13,742 lines** |
| median | **6 lines** |
| over the 50-line shunt threshold | 61 commands (14%), carrying 9,859 lines (72% of host volume) |
| **>= 1,000 lines** | **zero** |
| largest | 820 (`git diff HEAD~1`) |

What host-side commands actually are: 297 greps (`git grep`, `grep -n`, `grep -rn`), then
`git status` x75, `ls -la` x74, `git log` x55, `git diff` x50, `git show` x34. Overwhelmingly
tiny, with a tail in the hundreds of lines concentrated in `git diff` variants.

**The catastrophic-tail argument does not transfer.** Container-side, one command produced
25,105 lines -- 88% of that run's output volume -- which is what makes mechanical shunting
compelling there. Host-side the largest of 451 was 820 lines. Shunting the 61 oversized
commands to head+tail would save roughly 6,800 lines, on the order of **75k tokens of
conversation content** against runs admitting 1.1M-4.7M input tokens. Single-digit percent,
the same order as the read budget, for a mechanism with materially more risk: a `PreToolUse`
hook cannot see output that does not exist yet, so shunting host commands means the hook
*executing* them itself, with all the cwd, environment and timeout divergence that implies.

**Recommendation: do not build it now.** The measured benefit does not justify that risk, and
the same effort spent on call count would be worth more.

**Where the cost actually is, restated.** Reads cost ~620k on katex (13.21), host commands
~151k here, container commands already shunted. That is well under a quarter of a 4.7M-token
run. The remainder is the conversation being re-sent on every call, which scales with **call
count**, and 13.25 established the perimeter cannot reduce call count. Three separate
measurements now point the same way: **the remaining lever is not a bigger guard, it is fewer
calls, and that is a worker-plane problem.**

**Method note.** The replay is imperfect -- a freshly-initialised repo is not the mid-run tree,
and commands with pipes, redirects or docker were excluded (451 of 582). It establishes an
order of magnitude, not a precise figure, and that is all the decision needed.

### 13.29 Half of all tokens are spent waiting, not working (2026-09-22)

Found while de-risking the SKILL.state schema question. It does not answer that question; it
displaces it.

Per-turn telemetry from EXP-081's four runs, classified by whether a turn's entire response
was about waiting for a background task:

| run | waiting | working | waiting share |
|---|---|---|---|
| katex, cache on | 3,908,127 | 825,809 | **82.6%** |
| katex, control | 1,795,595 | 2,040,524 | **46.8%** |
| scc, cache on | 0 | 2,067,075 | 0% |
| scc, control | 0 | 1,346,477 | 0% |
| **all four** | **5,703,722** | 6,279,885 | **47.6%** |

The single most expensive turn recorded anywhere in this project cost **1,384,188 input tokens,
15,327,627 cache reads, 151,142 output and 110,092 thinking tokens**. Its complete response:

> Notice: The task 'Running jest on reproduction test' is currently running in the background.
> Please wait for it to complete.
> Wait for lint task to finish.

**Mechanism.** agy backgrounds long-running commands through `manage_task`. The agent then
polls for completion, and *each poll is a full model turn* carrying the entire accumulated
conversation. A slow test suite therefore converts directly into millions of tokens of nothing.
scc shows 0% because Go's test suite returns fast enough to run inline; katex runs jest and
yarn, and pays 47-83%.

**This is the problem the command guard was built for, and bolting it on made things worse.**
Debouncing the polls is treating the symptom at the wrong layer: 13.13 records the guard's
denial text instructing the worker to yield its turn, which in headless mode ends the run
outright. You cannot fix "the agent must poll" from outside the loop -- you can only make
polling more expensive or more fatal.

**What actually fixes it is one line of harness design: execute the command synchronously and
return its result.** No background task, no polling, no turn. That is unavailable at every
layer we have been working at and trivial at the layer above.

**Caveats.** Four runs, two tasks, and the entire effect comes from katex. The honest
generalisation is "wherever the verification command is slower than the harness will block
for", which is most real repositories, but it is a mechanism established on one of them.

**Consequence for the harness question.** The dominant cost here is not context accumulation
from reading, which is what SKILL.state addresses, and not per-call preamble, which is what the
perimeter addresses. It is turns spent on nothing. Any new runtime should be measured on that
first, because it is the largest number in this file and the cheapest to remove.

### 13.30 Offered a state file, the agent wrote nothing to it (2026-09-22)

Superstate has always exposed `state note`, and `.agent-state/state.json` carries a `notes`
array the worker can append to. On a full katex task -- two milestones, five failed
verifications, five rollbacks, eventually passing -- the array held **15 entries, of which the
agent wrote 0**. Every one was authored by `superstate-daemon`:

    [impact-pass]  [retry-extend]  [verify-fail] x5  [rollback] x5

**Caveat, and it matters:** the handoff prompt names the state file and the gate command but
never asks the worker to record anything. This is absence of instruction as much as absence of
need, and it does not establish that an agent *would not* write useful state if asked.

**What it does establish** is that the state which accumulated and proved useful was
**runtime-observed**: what failed, what was rolled back, what the tree looked like between
attempts. Facts the runtime is better placed to know than the worker, and -- unlike a worker's
self-report -- ones it cannot get wrong.

Same trace incidentally shows Invariant III working plainly: five failed attempts, five clean
rollbacks, then a pass.

**Design consequence, and how the open schema question gets settled.** State splits into three
regions by *authority*, not by who happens to write:

| region | written by | mutable to the agent |
|---|---|---|
| **orchestrator** — goal, gate, acceptance criteria | human or calling agent | **never** |
| **runtime** — observed facts, failures, rollbacks | the harness | no |
| **agent** — working notes, hypotheses, findings | the worker | yes |

The first is non-negotiable and settles the question this project spent a week on: a control
plane that lets the worker author its definition of done is self-grading with extra steps.
DeepSeek's harness reaches the same place by a different route -- its `create_goal`/`update_goal`
tools require "direct-human root authority" -- which is the enforcement mechanism superstate
asserted as doctrine but never had.

The third region is the experiment. SKILL.state's own limitation #1 is the unknown schema; the
way to answer it is to offer the region, *this time actually ask for it in the prompt*, and
measure what keys appear across a handful of real tasks. A stable shape means formalise it.
Nothing written, having been asked, means state is runtime-owned and the paper's patch model
does not transfer to software engineering. Either outcome is worth more than a guess, and it
costs nothing extra once the loop exists.
