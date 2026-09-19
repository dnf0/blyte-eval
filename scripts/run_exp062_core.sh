#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."

OUT_FILE="results/daemon_full_shunt_v_mcp_core14_exp062.json"

echo "=============================================================================="
echo "Starting EXP-062: Core 14 Tasks with Shunt Layer"
echo "Arms: superstate_daemon_full superstate_mcp"
echo "Governor concurrency limit: 2"
echo "Model: gemini-3.8-flash-high"
echo "Driver: agy"
echo "Output: ${OUT_FILE}"
echo "=============================================================================="

.venv/bin/python scripts/paired_run.py \
  --core \
  --arms superstate_daemon_full superstate_mcp \
  --driver agy \
  --model gemini-3.8-flash-high \
  --concurrency 2 \
  --out "${OUT_FILE}"
