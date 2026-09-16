# Experiment ledger

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
| `WITHDRAWN` | the verdict was wrong — usually a harness bug, not a real finding. **Leave the row in.** Three daemon findings were withdrawn; deleting them would have let each be rediscovered |
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
| EXP-050 | - | **how much of the lift is `superstate state prompt` itself** | vanilla, vanilla+state_prompt, superstate_mcp | 60 | all OFF | - | Not run. `vanilla.py` has never referenced `state_prompt` in any commit; EXP-039 tested a *different* text | PLANNED |

## Cross-cutting findings

Derived from the runs above rather than from a run of their own.

* **The lift is not the gate.** Across 55 live paired runs (EXP-021, EXP-041, EXP-049) the
  verification command handed to `superstate_mcp` was literally `true` for 22 of 30 tasks, and
  the margin holds there: vanilla 31/48, mcp 40/48. On the 18 tasks mcp wins and vanilla loses,
  **15 of vanilla's failures are "declared done, graded wrong"**, at $0.069 median spend against
  the $0.187 it spends on tasks it solves. It quits early and confidently.
* **The lift is not iteration, decomposition, or time.** Worker invocations are 1; milestones
  planned is 1 in 70/70; mcp uses 23% of its granted budget where vanilla uses 36%.
* **What remains is the handoff text.** `superstate state prompt` emits role framing, a goal
  restatement, the verification command and five rules including "HARD STOP UPON PASSING" — from
  the Rust binary, so `SUPERSTATE_EVAL_PROMPT_CONTRACTS=0` does not remove it. EXP-050 is the
  control that would size it.
* **Gate strength is the binding constraint.** In EXP-047, `merge-diff-arc-agi-task` and
  `sanitize-git-repo` passed their gates on every turn and still failed the sealed grader.
