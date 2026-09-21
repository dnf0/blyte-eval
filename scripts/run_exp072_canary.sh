#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."

# EXP-072: did the rollback and telemetry fixes take effect in a live run?
#
# Mechanism verification, not a solve-rate claim -- n=3 cannot separate 2/3 from 3/3.
# Decision: if [rollback] notes still appear on every verification failure, the fix did
# not take and no larger run follows. See FINDINGS.md 13.2 and 13.9.
#
# SUPERSTATE_BIN is pinned deliberately: `superstate` on PATH resolves to
# ~/.cargo/bin/superstate, a different and older build.
export SUPERSTATE_BIN="/Users/danielfisher/repos/superstate/target/release/superstate"

OUT_FILE="results/canary_rollback_fix_exp072.json"

echo "EXP-072 SWE-Canary: build-cython-ext (Py/C), scc-bounded-memory-spilling (Go), katex-multicolumn-array-spans (TS)"
echo "Arm: superstate_daemon_full   Binary: ${SUPERSTATE_BIN}"
echo "Output: ${OUT_FILE}"

.venv/bin/python scripts/paired_run.py \
  --arms superstate_daemon_full \
  --canary \
  --driver agy \
  --model gemini-3.8-flash-high \
  --concurrency 2 \
  --out "${OUT_FILE}"
