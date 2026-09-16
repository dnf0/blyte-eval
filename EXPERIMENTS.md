# Experiment ledger

**For what the experiments jointly establish, read [FINDINGS.md](FINDINGS.md) first.**
This file is the raw record; that one is the conclusion.

Every evaluation run gets a row **before** it starts. A results file with no row is an
orphan; a row with no results file is a ghost. `scripts/experiments.py check` finds both.

**Ask this file before running anything.** `scripts/experiments.py list <query>` answers
"have we already run this?" in one command. Twice now a run has been proposed that had
already happened, and once a run was proposed that had *not* happened but was believed to
have — both cost more than checking would have.

## Status values

| Status | Means |
|---|---|
| `STANDS` | the verdict is still believed |
| `WITHDRAWN` | the verdict was wrong — usually a harness bug, not a real finding. **Leave the row in.** 13 of the rows below are withdrawn, 9 of them to a single cause (the missing `--print-timeout`); deleting them would have let that be rediscovered run after run |
| `SUPERSEDED` | correct at the time, replaced by a later run |
| `PARTIAL` | the run did not finish; the file is a mid-run snapshot |
| `PLANNED` | registered, not yet run |

## Rules

1. **Register before running.** The question goes in the ledger before the first task starts.
2. **Record the switches.** `SUPERSTATE_EVAL_PROMPT_CONTRACTS`, `_GENERIC_RULES`,
   `_DERIVE_GATES` — all default OFF, and a run with one on is not comparable to one without.
3. **Check completeness when the run ends.** `paired_run.py` saves incrementally, so a killed
   run leaves a plausible partial file. `check` compares row count against declared `n`.
4. **Never delete a withdrawn row.** The withdrawal is the finding.

## Ledger

