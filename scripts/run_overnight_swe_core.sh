#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."
export PYTHONPATH="."

OUT_FILE="results/swe_core_daemon_v_vanilla_exp071.json"
CANARY_OUT="results/canary_control_plane_v_vanilla_exp070.json"

echo "=== EXP-071: Comprehensive Overnight SWE-Core Evaluation (9 Repositories x 3 Repeats x 2 Arms = 54 Runs) ==="
echo "Tasks: SWE_CORE_TASKS (9 canonical repositories)"
echo "Arms: superstate_daemon_full vanilla"
echo "Repeats: 3 per arm (54 total runs)"
echo "Driver: agy"
echo "Model: gemini-3.8-flash-high"
echo "Concurrency: 2"
echo "Output: ${OUT_FILE}"

# Wait for active EXP-070 Canary evaluation to finish (target: 6 runs)
echo "Checking status of active EXP-070 Canary evaluation..."
while true; do
  if [ -f "${CANARY_OUT}" ]; then
    COUNT=$(.venv/bin/python -c "import json; print(len(json.load(open('${CANARY_OUT}'))))" 2>/dev/null || echo 0)
    if [ "${COUNT}" -ge 6 ]; then
      echo "EXP-070 complete with ${COUNT} runs."
      break
    else
      echo "EXP-070 in progress: ${COUNT}/6 runs completed. Waiting 30s..."
    fi
  else
    echo "Waiting for ${CANARY_OUT} to be created... (30s)"
  fi
  sleep 30
done

echo "Pre-flight hygiene: Pruning orphan docker containers and freeing memory..."
docker ps -q --filter "ancestor=alexgshaw/*" 2>/dev/null | xargs -r docker rm -f 2>/dev/null || true

export SUPERSTATE_BIN="/Users/danielfisher/repos/superstate/target/release/superstate"

echo "Starting full 54-run overnight benchmark..."
.venv/bin/python scripts/paired_run.py \
  --arms superstate_daemon_full vanilla \
  --core \
  --repeats 3 \
  --driver agy \
  --model gemini-3.8-flash-high \
  --concurrency 2 \
  --out "${OUT_FILE}"

echo "Overnight run complete. Results saved to ${OUT_FILE}."
