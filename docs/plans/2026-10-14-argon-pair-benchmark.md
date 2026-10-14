# Plan: Argon pair benchmark, eval side

The spec is in the blyte repository, at `docs/specs/2026-10-14-argon-pair-benchmark.md`.
- Arm A: `blyte+blyte:vertex/gemini-4-argon`.
- Arm B: `blyte+blyte:gemini-3.8-flash-high`.
- Arm C: `blyte`.

All three run in one invocation with `--model vertex/gemini-4-argon`, since harnesses in a run share a model, and that model is the orchestrator.

Task E1 is independent. Task E2 builds against blyte's new `--orchestrate -- "<prompt>"` and `--dispatch-cmd`
(blyte plan Task HO1). Its tests use a stub binary, so it does not need that release to pass.

### Task E1

**Goal:** blyte runs report their real cost. Today Argon runs report $0.00.

**Where:**
- `lab/engine/drivers/blyte_native.py`, around lines 327-336, prices tokens with `estimate_cost_usd` from `agy_cli.py`.
- `MODEL_PRICING` in `lab/engine/drivers/agy_cli.py` (around line 33) has no `gemini-4-argon`, so it logs a warning and returns 0.0.

**Change:**
- In `BlyteNativeDriver`, use the report's `cost_usd` when it is a number, since blyte prices fresh, cached, output and thinking tokens itself. Fall back to `estimate_cost_usd` only when it is missing or null.
- Add a `cost_source` metric, `"report"` or `"estimate"`.
- Add `gemini-4-argon`, and its `vertex/` form if the lookup is by exact key, to `MODEL_PRICING`. Use blyte's prices: input 2.00, output 10.00, cached 0.10 per million tokens, in the table's tuple order.

**Tests** (`tests/test_blyte_native_driver.py`, `tests/test_agy_cli_driver.py`):
- a report with `cost_usd: 1.23` gives `cost_usd == 1.23` and `cost_source == "report"`;
- a report with no cost falls back to the estimate;
- an Argon model is priced at more than zero.

### Task E2

**Goal:** a `blyte+blyte:<implementer-model>` harness. blyte orchestrates on the run's `--model`, and dispatches implementers on `<implementer-model>` into the same task container.

**Where:**
- `lab/engine/harnesses.py`:
  - `parse_harness_spec` (around line 49 handles `claude+blyte` and `codex+blyte`, with one required option);
  - `build_harness` (around line 95);
  - the "known harnesses" error message.
- `lab/engine/drivers/container_exec_mcp.py`: `ContainerExec.dispatch(task, gate, max_seconds)` (around line 262) already copies the workdir, runs blyte in the container, and merges the result back.
  - It reads `BLYTE_EVAL_CONTAINER`, `BLYTE_IMPLEMENTER_MODEL`, `BLYTE_DISPATCH_DIR` and `BLYTE_BIN` from the environment.
- `lab/engine/drivers/claude_cli.py`: `_aggregate_dispatches` (line 101), and how it sets the dispatch environment (around lines 205-225) and sums `frontier_cost_usd` and `implementer_cost_usd` (around line 337). Copy that pattern; do not change the Claude driver's behaviour.
- `lab/engine/drivers/blyte_native.py`: `build_command` (line 225) and how a run reads its report.

**Change:**
1. A new module, `lab/engine/drivers/dispatch_hook.py`, runnable as `python -m lab.engine.drivers.dispatch_hook`.
   - It reads one JSON object `{task, gate, max_seconds?}` from stdin and calls `ContainerExec().dispatch(...)`.
   - It prints the returned JSON text to stdout, and exits 0, or 1 when `is_error` is true.
   - All configuration comes from the environment variables above.
2. A new driver, `BlytePairDriver`, in a new file `lab/engine/drivers/blyte_pair.py`. Reuse `BlyteNativeDriver` by subclassing or composing it, rather than copying it.
   - Its argv is `blyte --orchestrate --model <model> --container <id> --container-workdir /app --max-seconds <timeout> --report <path> --dispatch-cmd "<sys.executable> -m lab.engine.drivers.dispatch_hook" -- <prompt>`.
   - Never pass `--gate`.
   - Run it with the dispatch environment set: the container, the implementer model, a per-run dispatch dir, and `BLYTE_BIN`.
