#!/bin/bash
# EXP-054: who should write the gate?
#
# The gate is superstate's active ingredient -- the sign of the effect tracks its precision
# (92% -> +10pp on terminal-bench, 17% -> -11pp on datacurve). Nothing in superstate authors
# one; --verify-cmd is an input. So handoff-first depends on the handing-off agent writing a
# gate better than its own judgement about when it is done.
#
# The only evidence so far is two runs of one task, where an LLM produced a gate satisfied by
# `touch`. This measures it properly: the 13 gradeable terminal-bench tasks, where the
# hand-authored gates scored 92% precision in EXP-047. Same tasks, same arm, same model --
# the only difference is who wrote the gate.
#
# IGNORE_GATE_FIXTURES is required: a fixture exists for all 30 tasks and short-circuits
# _derive_gate before derivation is reached, so DERIVE_GATES alone would measure nothing.
set -euo pipefail
cd /Users/danielfisher/repos/superstate-eval

export SUPERSTATE_EVAL_DERIVE_GATES=1
export SUPERSTATE_EVAL_IGNORE_GATE_FIXTURES=1

TASKS="build-cython-ext chess-best-move code-from-image constraints-scheduling \
db-wal-recovery dna-insert extract-elf gcode-to-text git-leak-recovery kv-store-grpc \
openssl-selfsigned-cert regex-log vulnerable-secret"

exec .venv/bin/python scripts/paired_run.py \
  --tasks $TASKS \
  --arms superstate_daemon \
  --model gemini-3.8-flash-high \
  --repeats 2 \
  --concurrency 4 \
  --out results/derived_gates_13tasks.json
