#!/bin/bash
# Snapshot the superstate binary so a run cannot be changed underneath it.
#
# EXP-073 pinned SUPERSTATE_BIN to target/release/superstate -- the same path `cargo build`
# writes to -- and the binary was rebuilt 12 minutes into the run. No failure in that run
# could be attributed to a known build, so it was withdrawn. Copy first, pin the copy.
#
# Usage:  eval "$(scripts/pin_superstate_binary.sh)"
set -euo pipefail

SRC="${SUPERSTATE_SRC_BIN:-/Users/danielfisher/repos/superstate/target/release/superstate}"
[ -x "$SRC" ] || { echo "no executable superstate binary at $SRC" >&2; exit 1; }

STAMP=$(date +"%Y%m%d_%H%M%S")
DEST_DIR="/tmp/superstate_eval_bin"
DEST="${DEST_DIR}/superstate-${STAMP}"
mkdir -p "$DEST_DIR"
cp "$SRC" "$DEST"
chmod +x "$DEST"

# Record which build this is, so a results file can be traced back to a commit.
REV=$(git -C "$(dirname "$SRC")/../.." rev-parse --short HEAD 2>/dev/null || echo unknown)
echo "# snapshot of $SRC at rev ${REV}" >&2
echo "export SUPERSTATE_BIN=${DEST}"
