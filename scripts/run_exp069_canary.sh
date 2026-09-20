#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."

OUT_FILE="results/canary_integrated_build_cython_ext_exp069.json"

echo "=== EXP-069: Canary Verification of Fully Integrated Control Plane on build-cython-ext ==="
echo "Tasks: build-cython-ext"
echo "Arms: superstate_daemon_full"
echo "Driver: agy"
echo "Model: gemini-3.8-flash-high"
echo "Concurrency: 1"
echo "Output: ${OUT_FILE}"

export SUPERSTATE_BIN="/Users/danielfisher/repos/superstate/target/release/superstate"

.venv/bin/python scripts/paired_run.py \
  --arms superstate_daemon_full \
  --tasks build-cython-ext \
  --driver agy \
  --model gemini-3.8-flash-high \
  --budget-sec 450 \
  --concurrency 1 \
  --out "${OUT_FILE}"
