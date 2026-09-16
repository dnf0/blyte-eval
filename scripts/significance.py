#!/usr/bin/env python3
"""The paired significance test for superstate vs vanilla, pre-specified.

WHY THIS IS A SCRIPT AND NOT A CALCULATION SOMEONE REDOES
---------------------------------------------------------
This number moved four times in one day, always because of how the data was counted rather
than what the data said:

    +29pp, p=0.037    run-level, including self-graded tasks
    +19pp, p=0.109    gradeable only, still counting repeats as independent
           p=0.0166   permutation test, but the same task counted up to 3 times
           p=0.125    one observation per task -- correct, and not significant

The unit of analysis is the TASK. Five repeats of one task are one observation, not five;
so are the same task's runs appearing in three different results files. Pooling them is the
difference between p=0.017 and p=0.125.

PRE-SPECIFIED CHOICES, so this is not test-shopping after the fact:

  * unit            one task, all its runs pooled into a pass rate per arm
  * eligibility     gradeable (ships a sealed verifier), prompt contracts OFF,
                    experiment not WITHDRAWN in EXPERIMENTS.md
  * primary test    exact paired permutation on per-task differences. It uses the
                    magnitude of each difference, where a sign test discards it.
  * secondary       Wilcoxon signed-rank (ranked magnitudes) and the sign test
                    (direction only), reported alongside so the choice is visible.
  * ties            tasks where both arms score identically carry no information about
                    direction and are excluded from the test, but are reported.

Run it after any new results land:  scripts/significance.py
"""

from __future__ import annotations

import collections
import itertools
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lab.benchmarks.task_loader import load_benchmark_tasks  # noqa: E402

TASKS_ROOT = Path.home() / ".cache/agent-rules/frontier-eval/tasks"

# Contracts-off results holding both a baseline and a superstate arm, excluding every
# experiment marked WITHDRAWN in EXPERIMENTS.md.
ELIGIBLE = (
    "ov2_repeats.json",
    "tb_off.json",
    "gated_repeats.json",
    "frontier_raw_gains_5tasks.json",
    "datacurve_clean_9tasks.json",
)
SUPERSTATE_ARMS = {"superstate_mcp", "superstate_daemon", "superstate_solo"}


def _infra_failure(run: dict) -> bool:
    reason = run.get("failure_reason") or ""
    return reason.startswith("Cannot seed workspace") or run.get("wall_clock_sec", 0) < 5


def collect(results_dir: Path) -> list[tuple[str, float, float, int, int]]:
    """One row per task: (name, vanilla rate, superstate rate, n_vanilla, n_superstate)."""
    tasks = {t.name: t for t in load_benchmark_tasks(TASKS_ROOT)}
    agg: dict[str, dict[str, list[int]]] = collections.defaultdict(
        lambda: collections.defaultdict(lambda: [0, 0])
    )
    for name in ELIGIBLE:
        path = results_dir / name
        if not path.is_file():
            continue
        for run in json.loads(path.read_text(encoding="utf-8")):
            task = run["task_id"].split("/")[-1]
            spec = tasks.get(task)
            if spec is None or spec.tests_dir is None or _infra_failure(run):
                continue
            arm = run["arm"]
            group = "vanilla" if arm == "vanilla" else (
                "superstate" if arm in SUPERSTATE_ARMS else None
            )
            if group is None:
                continue
            agg[task][group][0] += bool(run.get("passed"))
            agg[task][group][1] += 1

    rows = []
    for task, arms in sorted(agg.items()):
        van, sup = arms["vanilla"], arms["superstate"]
        if not (van[1] and sup[1]):
            continue
        rows.append((task, van[0] / van[1], sup[0] / sup[1], van[1], sup[1]))
    return rows


def permutation_p(values: list[float]) -> float:
    """Exact two-sided paired permutation test: flip the sign of each task's difference."""
    n = len(values)
    observed = abs(sum(values) / n)
    extreme = sum(
        1
        for flips in itertools.product((1, -1), repeat=n)
        if abs(sum(f * v for f, v in zip(flips, values)) / n) >= observed - 1e-12
    )
    return extreme / 2**n


def wilcoxon_p(values: list[float]) -> float:
    """Exact two-sided Wilcoxon signed-rank, average ranks for ties in magnitude."""
    order = sorted(range(len(values)), key=lambda i: abs(values[i]))
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and abs(values[order[j + 1]]) == abs(values[order[i]]):
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    w_plus = sum(r for r, v in zip(ranks, values) if v > 0)
    total = sum(ranks)
    extreme = 0
    for flips in itertools.product((1, -1), repeat=len(values)):
        w = sum(r for f, r in zip(flips, ranks) if f > 0)
        if w >= w_plus or w <= total - w_plus:
            extreme += 1
    return extreme / 2 ** len(values)


def sign_p(positive: int, n: int) -> float:
    return min(1.0, 2 * sum(math.comb(n, k) for k in range(positive, n + 1)) / 2**n)


def main() -> int:
    rows = collect(Path(__file__).resolve().parent.parent / "results")
    if not rows:
        print("No eligible paired results found.")
        return 1

    informative = [r for r in rows if abs(r[2] - r[1]) > 1e-9]
    ties = len(rows) - len(informative)
    values = [r[2] - r[1] for r in informative]
    ahead = sum(1 for v in values if v > 0)

    print(f"{len(rows)} independent tasks (every run of a task pooled into one observation)")
    print(f"  informative {len(informative)}   ties {ties}")
    print(f"  superstate ahead {ahead}, vanilla ahead {len(values) - ahead}")
    print(f"  mean per-task difference {100 * sum(values) / len(values):+.1f}pp\n")

    if len(values) > 22:  # 2**23 permutations is where exact enumeration stops being cheap
        print("  too many informative tasks for exact enumeration; switch to a sampled test")
        return 1

    print(f"  PRIMARY   exact permutation    p = {permutation_p(values):.4f}")
    print(f"  secondary Wilcoxon signed-rank p = {wilcoxon_p(values):.4f}")
    print(f"  secondary sign test            p = {sign_p(ahead, len(values)):.4f}\n")

    print("  per task:")
    for task, van, sup, nv, ns in sorted(rows, key=lambda r: -(r[2] - r[1])):
        diff = sup - van
        tag = "  (tie)" if abs(diff) <= 1e-9 else ""
        print(
            f"    {task:38s} vanilla {100 * van:5.0f}% (n={nv:2d})   "
            f"superstate {100 * sup:5.0f}% (n={ns:2d})   {100 * diff:+6.0f}pp{tag}"
        )

    print(
        f"\n  The constraint is informative TASKS, not runs: {ties} of {len(rows)} are ties, "
        f"nearly all ceiling tasks both arms always solve.\n  More repeats of an existing task "
        "cannot fix that; more discriminating tasks can. See lab/benchmarks/task_sets.py."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