| id | date | question | arms | n | switches | results | verdict | status |
|---|---|---|---|---|---|---|---|---|
| EXP-001 | 2026-09-11 | early single-task probes; question not recorded at the time | superstate_rust variants | 1 | - | `db_wal_recovery_microturns.json` | superseded by later paired runs | SUPERSEDED |
| EXP-002 | 2026-09-11 | python vs rust engine on one task | superstate_python, superstate_rust_inplace | 2 | - | `db_wal_recovery_paired_python_vs_rust.json` | rust engine adopted | SUPERSEDED |
| EXP-003 | 2026-09-11 | python vs rust engine, second task | superstate_python, superstate_rust_inplace | 2 | - | `git_leak_recovery_paired_python_vs_rust.json` | rust engine adopted | SUPERSEDED |
| EXP-004 | 2026-09-11 | worktree vs in-place execution | superstate_rust | 1 | - | `git_leak_recovery_worktree_eval.json` | in-place adopted | SUPERSEDED |
| EXP-005 | 2026-09-11 | telemetry plumbing check | superstate_rust | 1 | - | `git_leak_recovery_telemetry_v4.json` | plumbing fixed | SUPERSEDED |
| EXP-006 | 2026-09-11 | telemetry, in-place variant | superstate_rust_inplace | 1 | - | `git_leak_recovery_telemetry_rust_inplace_v5.json` | plumbing fixed | SUPERSEDED |
| EXP-007 | 2026-09-11 | transparent worktree variant | superstate_rust | 1 | - | `git_leak_recovery_transparent_worktree_v6.json` | superseded | SUPERSEDED |
| EXP-008 | 2026-09-11 | symlink handling | superstate_rust | 1 | - | `db_wal_rust_symlink.json` | superseded | SUPERSEDED |
| EXP-009 | 2026-09-11 | is superstate faster than vanilla | superstate_rust_inplace, vanilla | 6 | - | `paired_speed_comparison.json` | 2/3 vs 2/3, no signal at n=3 | SUPERSEDED |
| EXP-010 | 2026-09-11 | speed, second attempt | superstate_rust_inplace, vanilla | 4 | - | `paired_speed_round2.json` | no signal at n=2 | SUPERSEDED |
| EXP-011 | 2026-09-11 | can sqlite-db-truncate be measured | superstate_rust_inplace, vanilla | 2 | - | `sqlite_db_truncate_paired.json` | no — grader exits 127 for every arm. See `UNMEASURABLE_TASKS` | STANDS |
| EXP-012 | 2026-09-12 | four-arm sanity check on one task | 4 arms | 4 | - | `db_wal_4arm_rerun.json` | all pass; task too easy to discriminate | SUPERSEDED |
| EXP-013 | 2026-09-12 | rust engine post-fix | superstate_rust | 1 | - | `db_wal_rust_fixed.json` | fix confirmed | SUPERSEDED |
| EXP-014 | 2026-09-12 | in-place rust | superstate_rust_inplace | 1 | - | `db_wal_rust_inplace.json` | confirmed | SUPERSEDED |
| EXP-015 | 2026-09-12 | direct-state timing, git-leak | superstate_rust_fast | 1 | - | `direct_state_git_leak_timing.json` | timing recorded | SUPERSEDED |
| EXP-016 | 2026-09-12 | direct-state timing, openssl | superstate_rust_fast | 1 | - | `direct_state_openssl_timing.json` | timing recorded | SUPERSEDED |
| EXP-017 | 2026-09-12 | openssl rerun | superstate_rust | 1 | - | `targeted_openssl_rerun.json` | passes | SUPERSEDED |
| EXP-018 | 2026-09-12 | terminal-bench tasks usable as fixtures | superstate_rust, vanilla | 4 | - | `targeted_terminal_validation.json` | yes; corpus adopted | STANDS |
| EXP-019 | 2026-09-12 | arm parity on terminal tasks | superstate_rust, vanilla | 4 | - | `terminal_paired_parity_verified.json` | parity confirmed at the time | SUPERSEDED |
| EXP-020 | 2026-09-12 | first broad three-arm sweep | superpowers, superstate_rust, vanilla | 117 | contracts ON | `weekend_run_20260912.json` | vanilla 28/40 led; superstate_rust 19/38. Confounded — contracts were on for superstate only | WITHDRAWN |
| EXP-021 | 2026-09-14 | four-arm normalized comparison, the headline run | vanilla, superpowers, superstate_agent_mcp, superstate_mcp | 120 | contracts ON | `frontier_4arm_normalized_30tasks.json` | mcp 19/30 vs vanilla 13/30. Direction later reproduced with contracts OFF, so the finding survives its confound | SUPERSEDED |
| EXP-022 | 2026-09-14 | does the lift hold on a Claude driver | vanilla, superpowers, superstate_mcp | 31 | contracts ON | `frontier_claude_haiku_25tasks.json` | 2/8 vs 2/14 — driver too weak to discriminate | STANDS |
| EXP-023 | 2026-09-14 | Condition B repeatability | superstate_daemon, superstate_solo, vanilla | 36 | - | `frontier_conditionb_repeats.json` | all three near 9/12; task set too easy | SUPERSEDED |
| EXP-024 | 2026-09-14 | daemon with a gated task set | superstate_daemon | 5 | all OFF | `frontier_daemon_gated_5tasks.json` | 2/5 — confounded by the missing `--print-timeout`; see EXP-046 | WITHDRAWN |
| EXP-024a | 2026-09-14 | daemon, complete-gate variant | superstate_daemon | 5 | all OFF | `frontier_daemon_complete_gate_5tasks.json` | 2/5 — same confound | WITHDRAWN |
| EXP-024b | 2026-09-14 | daemon with a prompt contract | superstate_daemon | 5 | contracts ON | `frontier_daemon_contract_5tasks.json` | 3/5 — same confound | WITHDRAWN |
| EXP-024c | 2026-09-14 | daemon, workspace-fingerprint progress detection | superstate_daemon | 5 | all OFF | `frontier_daemon_fp_5tasks.json` | 3/5 — same confound | WITHDRAWN |
| EXP-024d | 2026-09-14 | daemon, second gate formulation | superstate_daemon | 4 | all OFF | `frontier_daemon_gate2_5tasks.json` | 1/4 — same confound | WITHDRAWN |
| EXP-024e | 2026-09-14 | daemon alone, no comparison arm | superstate_daemon | 5 | all OFF | `frontier_daemon_only_5tasks.json` | 1/5 — same confound | WITHDRAWN |
| EXP-024f | 2026-09-14 | daemon, progress-based lease extension | superstate_daemon | 5 | all OFF | `frontier_daemon_progress_5tasks.json` | 3/5 — same confound | WITHDRAWN |
| EXP-025 | 2026-09-14 | cross-agent handoff pilot | superstate_daemon, superstate_relay, superstate_solo | 15 | - | `frontier_handoff_pilot_5tasks.json` | solo 4/5 led; daemon 2/5 | WITHDRAWN |
| EXP-026 | 2026-09-14 | handoff pilot after merge | superstate_daemon, superstate_relay, superstate_solo | 15 | - | `frontier_handoff_pilot_5tasks_postmerge.json` | daemon 0/5 — the `--print-timeout` bug | WITHDRAWN |
| EXP-027 | 2026-09-14 | Condition A at 30 tasks | superstate_agent_mcp | 30 | contracts ON | `frontier_mcp_30tasks.json` | 14/30 | SUPERSEDED |
| EXP-028 | 2026-09-14 | Condition B at 30 tasks | superstate_mcp | 30 | contracts ON | `frontier_mcp_harness_30tasks.json` | 16/30 | SUPERSEDED |
| EXP-029 | 2026-09-14 | raw gains with contracts off | superstate_daemon, superstate_solo, vanilla | 15 | all OFF | `frontier_raw_gains_5tasks.json` | 2/5, 3/5, 2/5 — n too small | SUPERSEDED |
| EXP-030 | 2026-09-14 | three-arm triad at 30 tasks | superpowers, superstate_agent_mcp, vanilla | 90 | contracts ON | `frontier_triad_30tasks.json` | agent_mcp 16/30 vs vanilla 13/30 | SUPERSEDED |
| EXP-031 | 2026-09-14 | triad, reverted build | superpowers, superstate_agent_mcp, vanilla | 90 | contracts ON | `frontier_triad_30tasks_reverted.json` | agent_mcp 14/30 | SUPERSEDED |
| EXP-032 | 2026-09-14 | four-arm probe on one task | superstate_agent_mcp, superstate_mcp, superstate_rust, vanilla | 4 | contracts ON | `mcp_complete_paired_comparison.json` | all pass; plumbing confirmed | SUPERSEDED |
| EXP-032a | 2026-09-14 | Condition A on build-cython-ext | superstate_agent_mcp | 1 | contracts ON | `mcp_agent_build_cython_ext.json` | passes | SUPERSEDED |
| EXP-032b | 2026-09-14 | Condition A on fastapi | superstate_agent_mcp | 1 | contracts ON | `mcp_agent_fastapi.json` | fails | SUPERSEDED |
| EXP-032c | 2026-09-14 | Condition A on openssl, rerun | superstate_agent_mcp | 1 | contracts ON | `mcp_agent_openssl_rerun.json` | passes | SUPERSEDED |
| EXP-032d | 2026-09-14 | three superstate engines on openssl | superstate_agent_mcp, superstate_mcp, superstate_rust | 3 | contracts ON | `mcp_trio_openssl_comparison.json` | agent_mcp 0/1, others pass | SUPERSEDED |
| EXP-033 | 2026-09-14 | 21-task three-arm | superstate_agent_mcp, superstate_rust, vanilla | 42 | contracts ON | `weekend_3arm_21tasks.json` | rust 12/14, agent_mcp 11/14, vanilla 10/14 | SUPERSEDED |
| EXP-034 | 2026-09-15 | Condition B with contracts off | superstate_mcp | 5 | all OFF | `conditionb_mcp_off.json` | 1/5 — budget floored by `-low` model | WITHDRAWN |
| EXP-035 | 2026-09-15 | fast-model prompting off | superstate_daemon, superstate_solo, vanilla | 12 | all OFF | `fast_prompting_off.json` | 0/4, 2/4, 0/4 — `-low` model floored every arm | WITHDRAWN |
| EXP-036 | 2026-09-15 | does the daemon turn floor help when ungated | superstate_daemon | 20 | all OFF | `ov1_daemon_turnfloor.json` | 10/20 | SUPERSEDED |
| EXP-037 | 2026-09-15 | quick prompting-off check | superstate_daemon, superstate_solo, vanilla | 15 | all OFF | `quick_prompting_off.json` | 1/5 each — n too small | SUPERSEDED |
| EXP-038 | 2026-09-15 | **do the portable discipline rules help vanilla** | vanilla | 9 | all OFF | `scoped_vanilla_plain.json` | baseline 4/9 | STANDS |
| EXP-039 | 2026-09-15 | **do the portable discipline rules help vanilla** | vanilla | 9 | GENERIC_RULES=1 | `scoped_vanilla_rules.json` | **4/9 → 1/9. `GENERIC_EXECUTION_RULES` actively harms vanilla.** Note: this is the *harness's* rules text, NOT `superstate state prompt` — see EXP-044 | STANDS |
| EXP-040 | 2026-09-15 | daemon on terminal-bench, contracts off | superstate_daemon | 20 | all OFF | `tb_daemon_off.json` | 10/20 — still carried the `--print-timeout` bug | WITHDRAWN |
| EXP-041 | 2026-09-15 | **Condition B vs vanilla, contracts off, terminal-bench** | superstate_mcp, vanilla | 40 | all OFF | `tb_off.json` | **mcp 14/20 vs vanilla 9/20** | STANDS |
| EXP-042 | 2026-09-15 | same, contracts on | superstate_mcp, vanilla | 40 | contracts ON | `tb_on.json` | mcp 14/20 vs vanilla 13/20 — contracts help vanilla, not mcp | STANDS |
| EXP-043 | 2026-09-15 | tier1 with contracts off | superstate_daemon, superstate_solo, vanilla | 4 | all OFF | `tier1_contracts_off.json` | 0 across the board; run aborted | PARTIAL |
| EXP-044 | 2026-09-16 | strict gate, clean | superstate_daemon | 10 | all OFF | `adv_a_strict_clean.json` | 10/10 but only 2 distinct tasks — uninformative | STANDS |
| EXP-045 | 2026-09-16 | advisory vs strict gate | superstate_daemon | 15 | advisory_gate | `adv_b_advisory_all.json` | 12/15 over 3 tasks — too few tasks to compare against EXP-044 | STANDS |
| EXP-046 | 2026-09-16 | daemon after the `--print-timeout` fix | superstate_daemon | 15 | all OFF | `daemon_timeout_fixed.json` | 15/15 — the earlier daemon deficits were this bug | STANDS |
| EXP-047 | 2026-09-16 | **daemon vs mcp, all 20 tasks gated, inputs verified identical** | superstate_daemon, superstate_mcp | 40 | all OFF | `daemon_v_mcp_gated20.json` | **12/20 each, disagreeing on zero tasks; daemon $0.25/run vs $0.33.** Real worker invocations: daemon 1 in 19/20, mcp 1 in 16/20 — the iteration loop is dormant, so the tie is by construction | STANDS |
| EXP-048 | 2026-09-16 | gated repeatability | superstate_daemon, superstate_mcp, vanilla | 45 | all OFF | `gated_repeats.json` | 3 tasks all arms pass — too easy to discriminate | STANDS |
| EXP-049 | 2026-09-16 | **Condition B vs vanilla at scale, contracts off** | superstate_daemon, superstate_mcp, vanilla | 120 | all OFF | `ov2_repeats.json` | **mcp 27/40 (67.5%) vs vanilla 18/40 (45%), p=0.037** | STANDS |
| EXP-051 | 2026-09-16 | **do the strengthened gates reject turn-one work, and does solve rate follow** | superstate_daemon, superstate_mcp | 16 | all OFF | `gates_v2_8tasks.json` | 0/8 both arms — but **7 of the 8 tasks have no sealed grader at all** and exit 127. The premise was wrong: these were never gate failures. See the corrected cross-cutting finding below | STANDS |
| EXP-052 | 2026-09-16 | **is the lift real on datacurve, with nothing contaminated** | vanilla, superstate_mcp | 7 | all OFF | `datacurve_clean_9tasks.json` | **stopped at 7 of 36 runs, deliberately** — no decision depended on the significance figure it would have produced. Its one completed task is worth keeping: `anko` went vanilla 0/2, mcp 2/2, with the gate rejecting and the worker iterating to 3 turns — the first time the loop has fired in any run | PARTIAL |
| EXP-053 | 2026-09-16 | **does the effect hold on selection-immune tasks, and do daemon and mcp diverge once the loop fires** | vanilla, superstate_mcp, superstate_daemon | 54 | all OFF | `datacurve_3arm_9tasks.json` | running — supersedes EXP-052. Six of the nine tasks hold no prior superstate result, so they cannot have been selected on outcome. Decides (a) whether the lift claim can be made, the interval being [0,+32]pp, and (b) whether ADR 0002's daemon-equals-mcp finding survives a regime where the loop actually iterates | PLANNED |
| EXP-050 | - | **how much of the lift is `superstate state prompt` itself** | vanilla, vanilla+state_prompt, superstate_mcp | 60 | all OFF | - | Not run. `vanilla.py` has never referenced `state_prompt` in any commit; EXP-039 tested a *different* text | PLANNED |

