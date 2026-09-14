#!/usr/bin/env bash
set -eo pipefail

cd /Users/danielfisher/repos/superstate-eval

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ========================================================"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Rerunning superstate_agent_mcp on 30 Tasks (Condition A Revert)"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ========================================================"

# Restore held-out test seals
uv run python3 -c 'from lab.sandbox.answer_key import AnswerKeyGuard; AnswerKeyGuard().restore_all()'

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting evaluation of 30 tasks on superstate_agent_mcp..."

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
  --arms superstate_agent_mcp \
  --driver agy \
  --model gemini-3.8-flash-high \
  --repeats 1 \
  --concurrency 4 \
  --out results/frontier_mcp_30tasks.json \
  2>&1 | tee -a results/frontier_mcp_30tasks.log

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Evaluation finished. Merging with baseline runs..."
uv run python3 scripts/merge_frontier_results.py

echo "[$(date '+%Y-%m-%d %H:%M:%S')] All done! Merged results in results/frontier_triad_30tasks_reverted.json"
