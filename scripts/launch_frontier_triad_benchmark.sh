#!/usr/bin/env bash
set -eo pipefail

cd /Users/danielfisher/repos/superstate-eval

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ========================================================"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Frontier Triad Benchmark: DataCurve 2026 + TerminalBench 2.1"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ========================================================"

# 1. Wait for active run to finish if running
while ps aux | grep -v grep | grep -q "paired_run.py.*weekend_3arm_21tasks"; do
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting for weekend 21-task run to conclude..."
  sleep 30
done

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Previous run concluded. Restoring held-out test seals..."
uv run python3 -c 'from lab.sandbox.answer_key import AnswerKeyGuard; AnswerKeyGuard().restore_all()'

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Launching 30-Task 3-Arm Evaluation:"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] - Tasks: 9 DataCurve 2026 Frontier + 21 TerminalBench 2.1"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] - Arms: vanilla vs. superpowers vs. superstate_agent_mcp"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] - Model: gemini-3.8-flash-high"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] - Concurrency: Dynamic Resource Governor (up to 5 workers)"

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
  --arms vanilla superpowers superstate_agent_mcp \
  --driver agy \
  --model gemini-3.8-flash-high \
  --repeats 1 \
  --concurrency 4 \
  --out results/frontier_triad_30tasks.json \
  2>&1 | tee -a results/frontier_triad_30tasks.log
