#!/usr/bin/env python3
"""Summarise what a run actually read, from the guards' own activity trace.

EXP-075 had one turn admit 1,917,135 input tokens against a 133,550-token codebase --
fourteen times the source. Two explanations survive and they point opposite ways: the same
files were read many times (a guard compounds), or the volume came from another channel
entirely (a guard barely helps). Nothing the daemon writes could tell them apart, because the
arm produces no tool-call transcript.

The guards see every read and every command, so they are the cheapest place to record it.
`guard-activity.jsonl` is that record; this reads it back.

    scripts/guard_activity.py /tmp/superstate_eval_runs/<stamp>/eval-.../workspace
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
import sys

CHARS_PER_TOKEN = 4
BYTES_PER_LINE = 40  # rough, and only used for an order-of-magnitude estimate


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("workspace", type=Path)
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args()

    log = args.workspace / ".agent-state" / "guard-activity.jsonl"
    if not log.is_file():
        print(f"no activity trace at {log}", file=sys.stderr)
        return 1

    entries = []
    for line in log.read_text(encoding="utf-8").splitlines():
        try:
            entries.append(json.loads(line))
        except Exception:
            continue
    if not entries:
        print("activity trace is empty")
        return 0

    kinds = collections.Counter(e.get("kind", "?") for e in entries)
    decisions = collections.Counter(e.get("decision", "?") for e in entries)
    reads = [e for e in entries if str(e.get("kind", "")).startswith(("read", "shell_read"))]
    per_file = collections.Counter(e.get("target", "?") for e in reads)

    print(f"{len(entries)} guard evaluations: {dict(kinds)}")
    print(f"decisions: {dict(decisions)}")

    if reads:
        allowed = [e for e in reads if e.get("decision") == "allow"]
        # Tokens that actually reached the prompt, for whole-file reads that were allowed.
        flowed = sum(
            int(e.get("lines") or 0) * BYTES_PER_LINE // CHARS_PER_TOKEN
            for e in allowed
            if e.get("kind") == "read_whole"
        )
        print(f"\nreads: {len(reads)} across {len(per_file)} distinct files")
        print(f"  whole-file reads allowed through: ~{flowed:,} tokens (est.)")
        repeats = [(f, n) for f, n in per_file.most_common() if n > 1]
        if repeats:
            print(f"\n  RE-READ FILES ({len(repeats)} of {len(per_file)}):")
            for target, n in repeats[: args.top]:
                print(f"    {n:3d}x  {target.split('/')[-1]}")
            print(
                f"\n  {sum(n for _, n in repeats)} of {len(reads)} reads were of a file already read."
            )
        else:
            print("\n  No file was read twice: repeated reads do not explain context growth.")

        # The distinction that decides whether a read cache would help at all. Re-reading a
        # DIFFERENT window of a large file is correct behaviour under a line budget; re-reading
        # the SAME window is redundancy a cache eliminates. EXP-079 recorded no ranges and so
        # could not separate them -- every "24x formatters.go" was ambiguous.
        windowed = [e for e in reads if e.get("start") is not None]
        if windowed:
            seen = collections.Counter(
                (e.get("target"), e.get("start"), e.get("end")) for e in windowed
            )
            identical = sum(n - 1 for n in seen.values() if n > 1)
            print(
                f"\n  of {len(windowed)} reads carrying a window, {identical} re-fetched a window "
                f"already fetched ({100 * identical / len(windowed):.0f}%)."
            )
            if identical:
                print("  redundant windows:")
                for (target, start, end), n in seen.most_common(args.top):
                    if n > 1:
                        print(f"    {n:3d}x  {str(target).split('/')[-1]} [{start}:{end}]")
            else:
                print("  every repeat was a different window: a read cache would save nothing.")
        elif reads:
            print("\n  no read carried a window; ranges are not recorded in this trace.")

    commands = [e for e in entries if e.get("kind") == "command"]
    if commands:
        print(f"\ncommands: {len(commands)}")
        for cmd, n in collections.Counter(e.get("target", "?") for e in commands).most_common(args.top):
            print(f"    {n:3d}x  {cmd[:90]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