## Cross-cutting findings

Derived from the runs above rather than from a run of their own.

* **Seven terminal-bench tasks have no sealed grader, and the harness was self-grading them.**
  `largest-eigenval`, `log-summary-date-ranges`, `merge-diff-arc-agi-task`,
  `modernize-scientific-stack`, `multi-source-data-merger`, `polyglot-c-py` and
  `sanitize-git-repo` ship no `tests/` directory. `task_loader` fell back to `pytest tests/`,
  which the harness ran **inside the agent's own container** -- so whatever the agent wrote
  into `tests/` became the grader.

  This was not symmetrical between arms. Over 55 paired runs these tasks went
  **vanilla 0/7, `superstate_mcp` 7/7**, because superstate's handoff prompt asks the worker
  to produce and run a verification command and the baseline gets no such instruction. They
  supplied **7 of the 18 discordant pairs** behind the headline lift. Where the agent wrote no
  `tests/`, the same fallback exited 127 and scored zero for every arm -- so these tasks
  produced spurious passes and spurious failures at once. `extractor.py` now refuses to grade
  them; all eight (with `sqlite-db-truncate`) are in `UNMEASURABLE_TASKS`, and a test fails if
  an ungradeable task is ever left off that list.

* **The lift survives, smaller.** Excluding the ungradeable tasks, across the same paired runs:

  | | n | vanilla | superstate_mcp | mcp-only wins | vanilla-only wins |
  |---|---|---|---|---|---|
  | as previously reported | 55 | 31 (56%) | 47 (85%) | 18 | 2 |
  | **measurable tasks only** | 48 | 31 (65%) | **40 (83%)** | **11** | 2 |

  11-2 on discordant pairs is still significant (sign test p≈0.011), but the margin is
  **+18pp, not +29pp**. Every published figure resting on the larger number is wrong.

