#!/usr/bin/env bash
set -eo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ========================================================"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Frontier Handoff Pilot Benchmark: Solo vs Relay vs Daemon"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ========================================================"

# Ensure any held-out tests left sealed by previously aborted runs are restored.
uv run python3 -c 'from lab.sandbox.answer_key import AnswerKeyGuard; AnswerKeyGuard().restore_all()'

mkdir -p results

exec uv run python3 scripts/paired_run.py \
  --tasks \
    fastapi-deprecation-response-headers \
    build-cython-ext \
    sqlite-db-truncate \
    db-wal-recovery \
    openssl-selfsigned-cert \
  --arms superstate_solo superstate_relay superstate_daemon \
  --driver agy \
  --model gemini-3.8-flash-high \
  --repeats 1 \
  --concurrency 3 \
  --out results/frontier_handoff_pilot_5tasks.json \
  "$@" \
  2>&1 | tee -a results/frontier_handoff_pilot_5tasks.log
