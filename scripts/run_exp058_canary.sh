#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Export deterministic rollback switch
export SUPERSTATE_EVAL_AUTO_ROLLBACK=1

ARMS=(superstate_daemon_review superstate_mcp)
OUT_FILE="results/canary_rollback_v_mcp_exp058.json"

echo "=========================================================="
echo "Starting EXP-058: Canary 3 with Deterministic Rollback"
echo "Arms: ${ARMS[*]}"
echo "Switches: SUPERSTATE_EVAL_AUTO_ROLLBACK=1"
echo "Tasks: Canary (build-cython-ext, chess-best-move, httpx-multipart-response-parsing)"
echo "Model: gemini-3.8-flash-high"
echo "Concurrency: 2"
echo "Output: ${OUT_FILE}"
echo "=========================================================="

.venv/bin/python scripts/paired_run.py \
  --arms "${ARMS[@]}" \
  --canary \
  --driver agy \
  --model gemini-3.8-flash-high \
  --concurrency 2 \
  --out "${OUT_FILE}"
