"""Tests for the native superstate harness driver.

Driven against a stub `superstate` that honours the --report contract, so nothing here spends
money, needs credentials, or launches Docker. Contract:
superstate/docs/superpowers/specs/2026-09-23-native-harness-eval-surface-design.md
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import textwrap
from typing import Any, Optional

import pytest

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.vanilla import VanillaAdapter
from lab.engine.drivers.agy_cli import estimate_cost_usd
from lab.engine.drivers.superstate_native import (
    CONTAINER_WORKDIR,
    MAX_TURNS,
    SuperstateNativeDriver,
    SuperstateNativeDriverError,
)

MODEL = "gemini-3.8-flash-high"


def _report(**overrides: Any) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": 1,
        "outcome": "verified",
        "error": None,
        "model_requested": MODEL,
        "model_id": "gemini/gemini-3.8-flash",
        "context": "state-only",
        "loop_breaker": True,
        "gated": False,
        "container": "cnt-1",
        "container_workdir": "/app",
        "duration_seconds": 12.5,
        "turns": 9,
        "empty_turns": 0,
        "tool_calls": 14,
        "gate_attempts": 1,
        "rollbacks": 0,
        "usage": {"input": 1000, "cached": 5000, "output": 200, "thinking": 300},
        "interceptions": {"read": 2, "bash": 0},
        "insists": 1,
        "agent_note_keys": [],
    }
    report.update(overrides)
    return report


def _make_stub(
    tmp_path: Path,
    report: Optional[dict[str, Any]],
    exit_code: int = 0,
    stderr: str = "",
    stdout: str = "",
) -> Path:
    """A fake `superstate` that logs its argv, prints `stdout`, and writes `report`."""
    stub = tmp_path / "superstate-stub"
    calls = tmp_path / "calls.jsonl"
    payload = json.dumps(report)
    stub.write_text(
        textwrap.dedent(
            f"""\
            #!{sys.executable}
            import json, sys
            from pathlib import Path
            args = sys.argv[1:]
            with open({str(calls)!r}, "a") as fh:
                fh.write(json.dumps(args) + "\\n")
            payload = {payload!r}
            if payload != "null":
                Path(args[args.index("--report") + 1]).write_text(payload)
            sys.stdout.write({stdout!r})
            sys.stderr.write({stderr!r})
            sys.exit({exit_code})
            """
        ),
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return stub



def _calls(tmp_path: Path) -> list[list[str]]:
    path = tmp_path / "calls.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _task(tmp_path: Path) -> TaskSpec:
    return TaskSpec(
        id="org/task",
        name="task",
        instruction="Fix the bug.",
        docker_image="img",
        task_dir=tmp_path,
    )


class FakeContainer:
    def __init__(self, container_id: str = "cnt-1") -> None:
        self.id = container_id
        self.name = f"eval-{container_id}"


@pytest.fixture(autouse=True)
def _api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")


def _driver(tmp_path: Path, stub: Path, **kwargs: Any) -> SuperstateNativeDriver:
    return SuperstateNativeDriver(model=MODEL, superstate_bin=stub, **kwargs)


def test_command_pins_model_container_workdir_and_budget(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report())
    driver = _driver(tmp_path, stub)
    driver.run(_task(tmp_path), tmp_path, timeout_sec=600.0, container=FakeContainer())

    [argv] = _calls(tmp_path)
    flags = argv[: argv.index("--")]
    assert argv[argv.index("--") + 1 :] == ["Fix the bug."]
    assert flags[flags.index("--model") + 1] == MODEL
    assert flags[flags.index("--context") + 1] == "folded"
    assert flags[flags.index("--container") + 1] == "cnt-1"
    assert flags[flags.index("--container-workdir") + 1] == CONTAINER_WORKDIR == "/app"
    assert flags[flags.index("--max-turns") + 1] == str(MAX_TURNS)
    assert flags[flags.index("--max-seconds") + 1] == "600"
    assert "--report" in flags
    assert "--gate" not in flags and "-g" not in flags
    assert "--no-loop-breaker" not in flags


def test_loop_breaker_ablation_and_context_are_passed(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report())
    driver = _driver(tmp_path, stub, context="conversational", loop_breaker=False)
    driver.run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer())

    [argv] = _calls(tmp_path)
    assert "--no-loop-breaker" in argv
    assert argv[argv.index("--context") + 1] == "conversational"


def test_telemetry_uses_agy_token_accounting(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report())
    report_dir = tmp_path / "reports"
    driver = _driver(tmp_path, stub, report_dir=report_dir)
    t = driver.run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer())

    assert t.success is True
    assert t.error_message is None
    # Fresh input and visible output stay separate from cached and thinking, and all four are
    # priced, exactly as AgyCliDriver now does.
    assert (t.input_tokens, t.output_tokens) == (1000, 200)
    assert (t.cached_input_tokens, t.thinking_tokens) == (5000, 300)
    assert t.cost_usd == estimate_cost_usd(MODEL, 1000, 200, cached_tokens=5000, thinking_tokens=300)
    assert t.raw_response == ""
    assert t.conversation_id is None
    assert driver.last_report is not None
    assert driver.last_report["usage"]["cached"] == 5000
    [saved] = list(report_dir.glob("*.json"))
    assert json.loads(saved.read_text())["insists"] == 1


def test_an_unverified_outcome_is_a_failure(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report(outcome="budget_exhausted"), exit_code=1)
    t = _driver(tmp_path, stub).run(
        _task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer()
    )
    assert t.success is False
    assert t.error_message is not None and "budget_exhausted" in t.error_message
    assert (t.input_tokens, t.output_tokens) == (1000, 200)


def test_a_missing_report_is_a_failure_never_a_pass(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, None, exit_code=1, stderr="thread 'main' panicked")
    t = _driver(tmp_path, stub).run(
        _task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer()
    )
    assert t.success is False
    assert t.error_message is not None
    assert "no report" in t.error_message
    assert "panicked" in t.error_message


def test_a_report_with_an_unknown_schema_is_a_failure(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report(schema_version=99))
    t = _driver(tmp_path, stub).run(
        _task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer()
    )
    assert t.success is False
    assert t.error_message is not None and "no report" in t.error_message


def test_refuses_to_run_without_a_sandbox(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report())
    t = _driver(tmp_path, stub).run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=None)
    assert t.success is False
    assert t.error_message is not None and "container" in t.error_message
    assert _calls(tmp_path) == []


def test_rejects_an_unknown_context(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report())
    with pytest.raises(SuperstateNativeDriverError):
        _driver(tmp_path, stub, context="stateless")


def test_requires_a_gemini_key_before_any_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    stub = _make_stub(tmp_path, _report())
    with pytest.raises(SuperstateNativeDriverError, match="GEMINI_API_KEY"):
        _driver(tmp_path, stub)


def test_binary_is_copied_to_a_run_scoped_path(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report())
    driver = _driver(tmp_path, stub)
    assert driver.superstate_bin != stub
    assert driver.superstate_bin.read_bytes() == stub.read_bytes()
    # A rebuild of the source mid-run must not change what this run executes (EXP-073).
    stub.write_text("#!/bin/sh\nexit 3\n")
    t = driver.run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer())
    assert t.success is True


def test_vanilla_arm_makes_exactly_one_driver_call(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report())
    driver = _driver(tmp_path, stub)
    result = VanillaAdapter().execute(
        tmp_path, _task(tmp_path), driver, timeout_sec=60.0, container=FakeContainer()
    )
    assert len(_calls(tmp_path)) == 1
    assert result.success is True
    assert result.turns == 1
    assert (result.input_tokens, result.output_tokens) == (1000, 200)
    assert (result.cached_input_tokens, result.thinking_tokens) == (5000, 300)


def test_paired_run_accepts_the_superstate_driver() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "paired_run", Path(__file__).resolve().parent.parent / "scripts" / "paired_run.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    args = module.build_parser().parse_args(
        ["--driver", "superstate", "--context", "conversational", "--no-loop-breaker"]
    )
    assert args.driver == "superstate"
    assert args.context == "conversational"
    assert args.no_loop_breaker is True
    defaults = module.build_parser().parse_args([])
    assert defaults.context == "folded"
    assert defaults.no_loop_breaker is False


def test_harness_name_encodes_the_configuration(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report())
    assert _driver(tmp_path, stub).harness_name == "blyte[folded]"
    ablated = _driver(tmp_path, stub, context="conversational", loop_breaker=False)
    assert ablated.harness_name == "blyte[conversational,no-loop-breaker]"


def test_tdd_gate_passes_the_flag_and_names_the_harness(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report())
    driver = _driver(tmp_path, stub, gate="tdd")
    assert driver.harness_name == "blyte[folded,tdd]"
    driver.run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer())
    [argv] = _calls(tmp_path)
    flags = argv[: argv.index("--")]
    assert "--tdd" in flags
    assert "--gate" not in flags and "-g" not in flags


def test_ungated_is_the_default(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report())
    driver = _driver(tmp_path, stub)
    driver.run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer())
    [argv] = _calls(tmp_path)
    assert "--tdd" not in argv


def test_rejects_an_unknown_gate(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report())
    with pytest.raises(SuperstateNativeDriverError):
        _driver(tmp_path, stub, gate="pytest")


def test_harness_name_orders_every_option(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report())
    driver = _driver(tmp_path, stub, context="conversational", loop_breaker=False, gate="tdd")
    assert driver.harness_name == "blyte[conversational,no-loop-breaker,tdd]"


def test_paired_run_accepts_the_tdd_gate() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "paired_run", Path(__file__).resolve().parent.parent / "scripts" / "paired_run.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.build_parser().parse_args(["--gate", "tdd"]).gate == "tdd"
    assert module.build_parser().parse_args([]).gate == "none"


EVENTS = "[Turn 1] looking around\n● read main.go -> 40 lines read\n[Turn 2] done\n"


def test_the_event_stream_is_saved_next_to_the_report(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report(), stdout=EVENTS, stderr="warning: slow\n")
    report_dir = tmp_path / "reports"
    driver = _driver(tmp_path, stub, report_dir=report_dir)
    driver.run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer())

    [report] = list(report_dir.glob("*.json"))
    [events] = list(report_dir.glob("*.events.log"))
    assert events.name == report.name.removesuffix(".json") + ".events.log"
    text = events.read_text()
    assert "● read main.go -> 40 lines read" in text
    assert "warning: slow" in text
    assert driver.last_events_path == events


def test_the_event_stream_is_kept_when_there_is_no_report(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, None, exit_code=1, stdout=EVENTS, stderr="panicked\n")
    report_dir = tmp_path / "reports"
    driver = _driver(tmp_path, stub, report_dir=report_dir)
    t = driver.run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer())

    assert t.success is False
    assert list(report_dir.glob("*.json")) == []
    [events] = list(report_dir.glob("*.events.log"))
    assert "[Turn 2] done" in events.read_text()
    assert "panicked" in events.read_text()


def test_nothing_is_written_without_a_report_dir(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report(), stdout=EVENTS)
    driver = _driver(tmp_path, stub)
    driver.run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer())
    assert driver.last_events_path is None


def test_state_window_context_is_passed_through(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report())
    driver = _driver(tmp_path, stub, context="state-window")
    assert driver.harness_name == "blyte[state-window]"
    driver.run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer())
    [argv] = _calls(tmp_path)
    assert argv[argv.index("--context") + 1] == "state-window"



def test_review_is_passed_and_named(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report())
    driver = _driver(tmp_path, stub, gate="tdd", review=True)
    assert driver.harness_name == "blyte[folded,tdd,review]"
    driver.run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer())
    [argv] = _calls(tmp_path)
    flags = argv[: argv.index("--")]
    assert "--review" in flags and "--tdd" in flags


def test_fold_notes_is_passed_and_named(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report())
    driver = _driver(tmp_path, stub, context="compact", fold_notes=True)
    assert driver.harness_name == "blyte[compact,fold-notes]"
    driver.run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer())
    [argv] = _calls(tmp_path)
    assert "--fold-notes" in argv[: argv.index("--")]


METRIC_EVENTS = (
    "[Turn 1] \n"
    "● read a.py -> 10 lines read\n"
    "● read a.py -> 10 lines read\n"
    "● edit a.py -> replaced 1 line\n"
    "● read a.py -> 10 lines read\n"
    "● bash pytest -q -> exit 1\n"
    "\x1b[31m● bash pytest -q -> exit 1\x1b[0m\n"
    "● grep foo -> 2 matches\n"
)

TURN_USAGE = [
    {"turn": 1, "input": 1000, "cached": 0, "output": 5, "thinking": 0,
     "prompt_messages": 1, "appended": False, "new_chars": 4000},
    {"turn": 2, "input": 300, "cached": 900, "output": 5, "thinking": 0,
     "prompt_messages": 3, "appended": True, "new_chars": 800},
    {"turn": 3, "input": 5000, "cached": 100, "output": 5, "thinking": 0,
     "prompt_messages": 5, "appended": True, "new_chars": 400},
]


def test_run_metrics_counts_rereads_repeats_and_splits_fresh_input() -> None:
    from lab.engine.drivers.superstate_native import run_metrics

    m = run_metrics(_report(turns=3, fold_notes=2, fold_note_failures=1, turn_usage=TURN_USAGE), METRIC_EVENTS)
    assert m["harness_turns"] == 3
    assert (m["fold_notes"], m["fold_note_failures"]) == (2, 1)
    assert (m["reads"], m["unchanged_rereads"], m["changed_rereads"]) == (3, 1, 1)
    assert m["repeated_commands"] == 1
    assert (m["appended_turns"], m["rewritten_turns"]) == (2, 1)
    assert m["fresh_on_appended"] == 5300
    assert m["new_tokens_est_on_appended"] == 300
    assert m["fresh_on_rewritten"] == 1000


def test_run_metrics_tolerates_an_old_report() -> None:
    from lab.engine.drivers.superstate_native import run_metrics

    m = run_metrics(_report(), "")
    assert m["reads"] == 0 and m["appended_turns"] == 0 and m["fold_notes"] == 0


def test_metrics_reach_the_task_result(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report(turns=3, turn_usage=TURN_USAGE), stdout=METRIC_EVENTS)
    driver = _driver(tmp_path, stub, max_cost_usd=4.0)
    result = VanillaAdapter().execute(
        tmp_path, _task(tmp_path), driver, timeout_sec=60.0, container=FakeContainer()
    )
    assert result.provenance["unchanged_rereads"] == 1
    assert result.provenance["harness_turns"] == 3
    assert result.provenance["cost_per_turn"] == pytest.approx(result.cost_usd / 3, rel=1e-3)
    assert result.provenance["max_cost_usd"] == 4.0


def test_fold_budget_and_cost_cap_are_passed(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report())
    driver = _driver(tmp_path, stub, context="compact", fold_budget=16000, max_cost_usd=2.5)
    assert driver.harness_name == "blyte[compact,fold-budget-16k]"
    driver.run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer())
    [argv] = _calls(tmp_path)
    flags = argv[: argv.index("--")]
    assert flags[flags.index("--fold-budget") + 1] == "16000"
    assert flags[flags.index("--max-cost-usd") + 1] == "2.5"


def test_no_cap_and_no_budget_pass_no_flags(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report())
    _driver(tmp_path, stub).run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer())
    [argv] = _calls(tmp_path)
    assert "--fold-budget" not in argv and "--max-cost-usd" not in argv


def test_paired_run_accepts_a_cost_cap() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "paired_run", Path(__file__).resolve().parent.parent / "scripts" / "paired_run.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    args = module.build_parser().parse_args(
        ["--harnesses", "blyte[compact]", "--max-cost-usd", "3"]
    )
    assert args.max_cost_usd == 3.0



def test_run_metrics_reports_the_final_fold_budget() -> None:
    from lab.engine.drivers.superstate_native import run_metrics

    usage = [dict(TURN_USAGE[0], fold_budget=16000), dict(TURN_USAGE[1], fold_budget=24000)]
    assert run_metrics(_report(turn_usage=usage), "")["final_fold_budget"] == 24000
    assert run_metrics(_report(turn_usage=TURN_USAGE), "")["final_fold_budget"] is None