* **The corpus holds 14 usable tasks, not 30.** Eight are ungradeable, seven sit at a ceiling
  every arm clears, one at a floor no arm has reached. By family: **datacurve 8 of 9 usable,
  terminal-bench 6 of 21** — the tier-1 repository tasks are where discrimination lives, and
  most of terminal-bench is a ceiling for this driver. That is why both superstate arms scored
  12/13 on the gradeable terminal-bench subset in EXP-047: it is a ceiling, not a gap, and no
  iteration loop can improve on it. Use `paired_run.py --core`; membership and the reason for
  every exclusion are in `lab/benchmarks/task_sets.py`.

* **The lift is not the gate.** The verification command handed to `superstate_mcp` was
  literally `true` for 22 of 30 tasks, and the margin holds there. On the tasks mcp wins and
  vanilla loses, **most of vanilla's failures are "declared done, graded wrong"**, at $0.069
  median spend against the $0.187 it spends on tasks it solves. It quits early and confidently.

* **Gate precision was 92%, not 60%.** An earlier reading of EXP-047 counted the seven
  ungradeable tasks as gate errors. On the 13 tasks that can actually be graded the gate agreed
  with the grader on 12. The gate is not a rubber stamp, and "gate strength is the binding
  constraint" was wrong -- the binding constraint is the corpus, 35% of which cannot be scored.
