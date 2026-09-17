#!/usr/bin/env python3
"""Evaluate Section 10's routing claims with a reproducible split-half validation.

Section 10 of FINDINGS.md claimed a +20pp lift from oracle routing between
single-milestone and multi-milestone execution.

This script tests whether that lift holds out-of-sample or collapses to noise/confound:
1. Reproduces the pooled per-task in-sample oracle numbers.
2. Conducts Monte Carlo split-half cross-validation (train on half of runs to select policy,
   evaluate on the held-out half).
3. Analyzes arm provenance behind the 'always-multi' data.
"""

from __future__ import annotations

import glob
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "results"

GRADEABLE_TB = [
    "terminal-bench/build-cython-ext",
    "terminal-bench/chess-best-move",
    "terminal-bench/code-from-image",
    "terminal-bench/constraints-scheduling",
    "terminal-bench/db-wal-recovery",
    "terminal-bench/dna-insert",
    "terminal-bench/extract-elf",
    "terminal-bench/gcode-to-text",
    "terminal-bench/git-leak-recovery",
    "terminal-bench/kv-store-grpc",
    "terminal-bench/openssl-selfsigned-cert",
    "terminal-bench/regex-log",
    "terminal-bench/vulnerable-secret",
]

DATACURVE_TASKS = [
    "datacurve/anko-typed-variable-bindings",
    "datacurve/arktype-json-schema-refs-dependencies",
    "datacurve/expr-try-catch-errors",
    "datacurve/fastapi-deprecation-response-headers",
    "datacurve/httpx-multipart-response-parsing",
    "datacurve/katex-multicolumn-array-spans",
    "datacurve/meriyah-explicit-resource-declarations",
    "datacurve/python-statemachine-state-data-scoping",
    "datacurve/scc-bounded-memory-spilling",
]


def classify_arm(arm: str | None) -> str | None:
    if arm == "vanilla":
        return "vanilla"
    if arm in ("superstate_mcp", "superstate_solo"):
        return "single"
    if arm in ("superstate_agent_mcp", "superstate_rust", "superstate_rust_inplace"):
        return "multi"
    return None


def load_runs() -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for f in sorted(RESULTS_DIR.glob("*.json")):
        try:
            with open(f, encoding="utf-8") as fp:
                data = json.load(fp)
                if isinstance(data, list):
                    for r in data:
                        if isinstance(r, dict) and r.get("task_id") and r.get("passed") is not None:
                            r["_source_file"] = f.name
                            runs.append(r)
        except Exception:
            pass
    return runs


