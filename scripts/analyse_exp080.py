#!/usr/bin/env python3
"""EXP-080 analysis: read-budget curve, window repeats, and the command channel, per repo.

Answers the three questions EXP-080 was registered to settle, from archived traces:

  1. Does the optimum read budget vary by repository, and does it track file-length
     distribution -- something the daemon could observe cheaply and derive the number from?
  2. Are the repeated reads EXP-079 found DISTINCT WINDOWS or RE-FETCHES of the same lines?
     Distinct windows means a read cache buys nothing and the lever is elsewhere.
  3. How much of the guard's traffic is commands rather than reads, and how much of that is
     host-side -- the channel shunting never sees, since it wraps only ./run-in-container.

    scripts/analyse_exp080.py traces/exp080_<stamp>/
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from read_budget import cost_at, windows_per_file  # noqa: E402

THRESHOLDS = (100, 200, 400, 800, 1600, 3200, 10**9)


def load(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def repeat_analysis(rows: list[dict]) -> dict:
    """Separate 'read the same file again' from 'read the same LINES again'.

    EXP-079 could only measure the first and reported 152 of 166 reads as repeats, which
    looks like a read cache would eliminate them. It only does if the LINES repeat.
    """
    seen_files: set[str] = set()
    seen_lines: dict[str, set[int]] = collections.defaultdict(set)
    reads = file_repeats = line_overlap_reads = 0
    redundant_lines = total_lines = 0

    for r in rows:
        if not str(r.get("kind", "")).startswith("read"):
            continue
        reads += 1
        path = r.get("target", "?")
        if path in seen_files:
            file_repeats += 1
        seen_files.add(path)

        start, end = r.get("start"), r.get("end")
        if start is None or end is None:
            start, end = 1, int(r.get("lines") or 0)
        window = set(range(int(start), int(end) + 1))
        if not window:
            continue
        already = window & seen_lines[path]
        total_lines += len(window)
        redundant_lines += len(already)
        if already:
            line_overlap_reads += 1
        seen_lines[path] |= window

    return {
        "reads": reads,
        "file_repeats": file_repeats,
        "line_overlap_reads": line_overlap_reads,
        "redundant_lines": redundant_lines,
        "total_lines": total_lines,
    }


def command_analysis(rows: list[dict]) -> dict:
    cmds = [r for r in rows if r.get("kind") == "command"]
    host = sum(1 for r in cmds if "run-in-container" not in str(r.get("target", "")))
    return {"commands": len(cmds), "host_side": host, "containerised": len(cmds) - host}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("trace_dir", type=Path)
    ap.add_argument("--preamble", type=int, default=2500)
    ap.add_argument("--tokens-per-line", type=int, default=11)
    args = ap.parse_args()

    traces = sorted(args.trace_dir.glob("*.jsonl"))
    if not traces:
        print(f"no traces in {args.trace_dir}", file=sys.stderr)
        return 1

    for t in traces:
        rows = load(t)
        # Task name out of the archived filename, which is the workspace dir name.
        name = t.name.replace(".guard-activity.jsonl", "")
        for prefix in ("eval-datacurve_", "eval-terminal-bench_"):
            name = name.replace(prefix, "")
        name = name.replace("-superstate_daemon_full", "").rsplit("-", 1)[0]

        print("=" * 78)
        print(f"{name}   ({len(rows)} guard events)")
        print("=" * 78)

        ev = collections.Counter(r.get("kind") for r in rows)
        print(f"  events: {dict(ev)}")

        cmd = command_analysis(rows)
        if cmd["commands"]:
            print(f"  commands: {cmd['commands']} total, {cmd['host_side']} host-side "
                  f"({100 * cmd['host_side'] / cmd['commands']:.0f}% -- never shunted), "
                  f"{cmd['containerised']} via run-in-container")

        rep = repeat_analysis(rows)
        if rep["reads"]:
            print(f"\n  Q2 repeats: {rep['reads']} reads, "
                  f"{rep['file_repeats']} re-read a file already read "
                  f"({100 * rep['file_repeats'] / rep['reads']:.0f}%)")
            print(f"              {rep['line_overlap_reads']} re-read lines already fetched "
                  f"({100 * rep['line_overlap_reads'] / rep['reads']:.0f}%)")
            if rep["total_lines"]:
                pct = 100 * rep["redundant_lines"] / rep["total_lines"]
                print(f"              {rep['redundant_lines']:,} of {rep['total_lines']:,} "
                      f"line-fetches were redundant ({pct:.1f}%)")
                verdict = ("a read cache would pay" if pct > 25 else
                           "a read cache buys little -- the lever is elsewhere")
                print(f"              -> {verdict}")

        files = windows_per_file(rows)
        if files:
            print(f"\n  Q1 budget curve ({len(files)} files read with windows):")
            best = None
            baseline = cost_at(200, files, args.preamble, args.tokens_per_line)
            for th in THRESHOLDS:
                total = cost_at(th, files, args.preamble, args.tokens_per_line)
                label = "unlimited" if th > 10**6 else f"{th:,}"
                mark = ""
                if best is None or total < best[1]:
                    best = (label, total, th)
                print(f"      {label:>10s} {total:>12,}{mark}")
            print(f"      -> optimum {best[0]} at {best[1]:,} "
                  f"({100 * (1 - best[1] / baseline):.0f}% cheaper than 200)")
            at800 = cost_at(800, files, args.preamble, args.tokens_per_line)
            print(f"      -> shipped 800 costs {at800:,} "
                  f"({100 * (at800 / best[1] - 1):+.1f}% vs optimum, "
                  f"{100 * (at800 / baseline - 1):+.1f}% vs 200)")
        print()

    print("NOTE: cost_at() assumes wanted lines repack optimally into threshold-sized")
    print("windows. Real agents choose windows themselves, so high thresholds are")
    print("flattered by the model. Treat the optimum as an upper bound on the gain.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
