#!/bin/bash
# EXP-080: what does the read budget actually cost or save, live, across four languages?
#
# 13.18 replayed a RECORDED trace through an arithmetic model and concluded 200 lines cost
# 2.2x a whole-file read. That is a model, not a measurement. This runs the same read-heavy
# prompt against the same repository with the file guard off, and at 200 / 800 / 1600, and
# compares the tokens agy actually reports.
#
# Decision it settles: keep 800, revert to 200, or drop the read guard from the daemon's
# default hooks. If `none` wins everywhere, the guard is a net cost and Invariant IV's read
# interception needs rethinking rather than retuning.
#
# Four repositories, one per language, because 13.19 named cross-repo variation as the thing
# blocking the daemon from deriving this number itself.

set -uo pipefail

CORPUS=/Users/danielfisher/bench_corpus
OUT="${1:-$CORPUS/exp080}"
BIN="${SUPERSTATE_BIN:-/tmp/superstate_eval_bin/superstate-20260921_225900}"
REPEATS="${REPEATS:-3}"
TIMEOUT="${TIMEOUT:-240}"
EVAL=/Users/danielfisher/repos/superstate-eval

mkdir -p "$OUT"
LOG="$OUT/sweep.log"

say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }

[ -x "$BIN" ] || { say "FATAL: no superstate binary at $BIN"; exit 1; }
say "binary: $BIN"
say "repeats per cell: $REPEATS, per-turn timeout: ${TIMEOUT}s"

# A read-heavy architecture question per repo. Each asks for a mechanism that spans several
# large files, so the turn must read broadly -- which is the only condition under which a
# read budget can matter at all.
prompt_for() {
  case "$1" in
    scc)      echo "Explain how scc counts lines and decides what to hold in memory versus stream, naming the specific files, structs and functions involved, and how the worker pool coordinates.";;
    katex)    echo "Explain how KaTeX parses an array environment and lays out its columns, naming the specific source files, classes and functions involved from parsing through to DOM building.";;
    pyknotid) echo "Explain how pyknotid represents a space curve and computes its knot invariants, naming the specific modules, classes and functions involved.";;
    superstate) echo "Explain how the daemon decides a milestone is complete and when it rolls back a failed attempt, naming the specific files, structs and functions involved.";;
  esac
}

repo_path() {
  case "$1" in
    superstate) echo /Users/danielfisher/repos/superstate;;
    *)          echo "$CORPUS/$1";;
  esac
}

# `none` is the baseline; the rest are the file guard at three budgets. The command guard is
# deliberately absent: this isolates ONE mechanism, which is the whole point of the instrument.
for repo in scc katex pyknotid superstate; do
  RP=$(repo_path "$repo")
  if [ ! -d "$RP" ]; then say "SKIP $repo: no repo at $RP"; continue; fi
  PROMPT=$(prompt_for "$repo")

  for cell in none:0 file:200 file:800 file:1600; do
    CONFIG="${cell%%:*}"
    THRESH="${cell##*:}"
    TAG="${repo}_${CONFIG}${THRESH}"
    DEST="$OUT/${TAG}.json"

    if [ -s "$DEST" ]; then say "skip $TAG (already have $DEST)"; continue; fi

    say "RUN $TAG"
    "$EVAL/.venv/bin/python" "$EVAL/scripts/guard_bench.py" \
        --repo "$RP" --prompt "$PROMPT" \
        --configs "$CONFIG" --repeats "$REPEATS" \
        --threshold-lines "$THRESH" --timeout-sec "$TIMEOUT" \
        --binary "$BIN" --out "$DEST" >> "$LOG" 2>&1
    rc=$?
    if [ $rc -ne 0 ]; then say "  FAILED rc=$rc (continuing)"; else say "  done -> $DEST"; fi
  done
done

say "SWEEP COMPLETE"
say "cells written: $(ls "$OUT"/*.json 2>/dev/null | wc -l | tr -d ' ')"
