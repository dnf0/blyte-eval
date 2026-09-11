#!/usr/bin/env bash
# scripts/run_weekend_benchmark.sh
# -----------------------------------------------------------------------------
# Launches the 132-run over-weekend benchmark suite:
#   - 22 tasks (all tasks with verified held-out test suites)
#   - 3 arms: vanilla, superpowers, superstate_rust
#   - 2 repeats per task/arm
#   - Concurrency: 4 workers
#   - Incremental results output: results/weekend_run_20260912.json
#   - OS notify-on-exit wrapper upon completion
# -----------------------------------------------------------------------------

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

LOG_FILE="results/weekend_run_20260912.log"
RESULTS_JSON="results/weekend_run_20260912.json"
DONE_FILE="results/weekend_run_20260912.done"

mkdir -p results

echo "=================================================================="
echo "Starting Superstate Over-Weekend Benchmark"
echo "Start Time: $(date)"
echo "Tasks: 22 tasks with held-out verifiers"
echo "Arms: vanilla superpowers superstate_rust (2 repeats each)"
echo "Concurrency: 4 workers"
echo "Results JSON: $RESULTS_JSON"
echo "Log File: $LOG_FILE"
echo "=================================================================="

# Function to send OS notification on exit
notify_completion() {
    EXIT_CODE=$?
    END_TIME=$(date)
    echo "=================================================================="
    echo "Benchmark finished with exit code $EXIT_CODE at $END_TIME"
    echo "=================================================================="
    echo "exit_code=$EXIT_CODE" > "$DONE_FILE"
    echo "finished_at=$END_TIME" >> "$DONE_FILE"

    if [ $EXIT_CODE -eq 0 ]; then
        osascript -e 'display notification "Superstate 132-run weekend benchmark completed successfully!" with title "Superstate Benchmark Finished"' 2>/dev/null || true
    else
        osascript -e 'display notification "Superstate weekend benchmark failed with code '$EXIT_CODE'!" with title "Superstate Benchmark Failed"' 2>/dev/null || true
    fi
}

trap notify_completion EXIT

uv run python scripts/paired_run.py \
    --only-with-verifier \
    --arms vanilla superpowers superstate_rust \
    --repeats 2 \
    --concurrency 4 \
    --out "$RESULTS_JSON" 2>&1 | tee "$LOG_FILE"
