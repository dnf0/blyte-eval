#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."

OUT_FILE="results/canary_dag_v_mcp_exp063.json"

echo "=== EXP-063: Canary Evaluation (Autonomous DAG Milestone Daemon vs MCP) ==="
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
