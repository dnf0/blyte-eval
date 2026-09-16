#!/bin/bash
# EXP-053: the 9 datacurve/tier-1 tasks across all three arms.
#
# Two decisions ride on this, which is why it is one run and not two:
#
#   1. Can the lift claim be made? The effect interval is [0,+32]pp. Six of these nine tasks
#      hold no prior superstate result, so they cannot have been selected on outcome -- the
#      only clean evidence obtainable.
#   2. Does superstate_daemon still equal superstate_mcp once the loop fires? ADR 0002 makes
#      the daemon the default on an equivalence measured where neither arm iterated (1 worker
#      invocation in 19 of 20 runs). Datacurve is the first place the gate has rejected work.
#
# Task-default budget (5400s): clamping it has floored every arm before.
set -euo pipefail
cd /Users/danielfisher/repos/superstate-eval

exec .venv/bin/python scripts/paired_run.py \
  --tier1 \
  --arms vanilla superstate_mcp superstate_daemon \
  --model gemini-3.8-flash-high \
  --repeats 2 \
  --concurrency 5 \
  --out results/datacurve_3arm_9tasks.json
