"""Harness-vs-harness comparison: the evaluation's current question.

Superstate is a harness in its own right, so the question is no longer "what does a layer add to
agy" (the arm table in CLAUDE.md, kept for reproducing bolt-on-era results) but "how do harnesses
compare on the same bare task, model and sealed grader". Every harness runs through the `bare`
pass-through arm: the task instruction untouched, guidance files stripped, no gate from the
evaluation. Anything a harness does beyond that (its loop, context strategy, its own gate) is part
of the harness, and is spelled out in its name, e.g. `superstate[state-only,tdd]`.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from lab.engine.budget_policy import RunTelemetry

#: The pass-through arm every harness runs under. An alias of the legacy `vanilla` adapter.
BARE_ARM = "bare"

_SPEC_RE = re.compile(r"^(?P<name>[a-z]+)(?:\[(?P<opts>[a-z,-]*)\])?$")
_SUPERSTATE_OPTIONS = ("state-only", "conversational", "no-loop-breaker", "tdd")


class HarnessSpecError(ValueError):
    """A harness spec that cannot be turned into a valid measurement."""


def parse_harness_spec(spec: str) -> tuple[str, list[str]]:
    """Split `superstate[conversational,tdd]` into `("superstate", ["conversational", "tdd"])`."""
    m = _SPEC_RE.match(spec.strip())
    if not m:
        raise HarnessSpecError(
            f"not a harness spec: {spec!r} (expected e.g. agy, superstate[state-only,tdd])"
        )
    name = m.group("name")
    opts = [o for o in (m.group("opts") or "").split(",") if o]
    if name in ("agy", "claude"):
        if opts:
            raise HarnessSpecError(f"{name} takes no options, got {opts}")
        return name, opts
    if name == "superstate":
        unknown = [o for o in opts if o not in _SUPERSTATE_OPTIONS]
        if unknown:
            raise HarnessSpecError(
                f"unknown superstate option(s) {unknown}; known: {list(_SUPERSTATE_OPTIONS)}"
            )
        if "state-only" in opts and "conversational" in opts:
            raise HarnessSpecError("choose one context: state-only or conversational")
        return name, opts
    raise HarnessSpecError(f"unknown harness {name!r}; known: agy, claude, superstate")


def build_harness(spec: str, model: str, report_dir: Optional[Path] = None) -> Any:
    """The driver for one harness spec. Every harness gets the same model string."""
    name, opts = parse_harness_spec(spec)
    if name == "agy":
        from lab.engine.drivers.agy_cli import AgyCliDriver

        return AgyCliDriver(model=model)
    if name == "claude":
        if model.startswith("gemini"):
            raise HarnessSpecError(
                f"claude needs a Claude model, got {model!r}; compare it in a separate run "
                "with --model claude-…, since harnesses in one run share a model"
            )
        from lab.engine.drivers.claude_cli import ClaudeCliDriver

        return ClaudeCliDriver(model=model)
    from lab.engine.drivers.superstate_native import SuperstateNativeDriver

    return SuperstateNativeDriver(
        model=model,
        context="conversational" if "conversational" in opts else "state-only",
        loop_breaker="no-loop-breaker" not in opts,
        gate="tdd" if "tdd" in opts else None,
        report_dir=report_dir,
    )


def harness_of(run: RunTelemetry) -> str:
    return str((run.extra or {}).get("harness") or "unknown")


def by_harness(runs: List[RunTelemetry]) -> List[RunTelemetry]:
    """Copies of `runs` labelled by harness, so arm-keyed summaries group by harness."""
    return [replace(r, arm=harness_of(r)) for r in runs]


def compare_harnesses(runs: List[RunTelemetry], baseline: str) -> Dict[str, Dict[str, Any]]:
    """Pair every harness with `baseline`, task by task.

    Repeats count as a pass rate per task. A task the baseline did not run is excluded, never
    compared against nothing.
    """
    cells: Dict[str, Dict[str, List[RunTelemetry]]] = {}
    for r in runs:
        cells.setdefault(r.task_id, {}).setdefault(harness_of(r), []).append(r)

    out: Dict[str, Dict[str, Any]] = {}
    for by_h in cells.values():
        base = by_h.get(baseline)
        if not base:
            continue
        b_rate = sum(x.passed for x in base) / len(base)
        b_cost = sum(x.cost_usd for x in base) / len(base)
        for h, h_runs in by_h.items():
            if h == baseline:
                continue
            h_rate = sum(x.passed for x in h_runs) / len(h_runs)
            e = out.setdefault(
                h,
                {
                    "tasks": 0,
                    "baseline_passes": 0.0,
                    "passes": 0.0,
                    "gained": 0,
                    "lost": 0,
                    "baseline_cost_usd": 0.0,
                    "cost_usd": 0.0,
                },
            )
            e["tasks"] += 1
            e["baseline_passes"] += b_rate
            e["passes"] += h_rate
            e["gained"] += int(h_rate > b_rate)
            e["lost"] += int(h_rate < b_rate)
            e["baseline_cost_usd"] += b_cost
            e["cost_usd"] += sum(x.cost_usd for x in h_runs) / len(h_runs)
    return out


def render_harness_comparison(runs: List[RunTelemetry], baseline: str) -> str:
    cmp = compare_harnesses(runs, baseline)
    if not cmp:
        return f"No paired results: no task was run by both `{baseline}` and another harness."
    lines = [
        f"## Harnesses against `{baseline}` (paired by task; same model, prompt and grader)",
        "",
        "| Harness | Paired tasks | Baseline passes | Passes | Gained | Lost | Baseline cost ($) | Cost ($) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for h in sorted(cmp):
        e = cmp[h]
        lines.append(
            f"| {h} | {e['tasks']} | {e['baseline_passes']:g} | {e['passes']:g} | "
            f"{e['gained']} | {e['lost']} | {e['baseline_cost_usd']:.2f} | {e['cost_usd']:.2f} |"
        )
    lines += [
        "",
        "Small n cannot support a claim: report the paired rows, not a headline rate.",
    ]
    return "\n".join(lines)
