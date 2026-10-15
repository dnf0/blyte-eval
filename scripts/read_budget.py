#!/usr/bin/env python3
"""Find the read threshold that actually minimises tokens, from a recorded trace.

A bounded read is not free: each tool call carries a fixed preamble (FINDINGS.md 13.17,
measured at ~2,500 tokens with MCP disabled and ~5,000 with it enabled). Splitting a file into
N windows therefore pays that preamble N times to avoid fetching the lines it skipped.

13.18 measured the consequence: at a 200-line threshold, `daemon.rs` took 14 calls costing
50,719 tokens where one whole-file read would have cost 23,466 -- 2.2x worse. The threshold
predates knowing a call had a fixed cost.

This replays a `guard-activity.jsonl` trace at different thresholds and reports total tokens,
so the value is chosen from evidence rather than guessed.

    scripts/read_budget.py <workspace-or-logs-dir> [--preamble 2500] [--tokens-per-line 11]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def windows_per_file(rows: list[dict]) -> dict[str, tuple[int, list[tuple[int, int]]]]:
    """path -> (file length, [(start, end), ...]) for every windowed read."""
    out: dict[str, tuple[int, list[tuple[int, int]]]] = {}
    for r in rows:
        if not str(r.get("kind", "")).startswith("read"):
            continue
        start, end = r.get("start"), r.get("end")
        if start is None or end is None:
            continue
        path = r.get("target", "?")
        length, wins = out.setdefault(path, (int(r.get("lines") or 0), []))
        wins.append((int(start), int(end)))
    return out


def cost_at(threshold: int, files: dict, preamble: int, tpl: int) -> int:
    """Total tokens to satisfy the same demand at a given threshold.

    The lines the agent actually wanted are held constant; only how many calls it takes to
    fetch them changes. Below the threshold a file is served whole in one call.
    """
    total = 0
    for _path, (length, wins) in files.items():
        wanted = set()
        for a, b in wins:
            wanted.update(range(a, b + 1))
        if length <= threshold:
            # Served whole: one call, the entire file.
            total += preamble + length * tpl
            continue
        # Still bounded: the same demand, re-chunked into threshold-sized windows.
        calls = max(1, -(-len(wanted) // threshold))
        total += calls * preamble + len(wanted) * tpl
    return total


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "workspace",
        type=Path,
        help="Workspace or run logs/ directory containing guard-activity.jsonl",
    )
    ap.add_argument("--preamble", type=int, default=2500,
                    help="fresh tokens a tool call costs before any content (13.17)")
    ap.add_argument("--tokens-per-line", type=int, default=11)
    args = ap.parse_args()

    candidates = [
        args.workspace / ".agent-state" / "guard-activity.jsonl",
        args.workspace / "artifacts" / "guard-activity.jsonl",
    ]
    log = next((p for p in candidates if p.is_file()), None)
    if log is None:
        tried = ", ".join(str(p) for p in candidates)
        print(f"no activity trace at {tried}", file=sys.stderr)
        return 1
    rows = []
    for line in log.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            continue

    files = windows_per_file(rows)
    if not files:
        print("trace carries no windowed reads; re-run with a binary that records ranges")
        return 1

    print(f"{len(files)} file(s) read with windows, preamble={args.preamble:,}, "
          f"{args.tokens_per_line} tokens/line\n")
    print(f"{'threshold':>10s} {'total tokens':>14s}")
    best = None
    for threshold in (100, 200, 400, 800, 1600, 3200, 10**9):
        total = cost_at(threshold, files, args.preamble, args.tokens_per_line)
        label = "unlimited" if threshold > 10**6 else f"{threshold:,}"
        print(f"{label:>10s} {total:>14,}")
        if best is None or total < best[1]:
            best = (label, total)
    baseline = cost_at(200, files, args.preamble, args.tokens_per_line)
    print(f"\n  best: {best[0]} at {best[1]:,} tokens "
          f"({100 * (1 - best[1] / baseline):.0f}% below the current 200-line budget)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
