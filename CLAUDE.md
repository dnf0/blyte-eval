# Working in superstate-eval

## Terminology — use these exact words

Two different things are both called "contract" in conversation. They are not related, and
conflating them has produced wrong conclusions.

| Term | Means | In code |
|---|---|---|
| **verification command** | the shell command whose exit code decides whether a milestone is complete | `verify_cmd`, `TaskSpec.verification_cmd`, `GATE_FIXTURES` |
| **gated / ungated** | whether that command *can* fail. `true`, `:`, `exit 0` are **ungated** | `is_vacuous_gate()` (Rust), `NOOP_GATE_RE` |
| **prompt contract** | the injected behavioural rules ("zero global exploration", "hard stop upon passing") | `TARGETED_EXECUTION_CONTRACT`, `prompt_contracts.py` |
| **sealed grader** | the held-out verifier at container-root `/tests/` that decides pass/fail | `extractor.py` |

Never say "contract" unqualified. Say *verification command* or *prompt contract*.

A package's own suite at `/app/<pkg>/tests/` is **not** the sealed grader. Match the grader
by path position (`references_sealed_grader()`), never by substring.

## Arms — check the name before comparing anything

The benchmark's Condition labels map to specific arm names. Getting this wrong invalidates
a comparison silently, and has.

| Arm | Condition | Loop driven by | Turns |
|---|---|---|---|
| `vanilla` | Baseline 1 | nothing — single shot | conversational |
| `superpowers` | Baseline 2 | nothing | conversational |
| `superstate_agent_mcp` | **Condition A** | the *agent*, in-loop via JSON-RPC | conversational *by design* |
| `superstate_mcp` | **Condition B** — the arm that scored 76% | the *harness*, over stdio MCP | stateless |
| `superstate_daemon` | (post-ADR-0002) | the Rust `DaemonRunner`, detached | stateless |
| `superstate_solo` | alias of `superstate_rust_inplace`/`_fast` | Python turn loop over the CLI | stateless |

`superstate_solo` and `superstate_daemon` are **not** Condition B. Only `superstate_mcp` is.

Condition B arms must never thread `conversation_id` — zero-turn injection is the mechanism
the result rests on. See `lab/engine/condition_b.py`.

## Verify before asserting

Every wrong claim in this repo's history came from inferring instead of checking. All are
one command.

- **A claim about a past run**: read the code *at that commit* (`git show <ref>:<path>`), not
  the current file. Several "confounds" found on 2026-09-14/15 were introduced those same days.
- **A flag's meaning**: read `--help`. `--timeout` on `state daemon` bounds each verification
  attempt, not the daemon's lifetime.
- **An arm's identity**: check the arm name against the report, not from memory.
- **A result**: read the results JSON, don't recall it.

## Running evaluations

- **Never request `--concurrency` above the governor's calculated max.** The surplus worker
  starves, times out at 300s, and is recorded as a *task* failure. Check the
  `Calculated concurrency:` log line and stay at or below it.
- **Clear orphan containers and `/tmp/superstate_eval_runs/*` between runs.** Stale workspaces
  consumed 51 GB and throttled the disk governor to 2 workers, producing spurious failures.
- **Watch for `Cost=$0.00` with a wall clock near the budget** — that is a driver turn that hit
  its timeout and lost its usage telemetry, not a cheap run. Raise `--budget-sec`.
- **`sqlite-db-truncate` is unmeasurable** — no verifier ships with it, so its grader exits 127
  for every arm. See `UNMEASURABLE_TASKS`.

## Switches (all default OFF)

| Env var | Effect |
|---|---|
| `SUPERSTATE_EVAL_PROMPT_CONTRACTS` | inject arm-specific prompt contracts (superstate arms only) |
| `SUPERSTATE_EVAL_GENERIC_RULES` | inject the portable discipline rules into baseline arms |
| `SUPERSTATE_EVAL_DERIVE_GATES` | let the daemon author its own verification command |

Defaults measure state management alone. Turning the first on makes any arm-vs-arm
comparison confounded, because baselines have no equivalent.

## Shell

`paired_run.py` invocations belong in a `#!/bin/bash` script. The interactive shell is zsh,
which does **not** word-split unquoted variables, so `--tasks $TASKS` passes the whole list
as one filename.
