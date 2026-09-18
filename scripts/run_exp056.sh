#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "Starting EXP-056: superstate_daemon_review vs superstate_mcp on --core (14 tasks)"
echo "Governor concurrency limit: 2"
echo "Model: gemini-3.8-flash-high"
echo "Output: results/daemon_review_v_mcp_core14.json"

.venv/bin/python scripts/paired_run.py \
  --arms superstate_daemon_review superstate_mcp \
  --core \
  --driver agy \
  --model gemini-3.8-flash-high \
  --concurrency 2 \
  --out results/daemon_review_v_mcp_core14.json
