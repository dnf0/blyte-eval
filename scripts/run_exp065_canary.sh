#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."

OUT_FILE="results/canary_dag_tdd_v_mcp_exp065.json"

echo "=== EXP-065: Canary Evaluation (Autonomous 2-Node TDD DAG Daemon vs MCP) ==="
echo "Tasks: build-cython-ext, chess-best-move, httpx-multipart-response-parsing"
echo "Arms: superstate_daemon_dag superstate_mcp"
echo "Driver: agy"
echo "Model: gemini-3.8-flash-high"
echo "Concurrency: 2"
echo "Output: ${OUT_FILE}"

.venv/bin/python scripts/paired_run.py \
  --arms superstate_daemon_dag superstate_mcp \
  --canary \
  --driver agy \
  --model gemini-3.8-flash-high \
  --concurrency 2 \
  --out "${OUT_FILE}"
