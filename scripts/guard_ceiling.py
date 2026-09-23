#!/usr/bin/env python3
"""The arithmetic upper bound on what a file read guard can save. No model calls, no agent.

WHY THIS EXISTS ALONGSIDE guard_bench.py
----------------------------------------
Spotify's Portal reports ~90% by "measuring tokens Claude would consume reading files directly
vs. consuming the bulk-reader's summary" -- a comparison of two artefacts, not of two agent
runs. It does not account for the agent reading parts of the file back afterwards.

`guard_bench.py` measures behaviour: one real turn per configuration, which on this repository
came out at -4.2%. This measures the ceiling: what the guard would save if the outline replaced
the read entirely and nothing was re-read. The gap between the two numbers is what the agent
gives back in targeted re-reads, and it is the interesting quantity.

Instant, deterministic, free -- run it before deciding a workload is worth an agent turn.

    scripts/guard_ceiling.py --repo ~/repos/superstate/crates/superstate-core --threshold 200
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

DEFAULT_BIN = Path("/Users/danielfisher/repos/superstate/target/release/superstate")
# Rough and stated rather than hidden: token counts here are a ratio, and any consistent
# divisor cancels between the two sides of the comparison.
CHARS_PER_TOKEN = 4

SOURCE_SUFFIXES = {".rs", ".py", ".go", ".ts", ".tsx", ".js", ".jsx", ".java", ".c", ".h", ".cpp"}


def outline_tokens(binary: Path, path: Path, threshold: int) -> int | None:
    """Tokens in the AST outline the guard returns, or None if this file would not be denied."""
    payload = json.dumps(
        {"tool_name": "view_file", "tool_input": {"AbsolutePath": str(path)}}
    )
    proc = subprocess.run(
        [str(binary), "guard", "pre-tool-use", "--threshold-lines", str(threshold)],
        input=payload, capture_output=True, text=True, timeout=30,
    )
    try:
        decision = json.loads(proc.stdout)
    except Exception:
        return None
    if decision.get("decision") != "deny":
        return None
    return len(decision.get("reason") or "") // CHARS_PER_TOKEN


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", required=True, type=Path)
    ap.add_argument("--threshold", type=int, default=200)
    ap.add_argument("--binary", type=Path, default=DEFAULT_BIN)
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args()

    if not args.binary.is_file():
        print(f"no superstate binary at {args.binary}", file=sys.stderr)
        return 1

    rows = []
    skipped = 0
    for path in sorted(args.repo.rglob("*")):
        if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
            continue
        if any(part in {"target", "node_modules", ".git"} for part in path.parts):
            continue
        try:
            raw = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        whole = len(raw) // CHARS_PER_TOKEN
        outline = outline_tokens(args.binary, path, args.threshold)
        if outline is None:
            skipped += 1
            continue
        rows.append((path.relative_to(args.repo), len(raw.splitlines()), whole, outline))

    if not rows:
        print(f"no file exceeds {args.threshold} lines; the guard can save nothing here")
        return 0

    rows.sort(key=lambda r: r[2], reverse=True)
    print(f"{'file':44s} {'lines':>7s} {'whole':>9s} {'outline':>8s} {'saved':>9s}")
    for rel, lines, whole, outline in rows[: args.top]:
        print(f"{str(rel)[:42]:44s} {lines:>7,} {whole:>9,} {outline:>8,} {whole - outline:>9,}")
    if len(rows) > args.top:
        print(f"  ... and {len(rows) - args.top} more")

    whole_total = sum(r[2] for r in rows)
    outline_total = sum(r[3] for r in rows)
    print(
        f"\n{len(rows)} file(s) over {args.threshold} lines, {skipped} under it (never intercepted)."
    )
    print(f"  read whole:        {whole_total:>9,} tokens")
    print(f"  outline instead:   {outline_total:>9,} tokens")
    print(f"  CEILING SAVING:    {100 * (whole_total - outline_total) / whole_total:>8.1f}%"
          "  (if the outline replaced every read and nothing was re-read)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
