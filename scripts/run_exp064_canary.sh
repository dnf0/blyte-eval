#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."

OUT_FILE="results/canary_impact_slicing_v_mcp_exp064.json"

echo "=== EXP-064: Canary Evaluation (Autonomous Daemon with Test Impact Slicing vs MCP) ==="
echo "Tasks: build-cython-ext, chess-best-move, httpx-multipart-response-parsing"
echo "Arms: superstate_daemon_full superstate_mcp"
echo "Driver: agy"
echo "Model: gemini-3.8-flash-high"
echo "Concurrency: 2"
echo "Output: ${OUT_FILE}"

.venv/bin/python scripts/paired_run.py \
  --arms superstate_daemon_full superstate_mcp \
  --canary \
  --driver agy \
  --model gemini-3.8-flash-high \
  --concurrency 2 \
  --out "${OUT_FILE}"
