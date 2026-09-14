#!/usr/bin/env bash
set -eo pipefail

cd /Users/danielfisher/repos/superstate-eval

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ========================================================"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Frontier Claude Haiku Benchmark: 25 Executable Tasks"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ========================================================"

# Ensure any held-out tests left sealed are restored
uv run python3 -c 'from lab.sandbox.answer_key import AnswerKeyGuard; AnswerKeyGuard().restore_all()'

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Launching 25-Task 3-Arm Evaluation under Claude Haiku:"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] - Arms: vanilla vs. superpowers vs. superstate_mcp"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] - Driver: claude (/Users/danielfisher/.local/bin/claude)"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] - Model: haiku (Claude 3.5 Haiku)"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] - Output: results/frontier_claude_haiku_25tasks.json"

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
    multi-source-data-merger \
    openssl-selfsigned-cert \
    polyglot-c-py \
    python-statemachine-state-data-scoping \
    regex-log \
    scc-bounded-memory-spilling \
    sqlite-db-truncate \
    vulnerable-secret \
  --arms vanilla superpowers superstate_mcp \
  --driver claude \
  --model haiku \
  --repeats 1 \
  --concurrency 3 \
  --out results/frontier_claude_haiku_25tasks.json
