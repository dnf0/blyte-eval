#!/usr/bin/env bash
set -eo pipefail

cd /Users/danielfisher/repos/superstate-eval

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ========================================================"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Condition B Benchmark: superstate_mcp (Harness MCP Driver)"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] With Stateless Milestone Retries & git diff --stat Diagnostics"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ========================================================"

# Restore held-out test seals
uv run python3 -c 'from lab.sandbox.answer_key import AnswerKeyGuard; AnswerKeyGuard().restore_all()'

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting evaluation of 30 tasks on superstate_mcp..."

uv run python3 scripts/paired_run.py \
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
    largest-eigenval \
    log-summary-date-ranges \
    merge-diff-arc-agi-task \
    meriyah-explicit-resource-declarations \
    modernize-scientific-stack \
    multi-source-data-merger \
    openssl-selfsigned-cert \
    polyglot-c-py \
    python-statemachine-state-data-scoping \
    regex-log \
    sanitize-git-repo \
    scc-bounded-memory-spilling \
    sqlite-db-truncate \
    vulnerable-secret \
  --arms superstate_mcp \
  --driver agy \
  --model gemini-3.8-flash-high \
  --repeats 1 \
  --concurrency 4 \
  --out results/frontier_mcp_harness_30tasks.json \
  2>&1 | tee -a results/frontier_mcp_harness_30tasks.log

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Condition B 30-task evaluation finished."
