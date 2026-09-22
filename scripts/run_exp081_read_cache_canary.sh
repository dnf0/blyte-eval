#!/bin/bash
set -uo pipefail
cd "$(dirname "$0")/.."

# EXP-081: does suppressing a read the worker already holds change what it can DO?
#
# The token half is settled and is NOT what this run is for. Replaying real whole-run traces
# offline puts the read cache at 45-68% of read cost, exactly and without noise (13.21).
#
# What no offline instrument can answer is behavioural. The cache refuses a re-read on the
# grounds that the worker already has those lines -- but context collapse is the third failure
# the manifesto names, and a compacted worker may genuinely no longer hold them. Two escapes
# are designed for that (content-hash invalidation, and serving any window insisted on twice)
# and neither has been under load.
#
# guard_bench cannot substitute: 0% of reads are fully-held repeats two minutes into a run
# against 39-61% over a whole run, and a bench turn is ~2 minutes (13.23).
#
# Treatment vs control differ by exactly `--no-read-cache`; test_arm_input_parity asserts it.
eval "$(scripts/pin_superstate_binary.sh)"

STAMP=$(date +"%Y%m%d_%H%M%S")
OUT_FILE="results/canary_read_cache_exp081.json"
ARCHIVE="traces/exp081_${STAMP}"
mkdir -p "$ARCHIVE"

echo "EXP-081 read-cache ablation: build-cython-ext (Py/C), scc (Go), katex (TS)"
echo "Binary:  ${SUPERSTATE_BIN}"
echo "Arms:    superstate_daemon_full (cache ON) vs superstate_daemon_nocache (control)"
echo "Output:  ${OUT_FILE}"
echo "Traces:  ${ARCHIVE}"
echo "Started: $(date)"

.venv/bin/python scripts/paired_run.py \
  --arms superstate_daemon_full superstate_daemon_nocache \
  --canary \
  --driver agy \
  --model gemini-3.8-flash-high \
  --concurrency 2 \
  --out "${OUT_FILE}"
echo "paired_run exit: $?"

# Archive before anything touches /tmp. EXP-079's traces were lost to housekeeping and its
# own open question could not be reopened against the data that raised it.
echo "archiving activity traces ..."
found=0
while IFS= read -r trace; do
  tag=$(basename "$(dirname "$(dirname "$(dirname "$trace")")")")
  cp "$trace" "$ARCHIVE/${tag}.guard-activity.jsonl" 2>/dev/null && found=$((found+1))
done < <(find /tmp/superstate_eval_runs -name "guard-activity.jsonl" 2>/dev/null)
echo "archived ${found} trace file(s) to ${ARCHIVE}"

# The precondition for the run meaning anything: the treatment must actually have cached.
# A treatment arm recording ~0 hits measures nothing, exactly as EXP-080's build-cython-ext
# cell did -- and a token delta reported beside an inert mechanism is how the 23.8% noise
# floor nearly passed for a result.
echo
echo "cache hits per trace (treatment arms must be non-zero for this run to mean anything):"
for f in "$ARCHIVE"/*.jsonl; do
  [ -e "$f" ] || continue
  printf '  %-62s ' "$(basename "$f" .guard-activity.jsonl | cut -c1-62)"
  .venv/bin/python -c "
import json,sys,collections
c=collections.Counter()
for l in open(sys.argv[1]):
    try: c[json.loads(l).get('decision')]+=1
    except Exception: pass
print(f\"cached={c.get('cached',0):4d}  allow={c.get('allow',0):4d}  deny={c.get('deny',0):3d}\")
" "$f"
done

echo "Finished: $(date)"
