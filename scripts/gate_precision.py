#!/usr/bin/env python3
"""Report how often a passing gate agrees with the sealed grader.

The gate is what tells the worker it is done. If it passes on work the grader rejects,
the worker stops early and the retry loop never engages -- which is precisely what
EXP-047 found: the gate ran 20 times, passed 20 times, and was wrong on 8. Precision
60%, recall against bad work zero.

Reads the milestone records each arm writes alongside its run, so it needs a run
directory rather than just the results JSON.

    scripts/gate_precision.py /tmp/superstate_eval_runs/<stamp> results/<run>.json
"""

from __future__ import annotations

import collections
import json
from pathlib import Path
import sys


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    run_root, results_path = Path(sys.argv[1]), Path(sys.argv[2])

    graded = {
        (r["task_id"], r["arm"]): bool(r.get("passed"))
        for r in json.loads(results_path.read_text(encoding="utf-8"))
    }

    per_arm: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    false_passes: list[tuple[str, str]] = []
    unrecorded: list[tuple[str, str]] = []

    for run_json in run_root.glob("*/logs/run.json"):
        record = json.loads(run_json.read_text(encoding="utf-8"))
        key = (record.get("task_id"), record.get("arm"))
        if key not in graded:
            continue
        milestones_path = run_json.parent / "milestones.jsonl"
        if not milestones_path.is_file():
            unrecorded.append(key)
            continue
        milestones = [json.loads(line) for line in milestones_path.read_text().splitlines() if line.strip()]
        ran = [m for m in milestones if m.get("gate_ran")]
        if not ran:
            unrecorded.append(key)
            continue
        gate_passed = all(m.get("gate_passed") for m in ran)
        per_arm[key[1]][(gate_passed, graded[key])] += 1
        if gate_passed and not graded[key]:
            false_passes.append(key)

    for arm, cell in sorted(per_arm.items()):
        tp, fp = cell[(True, True)], cell[(True, False)]
        fn, tn = cell[(False, True)], cell[(False, False)]
        total = tp + fp + fn + tn
        print(f"\n{arm}  ({total} runs with a recorded gate verdict)")
        print(f"                    grader PASS   grader FAIL")
        print(f"  gate says PASS {tp:12d} {fp:13d}")
        print(f"  gate says FAIL {fn:12d} {tn:13d}")
        if tp + fp:
            print(f"  precision {100 * tp / (tp + fp):.0f}%  -- when the gate says done, it is right this often")
        rejected = fn + tn
        print(
            f"  the gate rejected {rejected} of {total} runs"
            + ("  <- it never says no" if rejected == 0 else "")
        )

    if false_passes:
        print("\nCertified as done, rejected by the grader:")
        for task, arm in sorted(set(false_passes)):
            print(f"  {task.split('/')[-1]:34s} {arm}")

    if unrecorded:
        arms = sorted({a for _, a in unrecorded})
        print(f"\n{len(unrecorded)} run(s) wrote no gate verdict, so cannot be scored: arms {arms}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
