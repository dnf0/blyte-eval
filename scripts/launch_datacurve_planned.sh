#!/bin/bash
# EXP-055: the product as designed, against the configuration everything was measured on.
#
# superstate_mcp_planned uses zero_turn_planning=False: the driver writes a plan, milestones
# are parsed from it, require_decomposition refuses to run undecomposed, each milestone carries
# its own verify_cmd, and the adapter advances via state_ready -- so it walks the dependency
# graph rather than file order. That arm has been in the registry since 09-12 and appears in
# 0 of 309 recorded runs.
#
# Run on the 9 datacurve tasks, where the single-milestone arm lost to vanilla (23-27% against
# 43%) and where pooled history favours decomposition (anko 100% vs 33%, httpx 100% vs 44%).
#
# Concurrency 2: datacurve containers are capped at 8 GB and the governor now sizes from that.
# EXP-053 ran at 5 under the old flat assumption and lost 12 of 54 runs to starved workers.
set -euo pipefail
cd /Users/danielfisher/repos/superstate-eval

exec .venv/bin/python scripts/paired_run.py \
  --tier1 \
  --arms vanilla superstate_mcp superstate_mcp_planned \
  --model gemini-3.8-flash-high \
  --repeats 2 \
  --concurrency 2 \
  --out results/datacurve_planned_9tasks.json