def evaluate() -> None:
    runs = load_runs()
    print(f"Loaded {len(runs)} total valid task runs across {len(list(RESULTS_DIR.glob('*.json')))} files.")

    runs_by_task = defaultdict(lambda: defaultdict(list))
    multi_sources = Counter()

    for r in runs:
        t = r["task_id"]
        policy = classify_arm(r.get("arm"))
        if policy:
            runs_by_task[t][policy].append(bool(r["passed"]))
            if policy == "multi":
                multi_sources[f"{r['_source_file']} ({r.get('arm')})"] += 1

    print("\n--- Provenance of 'always-multi' data ---")
    for src, cnt in multi_sources.most_common():
        print(f"  {cnt:3d} runs: {src}")

    for name, task_set in [("DATACURVE (9 tasks)", DATACURVE_TASKS), ("TERMINAL-BENCH (13 gradeable tasks)", GRADEABLE_TB)]:
        print(f"\n==========================================")
        print(f"  {name}")
        print(f"==========================================")

        # In-sample summary per task
        print(f"{'Task':<45} | {'Single':<10} | {'Multi':<10} | {'In-Sample Oracle'}")
        print("-" * 80)
        s_rates, m_rates, oracle_rates = [], [], []

        for t in sorted(task_set):
            s = runs_by_task[t]["single"]
            m = runs_by_task[t]["multi"]
            sr = sum(s) / len(s) if s else 0.0
            mr = sum(m) / len(m) if m else 0.0
            orc = max(sr, mr)
            s_rates.append(sr)
            m_rates.append(mr)
            oracle_rates.append(orc)
            t_short = t.split("/")[-1]
            print(f"{t_short:<45} | {sum(s):2d}/{len(s):2d} ({sr*100:4.1f}%) | {sum(m):2d}/{len(m):2d} ({mr*100:4.1f}%) | {orc*100:4.1f}% (picks {'Multi' if mr > sr else 'Single' if sr > mr else 'Tie'})")

        macro_single = sum(s_rates) / len(s_rates)
        macro_multi = sum(m_rates) / len(m_rates)
        macro_oracle = sum(oracle_rates) / len(oracle_rates)
        best_fixed = max(macro_single, macro_multi)
        in_sample_lift = macro_oracle - best_fixed

        print("-" * 80)
        print(f"Macro In-Sample Average:")
        print(f"  Single:          {macro_single*100:5.1f}%")
        print(f"  Multi:           {macro_multi*100:5.1f}%")
        print(f"  In-Sample Oracle:{macro_oracle*100:5.1f}% (+{in_sample_lift*100:.1f}pp over better fixed policy)")

        # Split-half Monte Carlo validation
        num_trials = 1000
        random.seed(42)
        out_of_sample_lifts = []
        test_single_scores = []
        test_multi_scores = []
        test_routed_scores = []

        for _ in range(num_trials):
            t_s_test, t_m_test, t_routed_test = [], [], []

            for t in task_set:
                s_runs = list(runs_by_task[t]["single"])
                m_runs = list(runs_by_task[t]["multi"])

                if len(s_runs) < 2 or len(m_runs) < 2:
                    continue

                random.shuffle(s_runs)
                random.shuffle(m_runs)

                s_split = len(s_runs) // 2
                m_split = len(m_runs) // 2

                s_tr, s_te = s_runs[:s_split], s_runs[s_split:]
                m_tr, m_te = m_runs[:m_split], m_runs[m_split:]

                s_tr_rate = sum(s_tr) / len(s_tr)
                m_tr_rate = sum(m_tr) / len(m_tr)

                s_te_rate = sum(s_te) / len(s_te)
                m_te_rate = sum(m_te) / len(m_te)

                # Choose policy on training half
                if s_tr_rate > m_tr_rate:
                    chosen_test_rate = s_te_rate
                elif m_tr_rate > s_tr_rate:
                    chosen_test_rate = m_te_rate
                else:
                    chosen_test_rate = random.choice([s_te_rate, m_te_rate])

                t_s_test.append(s_te_rate)
                t_m_test.append(m_te_rate)
                t_routed_test.append(chosen_test_rate)

            if not t_routed_test:
                continue

            mean_s = sum(t_s_test) / len(t_s_test)
            mean_m = sum(t_m_test) / len(t_m_test)
            mean_routed = sum(t_routed_test) / len(t_routed_test)
            best_fixed_test = max(mean_s, mean_m)

            out_of_sample_lifts.append(mean_routed - best_fixed_test)
            test_single_scores.append(mean_s)
            test_multi_scores.append(mean_m)
            test_routed_scores.append(mean_routed)

        oos_lift = sum(out_of_sample_lifts) / len(out_of_sample_lifts)
        print(f"\nHeld-Out Split-Half Cross-Validation (1000 trials):")
        print(f"  Test Set Single:  {sum(test_single_scores)/len(test_single_scores)*100:5.1f}%")
        print(f"  Test Set Multi:   {sum(test_multi_scores)/len(test_multi_scores)*100:5.1f}%")
        print(f"  Test Set Routed:  {sum(test_routed_scores)/len(test_routed_scores)*100:5.1f}%")
        print(f"  Held-Out Lift:    {oos_lift*100:+5.1f}pp")
        if oos_lift <= 0:
            print(f"  --> VERDICT: Routing advantage collapses to ZERO or NEGATIVE out-of-sample. Claim falsified.")
        else:
            print(f"  --> VERDICT: Modest held-out lift observed, but note that Multi consists entirely of pre-09-15 confounded arms.")


if __name__ == "__main__":
    evaluate()
