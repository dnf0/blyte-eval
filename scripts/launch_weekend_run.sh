#!/usr/bin/env bash
set -eo pipefail

cd /Users/danielfisher/repos/superstate-eval

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ========================================================"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting Weekend 3-Arm Benchmark Orchestrator"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ========================================================"

# 1. Wait for any active single run (like task-10766) to finish
while ps aux | grep -v grep | grep -q "agy.real.*fastapi-deprecation-response-headers"; do
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting for active fastapi run to complete..."
  sleep 15
done

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Active run finished. Ensuring test directories are unsealed..."
uv run python3 -c 'from lab.sandbox.answer_key import AnswerKeyGuard; AnswerKeyGuard().restore_all()'

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Launching Full 3-Arm Paired Benchmark across 21 tasks..."
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Arms: vanilla, superstate_rust, superstate_agent_mcp"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Concurrency: 3 | Driver: agy | Model: gemini-3.8-flash-high"

exec uv run python3 scripts/paired_run.py \
  --tasks \
    anko-typed-variable-bindings \
    arktype-json-schema-refs-dependencies \
    build-cython-ext \
    chess-best-move \
    code-from-image \
    constraints-scheduling \
    db-wal-recovery \
    dna-insert \
    expr-try-catch-errors \
    extract-elf \
    fastapi-deprecation-response-headers \
    gcode-to-text \
    git-leak-recovery \
    httpx-multipart-response-parsing \
    katex-multicolumn-array-spans \
    kv-store-grpc \
    meriyah-explicit-resource-declarations \
    openssl-selfsigned-cert \
    python-statemachine-state-data-scoping \
    regex-log \
    scc-bounded-memory-spilling \
  --arms vanilla superstate_rust superstate_agent_mcp \
  --driver agy \
  --model gemini-3.8-flash-high \
  --repeats 1 \
  --concurrency 3 \
  --out results/weekend_3arm_21tasks.json \
  2>&1 | tee -a results/weekend_3arm_21tasks.log
