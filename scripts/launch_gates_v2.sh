#!/bin/bash
# EXP-051: the 8 tasks whose gates false-passed in EXP-047, with the gates rewritten.
# Same model, budget and arms as EXP-047 so the two are directly comparable.
# No vanilla: gate precision is measured within the superstate arms, and vanilla has no gate.
set -euo pipefail
cd /Users/danielfisher/repos/superstate-eval

TASKS="dna-insert largest-eigenval log-summary-date-ranges merge-diff-arc-agi-task \
modernize-scientific-stack multi-source-data-merger polyglot-c-py sanitize-git-repo"

exec .venv/bin/python scripts/paired_run.py \
  --tasks $TASKS \
  --arms superstate_daemon superstate_mcp \
  --model gemini-3.8-flash-high \
  --budget-sec 2400 \
  --concurrency 4 \
  --out results/gates_v2_8tasks.json
