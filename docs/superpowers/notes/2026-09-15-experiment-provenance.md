# Experiment provenance: what the 2026-09-13 benchmark actually ran

Verified against the code at the commits in use (`62be86c`, `f2edbd1`, `2beec91`), because
several "confounds" identified on 2026-09-14/15 turned out to have been introduced on those
same days rather than being present at the benchmark.

## Constant gates, not moving ones

```python
# lab/engine/adapters/superstate.py @ 2beec91
if vcmd and ("/tests/" in vcmd or vcmd.startswith("bash /tests")):
    vcmd = None
effective_vcmd = vcmd if vcmd and vcmd.strip() else "true"
```

The agent-facing gate was deterministically `"true"` once the sealed `/tests/` verifier was
stripped. Per-run LLM gate derivation did not exist; it was added 2026-09-14. The "spec is a
random variable" problem therefore applies only to 09-14/15 runs, not to the benchmark.

## Stateless solo, not conversational

`conversation_id` occurrences in `superstate.py`:

| commit | date | count |
|---|---|---|
| `62be86c` | 09-13 | 0 |
| `f2edbd1` | 09-13 | 0 |
| `2beec91` | 09-13 | 0 |

`f2edbd1` ("make milestone gate retries stateless with diff-stat diagnostics") landed
*before* the Condition B launch script. Conversation threading appeared after the benchmark
and was removed again in `f74e7af`. Condition B as benchmarked was genuinely zero-turn.

## The confound that is real

`TARGETED_EXECUTION_CONTRACT` (10 behavioural rules, added 2026-09-09) and
`AUTONOMOUS_MCP_EXECUTION_CONTRACT` were applied to superstate arms only. `vanilla` and
`superpowers` received no prompt support at all — `vanilla.py` has no prompt construction.

So published lift measured *control plane + hand-tuned prompt* against *neither*.

## The valid comparison

Run `vanilla` **with** prompt support and compare against the banked Condition B numbers.
Prompt support is then the only material difference between the configurations, which is
what makes the comparison interpretable. Half of `TARGETED_EXECUTION_CONTRACT` is scaffolding
for the state machine and cannot be given to a baseline (rule 7 asserts an orchestrator that
does not exist there), so the baseline receives `GENERIC_EXECUTION_RULES` — the five rules
that are true and meaningful without one. See `lab/engine/prompt_contracts.py`.
