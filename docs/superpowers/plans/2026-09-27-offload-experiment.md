# Offload Experiment: Claude Code Alone vs Claude Code + blyte — Plan

> **For agentic workers:** Tasks 1–3 are implementation tasks, one per dispatch, shadow-run (blyte vs agy). Do NOT `git push`, open PRs, start any benchmark or paid run, or call any model API; commit locally only. Do not edit `FINDINGS.md`, `EXPERIMENTS.md`, `CLAUDE.md`/`AGENTS.md` or `results/`. Task 4 is **HUMAN-approved only**: it spends money on two providers.

**Question:** if a frontier model plans and reviews and hands implementation to blyte on a cheaper
model, what does a task cost, how long does it take, and how often does it pass, compared with the
same frontier model doing the whole task itself in Claude Code?

**Why (2026-09-27):** blyte's docs now promote this pattern ("offload implementation from a
frontier model"). The existing evidence compares blyte with agy, both driven by Claude; it says
nothing about the saving against Claude doing the work alone. The docs say so, and this experiment
is what would let them carry a number.

## Design

- **Arms** (one Claude model for both, chosen at run time; `claude-sonnet-5` suggested):
  - **A: `claude`**, Claude Code alone (the existing harness).
  - **B: `claude+blyte[gemini-3.8-flash-high]`**, Claude Code as orchestrator with one extra tool,
    `dispatch_blyte`, that runs blyte inside the task's container on the named implementer model.
    Claude still has `run_in_container` for exploring and reviewing, so arm B is a superset of A:
    the question is whether Claude chooses to delegate and whether that pays.
- **Tasks:** the 9 DeepSWE tasks of FrontierHarness v1.0 (real repositories, held-out tests,
  objective grading; blyte alone on Gemini already has results for them).
- **Conditions:** agent offline (as FrontierHarness), graded by the held-out tests as today;
  interleaved order (A1 B1 A2 B2 …); one attempt per task per arm; the same wall-clock limit.
- **Measured per run:** pass/fail and target-test counts; wall time; **frontier cost** (Claude
  Code's `total_cost_usd`); **implementer cost** (sum of blyte reports' `cost_usd`); total cost;
  number of `dispatch_blyte` calls and their outcomes.
- **Estimated spend:** Claude about $2–6 per task per arm on Sonnet (unmeasured; FrontierHarness
  publishes no per-task cost for this model), so roughly $40–110 for 18 runs, plus under $10 of
  Gemini. Opus would cost several times more.
- **Honest limits, to be stated with the result:** 9 tasks, one attempt each (a 2-task difference
  is noise); one orchestrator prompt; one pair of models. A null or negative result is a result
  and goes in the docs too.

---

### Task 1: `dispatch_blyte` in the container MCP server

**Files:** `lab/engine/drivers/container_exec_mcp.py`, `tests/test_dispatch_blyte_tool.py` (new).

The server gains a second tool, listed only when the environment variable
`BLYTE_IMPLEMENTER_MODEL` is set:

- name `dispatch_blyte`; input `{task: string (required), gate: string (required), max_seconds: integer (optional, default 1200)}`.
- Behaviour: run `blyte --container <id> --container-workdir <workdir> --model $BLYTE_IMPLEMENTER_MODEL --gate <gate> --rollback=false --max-seconds <max_seconds> --report <reports_dir>/dispatch-<n>.json -- <task>` on the host (blyte talks to the model; its commands run in the container). `<reports_dir>` is `$BLYTE_DISPATCH_DIR` (required when the tool is enabled); `<n>` counts from 1.
- Returns JSON text: `{outcome, gate_attempts, gate_failures (each cut to 1,000 chars), turns, cost_usd, seconds, report}` from the report, or `{outcome: "error", error}` if blyte could not run.
- The blyte binary is `$BLYTE_BIN` or `blyte` on `PATH`. The model's API key is inherited from the environment and never echoed.
- Description text for the model: "Hand one well-specified implementation task to blyte, a cheaper implementer model working in this same container. It edits files, runs commands, and stops when `gate` (a shell command, e.g. the relevant test command) exits 0 or its budget runs out. Returns the outcome and any gate failures. You remain responsible for the result: review the changes with run_in_container afterwards."

Tests (mock `subprocess.run`; no real blyte, no network): the tool is absent without
`BLYTE_IMPLEMENTER_MODEL`; present with it; the argv contains `--container`, the model, the gate,
`--rollback=false` and a report path under `BLYTE_DISPATCH_DIR`; a report on disk is summarised;
a missing report gives `outcome: error`; `gate_failures` are cut to 1,000 characters.

Commit: `feat(eval): a dispatch_blyte tool lets an orchestrating agent hand tasks to blyte in the task container`

### Task 2: the `claude+blyte[<model>]` harness

**Files:** `lab/engine/harnesses.py`, `lab/engine/drivers/claude_cli.py`, `tests/test_offload_harness.py` (new).

- `parse_harness_spec("claude+blyte[gemini-3.8-flash-high]")` → `("claude+blyte", ["gemini-3.8-flash-high"])`; exactly one option (the implementer model) is required.
- `build_harness` returns a `ClaudeCliDriver` with `implementer_model=<option>`: its MCP server is started with `BLYTE_IMPLEMENTER_MODEL` and a per-run `BLYTE_DISPATCH_DIR` (inside the run's report directory), and it appends `OFFLOAD_SYSTEM_PROMPT` after the container prompt.
- `OFFLOAD_SYSTEM_PROMPT` (constant in `claude_cli.py`): "You can delegate implementation to `dispatch_blyte`. Do the understanding, planning and review yourself; hand well-specified implementation work to blyte with a precise task (files, expected behaviour, the tests that must pass) and a gate command that checks it. Review what it changed before you finish. Doing work yourself is allowed when delegating would not help."
- Telemetry: `extra` gains `frontier_cost_usd` (Claude's cost), `implementer_cost_usd` (sum over `BLYTE_DISPATCH_DIR/*.json`), `dispatches` (count) and `dispatch_outcomes` (list); `cost_usd` is their sum. The harness name recorded is `claude+blyte`.
- The existing `claude` harness is unchanged.

Tests: spec parsing (valid, missing option, two options); the driver's argv/env for both arms (the plain `claude` arm has no `BLYTE_*` variables); cost aggregation from two fake dispatch reports.

Commit: `feat(eval): a claude+blyte harness: Claude Code orchestrates, blyte implements`

### Task 3: frontier and implementer cost in the comparison

**Files:** `lab/engine/harnesses.py` (`render_harness_comparison`), its test file.

Add columns `frontier $` and `implementer $` (from `extra`, blank when absent) and a `dispatches`
column to the harness comparison table. Existing columns and their order are unchanged.

Commit: `feat(eval): the harness comparison splits frontier and implementer cost`

### Task 4 (HUMAN approval required): the run

After tasks 1–3 merge, and only with the user's go-ahead on model and budget:

```bash
# One task at a time, both arms interleaved, as the FrontierHarness run did (each task's image is
# pulled before its run and removed after it). Offline comes from each task's network_mode.
for t in <the 9 DeepSWE task dirs>; do
  uv run python scripts/paired_run.py --task "$t" --concurrency 1 \
    --harnesses claude "claude+blyte[gemini-3.8-flash-high]" --model <claude model> \
    --out "results/offload-<date>/$(basename "$t").json"
done
```

Then a write-up in superstate `docs/research/` with per-task results, costs split by model,
and the limits above, and the docs' "not measured yet" note replaced by the result, whichever way
it goes.
