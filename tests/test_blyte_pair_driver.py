"""Tests for BlytePairDriver and dispatch_hook."""

from __future__ import annotations

import io
import json
from pathlib import Path
import runpy
import sys
import textwrap
from typing import Any, Optional

import pytest

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.vanilla import VanillaAdapter
from lab.engine.drivers import dispatch_hook
from lab.engine.drivers.blyte_pair import BlytePairDriver, _aggregate_dispatches
from lab.engine.drivers.container_exec_mcp import ContainerExec

MODEL = "gemini-3.8-flash-high"
IMPL_MODEL = "gemini-3.8-flash-high"


def _report(**overrides: Any) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": 1,
        "outcome": "completed",
        "error": None,
        "model_requested": MODEL,
        "model_id": "gemini/gemini-3.8-flash",
        "context": "folded",
        "gated": False,
        "container": "cnt-1",
        "container_workdir": "/app",
        "duration_seconds": 12.5,
        "turns": 9,
        "empty_turns": 0,
        "tool_calls": 14,
        "gate_attempts": 0,
        "rollbacks": 0,
        "cost_usd": 0.50,
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
    stub = tmp_path / "blyte-stub"
    calls = tmp_path / "calls.jsonl"
    payload = json.dumps(report)
    stub.write_text(
        textwrap.dedent(
            f"""\
            #!{sys.executable}
            import json, os, sys
            from pathlib import Path
            args = sys.argv[1:]
            env_dump = {{k: os.environ[k] for k in os.environ if k.startswith("BLYTE_") or k == "PYTHONPATH"}}
            with open({str(calls)!r}, "a") as fh:
                fh.write(json.dumps({{"argv": args, "env": env_dump}}) + "\\n")
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


def _calls(tmp_path: Path) -> list[dict[str, Any]]:
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


# --- dispatch_hook tests ---


def test_dispatch_hook_success(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    expected = json.dumps({"outcome": "passed", "cost_usd": 0.15})
    monkeypatch.setattr(
        ContainerExec,
        "dispatch",
        lambda self, task, gate, **kw: (expected, False),
    )
    monkeypatch.setattr(
        "sys.stdin", io.StringIO(json.dumps({"task": "Fix bug", "gate": "pytest -q"}))
    )
    code = dispatch_hook.main()
    assert code == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out.strip()) == {"outcome": "passed", "cost_usd": 0.15}


def test_dispatch_hook_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    expected = json.dumps({"outcome": "error", "error": "gate failed"})
    monkeypatch.setattr(
        ContainerExec,
        "dispatch",
        lambda self, task, gate, **kw: (expected, True),
    )
    monkeypatch.setattr(
        "sys.stdin", io.StringIO(json.dumps({"task": "Fix bug", "gate": "pytest -q"}))
    )
    code = dispatch_hook.main()
    assert code == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out.strip()) == {"outcome": "error", "error": "gate failed"}


def test_dispatch_hook_forwards_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: list[tuple[str, str, dict[str, Any]]] = []
    monkeypatch.setattr(
        ContainerExec,
        "dispatch",
        lambda self, task, gate, **kw: (
            recorded.append((task, gate, kw)) or json.dumps({"outcome": "ok"}),
            False,
        ),
    )
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(
            json.dumps({"task": "Fix bug", "gate": "pytest -q", "max_seconds": 300})
        ),
    )
    code = dispatch_hook.main()
    assert code == 0
    assert recorded == [("Fix bug", "pytest -q", {"max_seconds": 300})]


def test_dispatch_hook_module_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ContainerExec,
        "dispatch",
        lambda self, task, gate, **kw: (json.dumps({"outcome": "passed"}), False),
    )
    monkeypatch.setattr(
        "sys.stdin", io.StringIO(json.dumps({"task": "Fix bug", "gate": "pytest"}))
    )
    sys.modules.pop("lab.engine.drivers.dispatch_hook", None)
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("lab.engine.drivers.dispatch_hook", run_name="__main__")
    assert exc.value.code == 0


# --- BlytePairDriver tests ---


def test_driver_argv_contains_flags_and_no_gate(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report(cost_usd=0.10, outcome="completed"))
    driver = BlytePairDriver(model=MODEL, implementer_model=IMPL_MODEL, blyte_bin=stub)
    driver.run(_task(tmp_path), tmp_path, timeout_sec=600.0, container=FakeContainer("cnt-42"))

    calls = _calls(tmp_path)
    assert len(calls) == 1
    argv = calls[0]["argv"]
    env = calls[0]["env"]

    assert "--orchestrate" in argv
    assert "--dispatch-cmd" in argv
    cmd_idx = argv.index("--dispatch-cmd")
    assert f"{sys.executable} -m lab.engine.drivers.dispatch_hook" in argv[cmd_idx + 1]
    assert "--" in argv
    prompt_idx = argv.index("--")
    assert argv[prompt_idx + 1 :] == ["Fix the bug."]

    assert "--gate" not in argv and "-g" not in argv and "--tdd" not in argv
    assert argv[argv.index("--container") + 1] == "cnt-42"
    assert argv[argv.index("--container-workdir") + 1] == "/app"
    assert argv[argv.index("--model") + 1] == MODEL
    assert argv[argv.index("--max-seconds") + 1] == "600"

    assert env["BLYTE_EVAL_CONTAINER"] == "cnt-42"
    assert env["BLYTE_IMPLEMENTER_MODEL"] == IMPL_MODEL
    assert "BLYTE_DISPATCH_DIR" in env
    assert env["BLYTE_BIN"] == str(driver.blyte_bin)
    assert "PYTHONPATH" in env


def test_cost_aggregation_from_two_dispatch_reports(tmp_path: Path) -> None:
    dispatch_dir = tmp_path / "dispatches"
    dispatch_dir.mkdir()
    (dispatch_dir / "dispatch-1.json").write_text(
        json.dumps({"outcome": "gated", "cost_usd": 0.12, "wall_clock_secs": 15.0}),
        encoding="utf-8",
    )
    (dispatch_dir / "dispatch-2.json").write_text(
        json.dumps({"outcome": "passed", "cost_usd": 0.18, "wall_clock_secs": 25.0}),
        encoding="utf-8",
    )

    stub = _make_stub(tmp_path, _report(cost_usd=0.50, outcome="completed"))
    driver = BlytePairDriver(
        model=MODEL,
        implementer_model=IMPL_MODEL,
        blyte_bin=stub,
        dispatch_dir=dispatch_dir,
    )

    t = driver.run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer())

    assert t.success is True
    # Orchestrator cost: 0.50, Implementer cost: 0.12 + 0.18 = 0.30, Total: 0.80
    assert t.cost_usd == pytest.approx(0.80)
    assert t.metrics["frontier_cost_usd"] == pytest.approx(0.50)
    assert t.metrics["implementer_cost_usd"] == pytest.approx(0.30)
    assert t.metrics["dispatches"] == 2
    assert t.metrics["dispatch_outcomes"] == ["gated", "passed"]
    assert t.metrics["implementer_wall_clock_secs"] == pytest.approx(40.0)

    # Check VanillaAdapter provenance propagation
    adapter = VanillaAdapter()
    res = adapter.execute(
        tmp_path,
        _task(tmp_path),
        driver,
        timeout_sec=60.0,
        container=FakeContainer(),
    )
    assert res.cost_usd == pytest.approx(0.80)
    assert res.provenance["frontier_cost_usd"] == pytest.approx(0.50)
    assert res.provenance["implementer_cost_usd"] == pytest.approx(0.30)
    assert res.provenance["dispatches"] == 2
    assert res.provenance["dispatch_outcomes"] == ["gated", "passed"]
    assert res.provenance["implementer_wall_clock_secs"] == pytest.approx(40.0)


def test_cost_aggregation_zero_dispatches(tmp_path: Path) -> None:
    dispatch_dir = tmp_path / "empty_dispatches"
    dispatch_dir.mkdir()
    stub = _make_stub(tmp_path, _report(cost_usd=0.45, outcome="completed"))
    driver = BlytePairDriver(
        model=MODEL,
        implementer_model=IMPL_MODEL,
        blyte_bin=stub,
        dispatch_dir=dispatch_dir,
    )

    t = driver.run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer())

    assert t.success is True
    assert t.cost_usd == pytest.approx(0.45)
    assert t.metrics["frontier_cost_usd"] == pytest.approx(0.45)
    assert t.metrics["implementer_cost_usd"] == 0.0
    assert t.metrics["dispatches"] == 0
    assert t.metrics["dispatch_outcomes"] == []
    assert t.metrics["implementer_wall_clock_secs"] == 0.0


def test_orchestrator_outcome_completed_is_success(tmp_path: Path) -> None:
    # Sealed grader decides pass/fail; orchestrator outcome is not required to be "verified"
    stub = _make_stub(tmp_path, _report(outcome="completed", cost_usd=0.20))
    driver = BlytePairDriver(model=MODEL, implementer_model=IMPL_MODEL, blyte_bin=stub)
    t = driver.run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer())
    assert t.success is True
    assert t.error_message is None


def test_orchestrator_error_is_failure(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report(outcome="error", error="model timeout"), exit_code=1)
    driver = BlytePairDriver(model=MODEL, implementer_model=IMPL_MODEL, blyte_bin=stub)
    t = driver.run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer())
    assert t.success is False
    assert "model timeout" in (t.error_message or "")


def test_missing_report_is_failure(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, None, exit_code=1, stderr="fatal error")
    driver = BlytePairDriver(model=MODEL, implementer_model=IMPL_MODEL, blyte_bin=stub)
    t = driver.run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer())
    assert t.success is False
    assert "no report" in (t.error_message or "")


def test_refuses_to_run_without_sandbox(tmp_path: Path) -> None:
    stub = _make_stub(tmp_path, _report())
    driver = BlytePairDriver(model=MODEL, implementer_model=IMPL_MODEL, blyte_bin=stub)
    t = driver.run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=None)
    assert t.success is False
    assert "container" in (t.error_message or "")


def test_build_command_includes_max_cost_when_env_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("BLYTE_EVAL_MAX_COST", "2.5")
    stub = _make_stub(tmp_path, _report())
    driver = BlytePairDriver(model=MODEL, implementer_model=IMPL_MODEL, blyte_bin=stub)
    cmd = driver.build_command(
        prompt="Fix the bug.",
        container_id="cnt-1",
        report_path=tmp_path / "report.json",
        timeout_sec=60.0,
    )
    assert "--max-cost" in cmd
    idx = cmd.index("--max-cost")
    assert cmd[idx + 1] == "2.5"
    assert idx < cmd.index("--")


def test_build_command_omits_max_cost_when_env_unset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("BLYTE_EVAL_MAX_COST", raising=False)
    stub = _make_stub(tmp_path, _report())
    driver = BlytePairDriver(model=MODEL, implementer_model=IMPL_MODEL, blyte_bin=stub)
    cmd = driver.build_command(
        prompt="Fix the bug.",
        container_id="cnt-1",
        report_path=tmp_path / "report.json",
        timeout_sec=60.0,
    )
    assert "--max-cost" not in cmd


def test_aggregation_with_two_good_reports_and_one_empty_file(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    dispatch_dir = tmp_path / "dispatches"
    dispatch_dir.mkdir()
    (dispatch_dir / "dispatch-1.json").write_text(
        json.dumps({"outcome": "gated", "cost_usd": 0.12, "wall_clock_secs": 10.0}),
        encoding="utf-8",
    )
    (dispatch_dir / "dispatch-2.json").write_text(
        json.dumps({"outcome": "verified", "cost_usd": 0.18, "wall_clock_secs": 20.0}),
        encoding="utf-8",
    )
    (dispatch_dir / "dispatch-3.json").write_text("", encoding="utf-8")

    cost, count, outcomes, wall_clock = _aggregate_dispatches(dispatch_dir)
    assert cost == pytest.approx(0.30)
    assert count == 3
    assert outcomes == ["gated", "verified"]
    assert wall_clock == pytest.approx(30.0)
    assert any("dispatch-3.json" in rec.message for rec in caplog.records)

    stub = _make_stub(tmp_path, _report(cost_usd=0.50, outcome="completed"))
    driver = BlytePairDriver(
        model=MODEL,
        implementer_model=IMPL_MODEL,
        blyte_bin=stub,
        dispatch_dir=dispatch_dir,
    )
    tel = driver.run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer())
    assert tel.cost_usd == pytest.approx(0.80)
    assert tel.metrics["implementer_cost_usd"] == pytest.approx(0.30)
    assert tel.metrics["dispatches"] == 3
    assert tel.metrics["dispatch_outcomes"] == ["gated", "verified"]


def test_clean_exit_inherited_by_pair_driver(tmp_path: Path) -> None:
    stub_ok = _make_stub(tmp_path, _report(outcome="completed", error=None))
    driver_ok = BlytePairDriver(model=MODEL, implementer_model=IMPL_MODEL, blyte_bin=stub_ok)
    tel_ok = driver_ok.run(_task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer())
    assert tel_ok.metrics["clean_exit"] is True

    stub_stopped = _make_stub(
        tmp_path,
        _report(outcome="error", error="stopped after 60s (--max-seconds 60)"),
        exit_code=1,
    )
    driver_stopped = BlytePairDriver(
        model=MODEL, implementer_model=IMPL_MODEL, blyte_bin=stub_stopped
    )
    tel_stopped = driver_stopped.run(
        _task(tmp_path), tmp_path, timeout_sec=60.0, container=FakeContainer()
    )
    assert tel_stopped.metrics["clean_exit"] is False
