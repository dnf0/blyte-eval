#!/usr/bin/env python3
"""What superstate is worth, per task and per dollar. Pre-specified.

THE P-VALUE IS THE SECONDARY METRIC HERE, DELIBERATELY
------------------------------------------------------
A p-value tests whether the effect is distinguishable from exactly zero. That is not a live
hypothesis: the mechanism is identified (the handoff prompt stops the worker declaring done
while wrong), it is visible in telemetry independent of any outcome, and nobody believes the
true effect is precisely nil. What a p-value mostly reports here is whether our corpus is big
enough -- a fact about the benchmark, not about superstate. The 30 tasks are a convenience
sample, not a draw from a population, so the inferential frame is shaky even at its best.

The decision this evidence serves is "should an agent hand work to superstate", which turns
on how much it converts and what that costs. So the primary outputs are effect size with an
interval, cost per solve, and the number of hand-offs needed per additional solve. The
permutation p is reported last, because uncertainty still has to be stated -- just in units
someone can act on.

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
  * primary         per-task effect size with a bootstrap interval over tasks, plus cost
                    per solve and number-needed-to-treat
  * inference       exact paired permutation on per-task differences, reported last. It uses
                    the magnitude of each difference, where a sign test discards it.
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


# (passed, cost_usd) per run, filled by collect() for tasks that appear in both arms.
COST_CACHE: dict[str, list[tuple[bool, float]]] = {"vanilla": [], "superstate": []}
COST_RUNS: dict = {}


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
            COST_RUNS.setdefault(task, {"vanilla": [], "superstate": []})[group].append(
                (bool(run.get("passed")), run.get("cost_usd") or 0.0)
            )

    rows = []
    for task, arms in sorted(agg.items()):
        if arms["vanilla"][1] and arms["superstate"][1]:
            for group in ("vanilla", "superstate"):
                COST_CACHE[group].extend(COST_RUNS[task][group])
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


def bootstrap_ci(values: list[float], draws: int = 20000, seed: int = 0) -> tuple[float, float]:
    """Percentile interval for the mean per-task difference, resampling TASKS."""
    import random

    rng = random.Random(seed)
    means = sorted(
        sum(rng.choice(values) for _ in values) / len(values) for _ in range(draws)
    )
    return means[int(0.025 * draws)], means[int(0.975 * draws)]


def main() -> int:
    rows = collect(Path(__file__).resolve().parent.parent / "results")
    if not rows:
        print("No eligible paired results found.")
        return 1

    informative = [r for r in rows if abs(r[2] - r[1]) > 1e-9]
    ties = len(rows) - len(informative)
    values = [r[2] - r[1] for r in informative]
    ahead = sum(1 for v in values if v > 0)

    all_diffs = [r[2] - r[1] for r in rows]
    lo, hi = bootstrap_ci(all_diffs)
    print(f"{len(rows)} independent tasks (every run of a task pooled into one observation)")
    print(f"  informative {len(informative)}   ties {ties}   "
          f"superstate ahead {ahead}, vanilla ahead {len(values) - ahead}\n")
    print("  EFFECT")
    print(f"    mean per-task difference   {100 * sum(all_diffs) / len(all_diffs):+.1f}pp"
          f"   95% CI [{100 * lo:+.0f}, {100 * hi:+.0f}]pp")
    ilo, ihi = bootstrap_ci(values)
    print(f"    among informative tasks    {100 * sum(values) / len(values):+.1f}pp"
          f"   95% CI [{100 * ilo:+.0f}, {100 * ihi:+.0f}]pp\n")

    if len(values) > 22:  # 2**23 permutations is where exact enumeration stops being cheap
        print("  too many informative tasks for exact enumeration; switch to a sampled test")
        return 1

    # Cost is what actually decides adoption: an effect nobody can afford is not a result.
    print("  COST")
    for label, key in (("vanilla", "vanilla"), ("superstate", "superstate")):
        runs = COST_CACHE[key]
        solved = sum(1 for passed, _ in runs if passed)
        spend = sum(c for _, c in runs)
        per_run = spend / len(runs)
        per_solve = spend / solved if solved else float("nan")
        print(f"    {label:11s} {solved:3d}/{len(runs):3d} solved   ${per_run:.3f}/run   "
              f"${per_solve:.2f} per solve")
    v, s_ = COST_CACHE["vanilla"], COST_CACHE["superstate"]
    rv = sum(1 for p_, _ in v if p_) / len(v)
    rs = sum(1 for p_, _ in s_ if p_) / len(s_)
    extra = sum(c for _, c in s_) / len(s_) - sum(c for _, c in v) / len(v)
    if rs > rv:
        nnt = 1 / (rs - rv)
        print(f"    hand off {nnt:.1f} tasks to gain one extra solve, "
              f"at ${nnt * extra:.2f} of additional spend")
    print()

    print("  INFERENCE (secondary -- see the module docstring)")
    print(f"    exact permutation    p = {permutation_p(values):.4f}")
    print(f"    Wilcoxon signed-rank p = {wilcoxon_p(values):.4f}")
    print(f"    sign test            p = {sign_p(ahead, len(values)):.4f}\n")

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
