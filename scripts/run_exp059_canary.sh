#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."

ARMS=(superstate_daemon_review superstate_daemon_rollback)
OUT_FILE="results/canary_rollback_ablation_exp059.json"

echo "=========================================================="
echo "Starting EXP-059: Canary 3 Deterministic Rollback Ablation"
echo "Arms: ${ARMS[*]}"
echo "Switches: all OFF (arms configure auto_rollback explicitly)"
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
