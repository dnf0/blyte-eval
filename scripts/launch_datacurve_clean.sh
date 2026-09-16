#!/bin/bash
# EXP-052: the 9 datacurve/tier-1 tasks -- the only place clean evidence is missing.
#
# All 9 ship a sealed grader, and 8 of the 14 discriminating tasks in the corpus live here.
# Every existing contracts-off datacurve run is WITHDRAWN (the -low model floored all arms),
# leaving exactly one pairable task.
#
# vanilla is included deliberately: new task set, unmeasured difficulty, and a lift claim at
# stake -- all three of the conditions under which a control earns its cost.
# Task-default budget (5400s): clamping it has floored every arm before.
set -euo pipefail
cd /Users/danielfisher/repos/superstate-eval

exec .venv/bin/python scripts/paired_run.py \
  --tier1 \
  --arms vanilla superstate_mcp \
  --model gemini-3.8-flash-high \
  --repeats 2 \
  --concurrency 5 \
  --out results/datacurve_clean_9tasks.json
