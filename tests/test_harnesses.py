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
def blyte_stub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    stub = tmp_path / "blyte"
    stub.write_text("#!/bin/sh\nexit 0\n")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("BLYTE_BIN", str(stub))
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    return stub


def test_parse_accepts_bare_names_and_blyte_options() -> None:
    assert parse_harness_spec("agy") == ("agy", [])
    assert parse_harness_spec("claude") == ("claude", [])
    assert parse_harness_spec("blyte") == ("blyte", [])
    assert parse_harness_spec("blyte[conversational,fold-budget-16k]") == (
        "blyte",
        ["conversational", "fold-budget-16k"],
    )


@pytest.mark.parametrize(
    "spec",
    [
        "vanilla",
        "agy[tdd]",
        "blyte[fast]",
        "blyte[state-only,conversational]",
        "blyte state-only",
        "",
    ],
)
def test_parse_rejects_anything_else(spec: str) -> None:
    with pytest.raises(HarnessSpecError):
        parse_harness_spec(spec)


def test_blyte_specs_build_drivers_named_by_their_settings(blyte_stub: Path) -> None:
    assert build_harness("blyte", MODEL).harness_name == "blyte[folded]"
    built = build_harness("blyte[conversational,fold-budget-16k]", MODEL)
    assert built.harness_name == "blyte[conversational,fold-budget-16k]"
    assert built.model == MODEL


def test_claude_refuses_a_gemini_model() -> None:
    with pytest.raises(HarnessSpecError, match="Claude model"):
        build_harness("claude", MODEL)


def test_the_bare_arm_is_the_pass_through_adapter() -> None:
    assert isinstance(AblationRunner._get_adapter(None, BARE_ARM), VanillaAdapter)  # type: ignore[arg-type]


def test_harnesses_pair_by_task_against_the_baseline() -> None:
    runs = [
        _run("t1", "agy", True, cost=1.0),
        _run("t1", "blyte[folded]", True, cost=2.0),
        _run("t2", "agy", False, cost=1.0),
        _run("t2", "blyte[folded]", True, cost=3.0),
        # No baseline run for t3: excluded, never compared against nothing.
        _run("t3", "blyte[folded]", True, cost=5.0),
    ]
    cmp = compare_harnesses(runs, baseline="agy")
    assert list(cmp) == ["blyte[folded]"]
    e = cmp["blyte[folded]"]
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
        _run("t1", "blyte[folded]", True),
        _run("t1", "blyte[folded]", True),
    ]
    e = compare_harnesses(runs, baseline="agy")["blyte[folded]"]
    assert e["baseline_passes"] == pytest.approx(0.5)
    assert e["passes"] == pytest.approx(1.0)
    assert (e["gained"], e["lost"]) == (1, 0)


def test_by_harness_relabels_copies_and_leaves_results_untouched() -> None:
    runs = [_run("t1", "agy", True)]
    relabelled = by_harness(runs)
    assert relabelled[0].arm == "agy"
    assert runs[0].arm == BARE_ARM


def test_render_names_the_baseline_and_says_so_when_nothing_pairs() -> None:
    runs = [_run("t1", "agy", True), _run("t1", "blyte[folded]", False)]
    text = render_harness_comparison(runs, baseline="agy")
    assert "against `agy`" in text
    assert "| blyte[folded] | 1 |" in text
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
        ["--harnesses", "agy", "blyte[folded]", "blyte[folded,fold-budget-16k]"]
    )
    assert args.harnesses == ["agy", "blyte[folded]", "blyte[folded,fold-budget-16k]"]
    assert module.build_parser().parse_args([]).harnesses is None


@pytest.mark.parametrize(
    "spec",
    [
        "blyte[folded,conversational]",
    ],
)
def test_only_one_context_per_harness(spec: str) -> None:
    with pytest.raises(HarnessSpecError, match="one context"):
        parse_harness_spec(spec)


def test_folded_is_a_blyte_context(blyte_stub: Path) -> None:
    assert build_harness("blyte[folded]", MODEL).harness_name == "blyte[folded]"
    with pytest.raises(HarnessSpecError, match="one context"):
        parse_harness_spec("blyte[folded,conversational]")


def test_fold_budget_is_a_blyte_option(blyte_stub: Path) -> None:
    built = build_harness("blyte[folded,fold-budget-16k]", MODEL)
    assert built.harness_name == "blyte[folded,fold-budget-16k]"
    assert built.fold_budget == 16000
    with pytest.raises(HarnessSpecError, match="one fold budget"):
        parse_harness_spec("blyte[folded,fold-budget-16k,fold-budget-8k]")
    with pytest.raises(HarnessSpecError, match="unknown blyte option"):
        parse_harness_spec("blyte[folded,fold-budget-lots]")


def test_superstate_is_an_alias_for_blyte(blyte_stub: Path) -> None:
    # Renamed 2026-09-24; results and FINDINGS before then use superstate[...].
    assert parse_harness_spec("superstate[folded,fold-budget-16k]") == ("blyte", ["folded", "fold-budget-16k"])
    assert build_harness("superstate[folded]", MODEL).harness_name == "blyte[folded]"


def test_harness_repeats_are_interleaved_not_blocked() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "paired_run", Path(__file__).resolve().parent.parent / "scripts" / "paired_run.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    jobs = module.harness_jobs(["t"], ["agy", "blyte"], 3)
    assert [(rep, drv) for _, _, rep, _, drv in jobs] == [
        (1, "agy"), (1, "blyte"), (2, "agy"), (2, "blyte"), (3, "agy"), (3, "blyte"),
    ]
