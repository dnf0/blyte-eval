#!/bin/bash
set -euo pipefail

# EXP-065: Adversarial Code Review Control Plane Canary Evaluation
# Testing superstate_daemon_review vs superstate_mcp on the 3-task Canary slice

cd "$(dirname "$0")/.."

.venv/bin/python scripts/paired_run.py \
    --canary \
    --arms superstate_daemon_review superstate_mcp \
    --concurrency 2 \
    --out results/canary_review_v_mcp_exp065.json

