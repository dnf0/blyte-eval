"""Harness-vs-harness comparison: specs, drivers, and per-task pairing. No model or Docker."""

from __future__ import annotations

from pathlib import Path
import stat

import pytest

from lab.engine.adapters.vanilla import VanillaAdapter
from lab.engine.budget_policy import RunTelemetry
from lab.engine.harnesses import (
    BARE_ARM,
    HarnessSpecError,
    build_harness,
    by_harness,
    compare_harnesses,
    parse_harness_spec,
    render_harness_comparison,
)
from lab.engine.runner import AblationRunner

MODEL = "gemini-3.8-flash-high"


def _run(task: str, harness: str, passed: bool, cost: float = 1.0) -> RunTelemetry:
    return RunTelemetry(
        task_id=task,
        arm=BARE_ARM,
        passed=passed,
        wall_clock_sec=10.0,
        cost_usd=cost,
        input_tokens=100,
        output_tokens=10,
        extra={"harness": harness},
    )


@pytest.fixture
def superstate_stub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    stub = tmp_path / "superstate"
    stub.write_text("#!/bin/sh\nexit 0\n")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("SUPERSTATE_BIN", str(stub))
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    return stub


def test_parse_accepts_bare_names_and_superstate_options() -> None:
    assert parse_harness_spec("agy") == ("agy", [])
    assert parse_harness_spec("claude") == ("claude", [])
    assert parse_harness_spec("superstate") == ("superstate", [])
    assert parse_harness_spec("superstate[conversational,no-loop-breaker,tdd]") == (
        "superstate",
        ["conversational", "no-loop-breaker", "tdd"],
    )


@pytest.mark.parametrize(
    "spec",
    [
        "vanilla",
        "agy[tdd]",
        "superstate[fast]",
        "superstate[state-only,conversational]",
        "superstate state-only",
        "",
    ],
)
def test_parse_rejects_anything_else(spec: str) -> None:
    with pytest.raises(HarnessSpecError):
        parse_harness_spec(spec)


def test_superstate_specs_build_drivers_named_by_their_settings(superstate_stub: Path) -> None:
    assert build_harness("superstate", MODEL).harness_name == "superstate[folded]"
    built = build_harness("superstate[conversational,no-loop-breaker,tdd]", MODEL)
    assert built.harness_name == "superstate[conversational,no-loop-breaker,tdd]"
    assert built.model == MODEL


def test_claude_refuses_a_gemini_model() -> None:
    with pytest.raises(HarnessSpecError, match="Claude model"):
        build_harness("claude", MODEL)


def test_the_bare_arm_is_the_pass_through_adapter() -> None:
    assert isinstance(AblationRunner._get_adapter(None, BARE_ARM), VanillaAdapter)  # type: ignore[arg-type]


def test_harnesses_pair_by_task_against_the_baseline() -> None:
    runs = [
        _run("t1", "agy", True, cost=1.0),
        _run("t1", "superstate[state-only]", True, cost=2.0),
        _run("t2", "agy", False, cost=1.0),
        _run("t2", "superstate[state-only]", True, cost=3.0),
        # No baseline run for t3: excluded, never compared against nothing.
        _run("t3", "superstate[state-only]", True, cost=5.0),
    ]
    cmp = compare_harnesses(runs, baseline="agy")
    assert list(cmp) == ["superstate[state-only]"]
    e = cmp["superstate[state-only]"]
    assert e["tasks"] == 2
    assert e["baseline_passes"] == 1
    assert e["passes"] == 2
    assert (e["gained"], e["lost"]) == (1, 0)
    assert e["baseline_cost_usd"] == pytest.approx(2.0)
    assert e["cost_usd"] == pytest.approx(5.0)


def test_repeats_count_as_a_pass_rate_per_task() -> None:
    runs = [
        _run("t1", "agy", True),
        _run("t1", "agy", False),
        _run("t1", "superstate[state-only]", True),
        _run("t1", "superstate[state-only]", True),
    ]
    e = compare_harnesses(runs, baseline="agy")["superstate[state-only]"]
    assert e["baseline_passes"] == pytest.approx(0.5)
    assert e["passes"] == pytest.approx(1.0)
    assert (e["gained"], e["lost"]) == (1, 0)


def test_by_harness_relabels_copies_and_leaves_results_untouched() -> None:
    runs = [_run("t1", "agy", True)]
    relabelled = by_harness(runs)
    assert relabelled[0].arm == "agy"
    assert runs[0].arm == BARE_ARM


def test_render_names_the_baseline_and_says_so_when_nothing_pairs() -> None:
    runs = [_run("t1", "agy", True), _run("t1", "superstate[state-only]", False)]
    text = render_harness_comparison(runs, baseline="agy")
    assert "against `agy`" in text
    assert "| superstate[state-only] | 1 |" in text
    empty = render_harness_comparison([_run("t1", "agy", True)], baseline="agy")
    assert empty.startswith("No paired results")


def test_paired_run_accepts_harnesses() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "paired_run", Path(__file__).resolve().parent.parent / "scripts" / "paired_run.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    args = module.build_parser().parse_args(
        ["--harnesses", "agy", "superstate[state-only]", "superstate[state-only,tdd]"]
    )
    assert args.harnesses == ["agy", "superstate[state-only]", "superstate[state-only,tdd]"]
    assert module.build_parser().parse_args([]).harnesses is None


def test_state_window_is_a_superstate_context(superstate_stub: Path) -> None:
    assert parse_harness_spec("superstate[state-window,tdd]") == (
        "superstate",
        ["state-window", "tdd"],
    )
    assert build_harness("superstate[state-window]", MODEL).harness_name == "superstate[state-window]"


@pytest.mark.parametrize(
    "spec",
    [
        "superstate[state-window,state-only]",
        "superstate[state-window,conversational]",
    ],
)
def test_only_one_context_per_harness(spec: str) -> None:
    with pytest.raises(HarnessSpecError, match="one context"):
        parse_harness_spec(spec)


def test_folded_is_a_superstate_context(superstate_stub: Path) -> None:
    assert build_harness("superstate[folded]", MODEL).harness_name == "superstate[folded]"
    with pytest.raises(HarnessSpecError, match="one context"):
        parse_harness_spec("superstate[folded,conversational]")


def test_review_is_a_superstate_option(superstate_stub: Path) -> None:
    built = build_harness("superstate[folded,tdd,review]", MODEL)
    assert built.harness_name == "superstate[folded,tdd,review]"
    assert build_harness("superstate[conversational]", MODEL).harness_name == "superstate[conversational]"
