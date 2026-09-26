#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Default harnesses if not provided via arguments
if [ $# -eq 0 ]; then
  HARNESSES=(agy "blyte[folded]")
elif [ $# -eq 1 ]; then
  # Allow passing space-separated harnesses in a single quoted argument or single harness
  # shellcheck disable=SC2206
  HARNESSES=($1)
else
  HARNESSES=("$@")
fi

STAMP=$(date +"%Y%m%d_%H%M%S")
OUT_FILE="results/canary_${STAMP}.json"

echo "Starting SWE-Canary evaluation on 3 tri-language repository tasks (build-cython-ext, scc-bounded-memory-spilling, katex-multicolumn-array-spans)"
echo "Harnesses: ${HARNESSES[*]}"
echo "Governor concurrency limit: 2"
echo "Model: gemini-3.8-flash-high"
echo "Output: ${OUT_FILE}"

.venv/bin/python scripts/paired_run.py \
  --harnesses "${HARNESSES[@]}" \
  --canary \
  --model gemini-3.8-flash-high \
  --concurrency 2 \
  --out "${OUT_FILE}"