3. Telemetry:
   - `cost_usd` is the orchestrator's report `cost_usd` plus the sum of the dispatch reports.
   - Metrics are `frontier_cost_usd`, `implementer_cost_usd`, `dispatches`, `dispatch_outcomes`, and `implementer_wall_clock_secs`, the sum of the dispatch reports' `wall_clock_secs`.
   - `success` is decided the same way as for other drivers. The sealed grader decides pass or fail, so do not treat the orchestrator's outcome as verified.
4. `parse_harness_spec` accepts `blyte+blyte` with exactly one implementer-model option. `build_harness` refuses non-Gemini run models, mirroring the Claude and Codex checks.

**Tests:**
- Harness parsing for `blyte+blyte:gemini-3.8-flash-high`; missing or extra options are rejected.
- The driver argv contains `--orchestrate`, `--dispatch-cmd` and `--`, and no `--gate`.
- `dispatch_hook` is fed stdin JSON with `ContainerExec.dispatch` monkeypatched; its stdout and exit code are checked.
- Cost aggregation from a temporary dispatch dir with two report JSONs plus an orchestrator report.
- No test needs Docker or a real blyte.

### Task E3

**Goal:** a per-process spend cap. A runaway run cannot blow the benchmark budget.

**Change:**
- `scripts/paired_run.py` gets `--max-cost USD`, a float, default none. When set, it is exported as the environment variable `BLYTE_EVAL_MAX_COST` for the whole run.
- Every blyte process the eval starts passes `--max-cost <value>` when `BLYTE_EVAL_MAX_COST` is set, and nothing when it is unset. blyte already supports `--max-cost <USD>`: the run stops before a model call once that is spent. The processes are:
  - `BlyteNativeDriver.build_command` (`lab/engine/drivers/blyte_native.py`, around line 225), which covers the solo arm;
  - `BlytePairDriver.build_command` (`lab/engine/drivers/blyte_pair.py`), which covers the orchestrator;
  - the dispatch argv in `ContainerExec.dispatch` (`lab/engine/drivers/container_exec_mcp.py`, around line 311), which covers each implementer.
- The cap is per process. A pair run's worst case is the orchestrator cap plus the cap times the number of dispatches. Say so in the `--max-cost` help text.
- Read the value in one small helper, so the three call sites stay consistent, and reject a non-positive value.

**Tests:**
- Each of the three argv builders includes `--max-cost 2.5` when `BLYTE_EVAL_MAX_COST=2.5`, and omits it when the variable is unset. Use monkeypatched environment variables, with no Docker and no real blyte.
- The `paired_run` argument is parsed and exported.

### Task E4

**Goal:** every dispatch in a pair run keeps its own report, so pair costs are complete; and
each run records whether blyte exited on its own.

**Bug:** `dispatch_hook` builds a new `ContainerExec` per call, and `ContainerExec.dispatch`
(`lab/engine/drivers/container_exec_mcp.py`, around lines 328-340) numbers reports from the
instance's `self.dispatch_count`, which starts at 0 in each process. Every dispatch writes
`dispatch-1.json` and `dispatch-1.events.log` and reuses the copy dir `blyte-dispatch-1`, so
each dispatch overwrites the one before it.

**Change:**
1. In `ContainerExec.dispatch`, choose `n` as the lowest number whose report is not taken in
   `reports_dir`, claimed atomically so two concurrent hooks can't pick the same one (for
   example, create `dispatch-{n}.json` with `os.open(..., O_CREAT | O_EXCL)` in a loop and let
   blyte overwrite it). Use the same `n` for the events log and the copy dir. Keep the
   in-process counter only if something else still needs it.
   - `BlytePairDriver` sums `dispatch_dir.glob("*.json")` (`blyte_pair.py` line 48): make sure
     a claimed-but-empty or unparsable report (a dispatch that crashed) is skipped with a
     warning, not a crash, and still counts as a dispatch.
2. A `clean_exit` metric on blyte runs (`BlyteNativeDriver`, inherited by `BlytePairDriver`):
   true when blyte ended on its own, false when its report's `error` says it was stopped past
   `--max-seconds` (the watchdog message starts with `stopped `) or when the eval killed it.
   Add it next to the existing metrics; don't change `success`.

**Tests** (no Docker, no real blyte):
- Two `ContainerExec` instances (as two hook processes would make) dispatching into the same
  dir, with `_sh` and the blyte call monkeypatched, get report paths `dispatch-1.json` and
  `dispatch-2.json` and different copy dirs.
- Aggregation over a dir with two good reports and one empty file sums the two and counts 3
  dispatches.
- `clean_exit` is false for a report whose `error` starts with `stopped `, true otherwise.
