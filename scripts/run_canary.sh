#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Default arms if not provided via arguments
if [ $# -eq 0 ]; then
  ARMS=(superstate_daemon_review superstate_mcp)
elif [ $# -eq 1 ]; then
  # Allow passing space-separated arms in a single quoted argument or single arm
  # shellcheck disable=SC2206
  ARMS=($1)
else
  ARMS=("$@")
fi

STAMP=$(date +"%Y%m%d_%H%M%S")
OUT_FILE="results/canary_${STAMP}.json"

echo "Starting SWE-Canary evaluation on 3 tri-language repository tasks (build-cython-ext, scc-bounded-memory-spilling, katex-multicolumn-array-spans)"
echo "Arms: ${ARMS[*]}"
echo "Governor concurrency limit: 2"
echo "Model: gemini-3.8-flash-high"
echo "Driver: agy"
echo "Output: ${OUT_FILE}"

.venv/bin/python scripts/paired_run.py \
  --arms "${ARMS[@]}" \
  --canary \
  --driver agy \
  --model gemini-3.8-flash-high \
  --concurrency 2 \
  --out "${OUT_FILE}"
