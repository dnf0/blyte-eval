#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."
export PYTHONPATH="."

OUT_FILE="results/canary_control_plane_v_mcp_exp065.json"

echo "=== EXP-065: Tri-Language SWE-Canary Evaluation (Autonomous Control Plane Daemon vs MCP) ==="
echo "Tasks: build-cython-ext (Py/C), scc-bounded-memory-spilling (Go), katex-multicolumn-array-spans (TS)"
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