* **The lift is not iteration, decomposition, or time.** Worker invocations are 1; milestones
  planned is 1 in 70/70; mcp uses 23% of its granted budget where vanilla uses 36%.
* **What remains is the handoff text.** `superstate state prompt` emits role framing, a goal
  restatement, the verification command and five rules including "HARD STOP UPON PASSING" — from
  the Rust binary, so `SUPERSTATE_EVAL_PROMPT_CONTRACTS=0` does not remove it. EXP-050 is the
  control that would size it.
* **Gate strength is the binding constraint.** In EXP-047, `merge-diff-arc-agi-task` and
  `sanitize-git-repo` passed their gates on every turn and still failed the sealed grader.
* **A `vanilla` arm earns its place in two cases only, not four.** It costs 26% of all spend
  ever ($90 of $341) and the diagnostic role once claimed for it does not hold up: of the 13
  withdrawn rows, only **2** included a vanilla arm at all (EXP-020, EXP-035). The other 11
  were caught by reading code, not by a control. Floor and ceiling effects show up in any arm
  — `tier1_contracts_off` at 0 and `quick_prompting_off` at 1/5 need no baseline to look
  wrong, and `gated_repeats` was *not* an undiscriminating set, since `superstate_daemon`
  scored 10/15 on it where the others scored 15/15.

  What a control uniquely provides is the finding that a treatment is **worse than nothing** —
  EXP-020, where vanilla's 28/40 beat `superstate_rust`'s 19/38 and exposed the prompt-contract
  confound. No superstate-vs-superstate comparison can surface that. So run `vanilla` when:

  1. the task set is new and its difficulty is unmeasured;
  2. the driver or model has changed;
  3. a lift is about to be claimed in an ADR or write-up.

  Otherwise omit it. Gate-strength work and daemon-vs-mcp comparisons are measured entirely
  within the superstate arms, where `vanilla` has no gate and contributes nothing. The lift
  itself is banked at EXP-049 and does not need re-measuring.
