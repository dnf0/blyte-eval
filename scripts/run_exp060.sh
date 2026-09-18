#!/bin/bash
set -euo pipefail

cd /Users/danielfisher/repos/superstate-eval

# Ensure all switches default to 0 / clean state
export SUPERSTATE_EVAL_PROMPT_CONTRACTS=0
export SUPERSTATE_EVAL_GENERIC_RULES=0
export SUPERSTATE_EVAL_DERIVE_GATES=0

# Core 14 benchmark: superstate_daemon_full vs superstate_mcp
.venv/bin/python scripts/paired_run.py \
    --core \
    --arms superstate_daemon_full superstate_mcp \
    --concurrency 2 \
    --out results/daemon_full_v_mcp_core14_exp060.json
