#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."

# EXP-073: first execution of the autonomous TDD DAG.
#
# Does `tdd-reproduction-test` ever complete -- can the worker author a reproduction test
# that compiles AND fails -- and does the DAG advance to `fix-implementation`?
# Decision: if RED never completes, autonomous TDD is not viable as the default.
#
# Pin a SNAPSHOT of the binary, never the live build path.
#
# `superstate` on PATH is ~/.cargo/bin/superstate, an older build -- and target/release is
# what `cargo build` overwrites. EXP-073's first attempt pinned the latter and was rebuilt 12
# minutes in, so nothing it measured could be attributed to a known build. It was withdrawn.
eval "$(scripts/pin_superstate_binary.sh)"

OUT_FILE="results/canary_guard_fix_exp077.json"

echo "EXP-077 TDD canary: build-cython-ext (native runner), scc (Go TDD), katex (TS TDD)"
echo "Binary: ${SUPERSTATE_BIN}"
echo "Output: ${OUT_FILE}"

.venv/bin/python scripts/paired_run.py \
  --arms superstate_daemon_full \
  --canary \
  --driver agy \
  --model gemini-3.8-flash-high \
  --concurrency 2 \
  --out "${OUT_FILE}"
