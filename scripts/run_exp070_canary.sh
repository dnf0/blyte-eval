#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."
export PYTHONPATH="."

OUT_FILE="results/canary_control_plane_v_vanilla_exp070.json"

echo "=== EXP-070: Tri-Language SWE-Canary Evaluation (Autonomous Control Plane Daemon vs Vanilla) ==="
echo "Tasks: build-cython-ext (Py/C), scc-bounded-memory-spilling (Go), katex-multicolumn-array-spans (TS)"
echo "Arms: superstate_daemon_full vanilla"
echo "Driver: agy"
echo "Model: gemini-3.8-flash-high"
echo "Concurrency: 2"
echo "Output: ${OUT_FILE}"

export SUPERSTATE_BIN="/Users/danielfisher/repos/superstate/target/release/superstate"

.venv/bin/python scripts/paired_run.py \
  --arms superstate_daemon_full vanilla \
  --canary \
  --driver agy \
  --model gemini-3.8-flash-high \
  --concurrency 2 \
  --out "${OUT_FILE}"
