#!/usr/bin/env python3
"""Reconcile EXPERIMENTS.md against results/ so "has this been run?" is one command.

Three failures this catches, all of which have already cost real time:

* **orphan** -- a results file nobody can explain. Fifty-nine accumulated before anyone
  asked what question each one answered.
* **ghost** -- a ledger row whose results file is missing, so its verdict rests on nothing.
* **truncated** -- a results file holding fewer runs than the ledger declares. `paired_run.py`
  saves incrementally, so a killed run leaves a plausible-looking partial file. One such
  snapshot (31 of 40 rows) reached main and showed 10/16 vs 15/15 for a comparison whose
  real outcome was 12/20 vs 12/20.

Usage:
    scripts/experiments.py check          # reconcile; non-zero exit if anything is wrong
    scripts/experiments.py list [QUERY]   # the ledger, optionally filtered
    scripts/experiments.py scan           # tallies straight from results/, ledger ignored
"""

from __future__ import annotations

import collections
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "EXPERIMENTS.md"
RESULTS = ROOT / "results"

# A ledger row: | id | date | question | arms | n | switches | results | verdict | status |
ROW = re.compile(r"^\|\s*(?P<id>[A-Z]+-\d+[a-z]?)\s*\|(?P<rest>.*)\|\s*$")
VALID_STATUS = {"STANDS", "WITHDRAWN", "SUPERSEDED", "PARTIAL", "PLANNED"}


def tally(path: Path) -> tuple[int, int, dict[str, tuple[int, int]]]:
    """Return (rows, distinct tasks, {arm: (passed, n)}) for a results JSON."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return 0, 0, {}
    if not (isinstance(data, list) and data and isinstance(data[0], dict) and "arm" in data[0]):
        return 0, 0, {}
    agg: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0])
    for r in data:
        agg[r["arm"]][0] += bool(r.get("passed"))
        agg[r["arm"]][1] += 1
    return len(data), len({r.get("task_id") for r in data}), {a: tuple(v) for a, v in agg.items()}


def parse_ledger() -> list[dict[str, str]]:
    if not LEDGER.is_file():
        return []
    out = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        m = ROW.match(line.strip())
        if not m:
            continue
        cells = [c.strip() for c in m.group("rest").split("|")]
        if len(cells) < 8:
            continue
        out.append(
            dict(
                id=m.group("id"), date=cells[0], question=cells[1], arms=cells[2],
                n=cells[3], switches=cells[4], results=cells[5].strip("`"),
                verdict=cells[6], status=cells[7].strip("*"),
            )
        )
    return out


def cmd_check() -> int:
    rows = parse_ledger()
    if not rows:
        print("No ledger rows parsed from EXPERIMENTS.md")
        return 1

    claimed = {r["results"] for r in rows if r["results"] not in ("-", "")}
    on_disk = {p.name for p in RESULTS.glob("*.json") if tally(p)[0]}
    problems = 0

    for name in sorted(on_disk - claimed):
        rowcount, tasks, arms = tally(RESULTS / name)
        print(f"ORPHAN     {name}  ({rowcount} runs, {tasks} tasks) -- no ledger row")
        problems += 1

    for r in rows:
        if r["results"] in ("-", ""):
            if r["status"] != "PLANNED":
                print(f"GHOST      {r['id']}  status={r['status']} but names no results file")
                problems += 1
            continue
        path = RESULTS / r["results"]
        if not path.is_file():
            if r["status"] != "PLANNED":
                print(f"GHOST      {r['id']}  {r['results']} is missing from results/")
                problems += 1
            continue
        rowcount, _, _ = tally(path)
        try:
            declared = int(re.sub(r"\D", "", r["n"]) or 0)
        except ValueError:
            declared = 0
        if declared and rowcount < declared:
            if r["status"] != "PLANNED":
                print(
                    f"TRUNCATED  {r['id']}  {r['results']} holds {rowcount} runs, "
                    f"ledger declares {declared} -- killed mid-run?"
                )
                problems += 1
        if r["status"] not in VALID_STATUS:
            print(f"BAD STATUS {r['id']}  '{r['status']}' not in {sorted(VALID_STATUS)}")
            problems += 1

    print(f"\n{len(rows)} ledger rows, {len(on_disk)} results files, {problems} problem(s)")
    return 1 if problems else 0


def cmd_list(query: str | None) -> int:
    rows = parse_ledger()
    if query:
        q = query.lower()
        rows = [r for r in rows if any(q in v.lower() for v in r.values())]
        if not rows:
            print(f"Nothing in the ledger matches '{query}'. It has probably not been run.")
            return 1
    for r in rows:
        mark = {"WITHDRAWN": "✗", "SUPERSEDED": "~", "PLANNED": "·"}.get(r["status"], "✓")
        print(f"{mark} {r['id']}  {r['date']}  [{r['status']}]  {r['question']}")
        print(f"    arms: {r['arms']}   n={r['n']}   switches: {r['switches']}")
        print(f"    -> {r['verdict']}")
        print(f"       results/{r['results']}\n")
    return 0


def cmd_scan() -> int:
    for path in sorted(RESULTS.glob("*.json")):
        rowcount, tasks, arms = tally(path)
        if not rowcount:
            continue
        summary = "; ".join(f"{a} {p}/{n}" for a, (p, n) in sorted(arms.items()))
        print(f"{path.name:44s} {rowcount:4d} runs {tasks:3d} tasks  {summary}")
    return 0


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        return cmd_check()
    if cmd == "list":
        return cmd_list(sys.argv[2] if len(sys.argv) > 2 else None)
    if cmd == "scan":
        return cmd_scan()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
