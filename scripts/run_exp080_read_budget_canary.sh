#!/bin/bash
set -uo pipefail
cd "$(dirname "$0")/.."

# EXP-080: what read budget does a REAL task want, per repository -- and are the repeated
# reads EXP-079 found distinct windows or genuine re-fetches?
#
# WHY THIS SHAPE, AND NOT A LIVE THRESHOLD SWEEP
# ----------------------------------------------
# The obvious experiment -- run the same prompt at 200/800/1600 and compare tokens -- was
# smoke-tested on scc and cannot work. At 800 the guard denied NOTHING (0 denials, 0 lines
# withheld) and the two conditions still differed by 23.8% in input tokens. That 23.8% is
# pure run-to-run noise, and it swamps any effect a budget could have. Detecting a real
# difference through it would take an n nobody should pay for.
#
# The arithmetic replay has no noise at all. `read_budget.py` takes a recorded trace and
# costs it at every threshold exactly. What is missing is not precision, it is TRACES from
# real tasks on more than one repository -- 13.18 replayed exactly one, superstate-core,
# whose only file over 1,600 lines is daemon.rs itself. Its "optimum 1,600" is therefore
# close to the point where the budget stops binding at all, which is not the same finding.
#
# So: run the canary once to GENERATE traces, then replay them offline at every threshold.
# One run, ~$6, answers three open questions:
#
#   1. (13.19) Does the optimum budget vary by repository, and does it track anything the
#      daemon can observe cheaply -- file-length distribution being the obvious candidate?
#      DECISION: whether the daemon can derive this number itself or must ship a constant.
#   2. (EXP-079, "still unresolved") Are the ~150 repeated reads per task distinct windows
#      or re-fetches of the same lines? That binary predated window recording; this one
#      records start/end on every read.
#      DECISION: a read cache (if re-fetches) vs host-side command shunting (if not).
#   3. Does the 800-line build regress anything end-to-end vs EXP-079's three runs?
#
# Pin a SNAPSHOT of the binary, never the live build path -- EXP-073 was rebuilt 12 minutes
# in and had to be withdrawn.
eval "$(scripts/pin_superstate_binary.sh)"

STAMP=$(date +"%Y%m%d_%H%M%S")
OUT_FILE="results/canary_read_budget_exp080.json"
ARCHIVE="traces/exp080_${STAMP}"
mkdir -p "$ARCHIVE"

echo "EXP-080 read-budget canary: build-cython-ext (Py/C), scc (Go), katex (TS)"
echo "Binary:  ${SUPERSTATE_BIN}"
echo "Output:  ${OUT_FILE}"
echo "Traces:  ${ARCHIVE}"
echo "Started: $(date)"

.venv/bin/python scripts/paired_run.py \
  --arms superstate_daemon_full \
  --canary \
  --driver agy \
  --model gemini-3.8-flash-high \
  --concurrency 2 \
  --out "${OUT_FILE}"
RC=$?
echo "paired_run exit: ${RC}"

# ARCHIVE THE TRACES BEFORE ANYTHING CLEANS /tmp.
# EXP-079's per-read traces were deleted with their workspaces during housekeeping on
# 2026-09-21 and cannot be recovered, so its "distinct windows or re-fetches" question could
# not be reopened against the data that raised it. The scored JSON is not a substitute: it
# carries totals, not the per-read records the whole analysis needs.
echo "archiving activity traces ..."
found=0
while IFS= read -r trace; do
  # <run>/<task-dir>/workspace/.agent-state/guard-activity.jsonl -- the task name is THREE
  # levels up. Using the workspace dir gave every task the tag "workspace", so each trace
  # overwrote the last and the archive kept exactly one.
  tag=$(basename "$(dirname "$(dirname "$(dirname "$trace")")")")
  cp "$trace" "$ARCHIVE/${tag}.guard-activity.jsonl" 2>/dev/null && found=$((found+1))
done < <(find /tmp/superstate_eval_runs -name "guard-activity.jsonl" 2>/dev/null)
echo "archived ${found} trace file(s) to ${ARCHIVE}"

if [ "$found" -eq 0 ]; then
  echo "WARNING: no traces archived -- the replay analysis has no input."
fi

echo "Finished: $(date)"
