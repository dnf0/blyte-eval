import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from typing import Any, Optional

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.base import AgentDriver, DriverTelemetry
from lab.engine.adapters.superstate_daemon import (
    AUTO_ROLLBACK_ENV_FLAG,
    SuperstateDaemonAdapter,
    auto_rollback_enabled,
)

import pytest


@pytest.fixture
def derivation_on(monkeypatch):
    """Gate derivation is opt-in: the daemon does not author its own contract by default.

    These tests exercise that opt-in machinery, so they enable it explicitly rather than
    relying on a default that would invert the handoff.
    """
    from lab.engine.adapters.superstate_daemon import GATE_DERIVATION_ENV_FLAG

    monkeypatch.setenv(GATE_DERIVATION_ENV_FLAG, "1")


def test_daemon_adapter_initialization() -> None:
    adapter = SuperstateDaemonAdapter(driver_preset="agy")
    assert adapter.name == "superstate_daemon"
    assert adapter.driver_preset == "agy"


def test_daemon_adapter_run_mocked(tmp_path: Path) -> None:
    adapter = SuperstateDaemonAdapter(driver_preset="agy", poll_interval_sec=0.01)
    task = TaskSpec(
        id="daemon-test",
        name="Daemon Test",
        instruction="Complete task autonomously",
        docker_image="test:latest",
    )

    state_dir = tmp_path / ".agent-state"
    daemons_dir = state_dir / "daemons"
    daemons_dir.mkdir(parents=True, exist_ok=True)
    pid_file = daemons_dir / "default.pid"
    pid_file.write_text("999999\n", encoding="utf-8")

    state_file = state_dir / "state.json"
    state_file.write_text('{"status": "completed", "step": 1, "completed_tasks": [{"id": "task-1"}]}', encoding="utf-8")

    with patch("lab.engine.adapters.superstate_daemon.is_pid_alive", side_effect=[True, False]), \
         patch.object(adapter, "_init_daemon_state", return_value=True), \
         patch.object(adapter, "_spawn_daemon", return_value=True), \
         patch.object(adapter, "_run_gate_command", return_value=(True, 0, "pass")):
        result = adapter.run_task(
            task=task,
            workspace_path=tmp_path,
            driver=None,
            budget_sec=60.0,
        )

    assert result.success is True
    assert result.harness_name == "superstate_daemon"
    assert result.task_id == "daemon-test"


def _task_with_verifier(verification_cmd: str) -> TaskSpec:
    return TaskSpec(
        id="daemon-verifier",
        name="Daemon Verifier",
        instruction="Do work",
        docker_image="test:latest",
        verification_cmd=verification_cmd,
    )


def test_execute_sanitizes_held_out_verifier(tmp_path: Path) -> None:
    """A sealed held-out verifier must never become the daemon's gate.

    Gating on `/tests/...` would let the daemon read the answer key it is being
    scored against. execute() replaces it with `true`; the real verdict is taken
    later by the harness against the sealed suite.
    """
    adapter = SuperstateDaemonAdapter(driver_preset="agy", poll_interval_sec=0.01)
    with patch.object(adapter, "_init_daemon_state", return_value=False) as mock_init:
        adapter.execute(tmp_path, _task_with_verifier("bash /tests/test.sh"))
    assert mock_init.call_args[0][2] == "true"


def test_execute_preserves_local_verifier(tmp_path: Path) -> None:
    """A task-local verifier is a legitimate gate and must be passed through."""
    adapter = SuperstateDaemonAdapter(driver_preset="agy", poll_interval_sec=0.01)
    with patch.object(adapter, "_init_daemon_state", return_value=False) as mock_init:
        adapter.execute(tmp_path, _task_with_verifier("pytest tests/local"))
    assert mock_init.call_args[0][2] == "pytest tests/local"


def test_daemon_resolves_rust_engine_not_python() -> None:
    """The daemon arm must resolve the Rust engine, which is the only one with `state daemon`.

    Regression guard: this arm silently depended on ~/.local/bin/superstate being a
    symlink to the Rust build, so a bare find_superstate_binary() (which defaults to
    ENGINE_PYTHON) happened to return Rust. Once ENGINE_PYTHON was corrected to point at
    agent-rules, every daemon spawn failed with "Failed to spawn superstate daemon".
    """
    adapter = SuperstateDaemonAdapter()
    assert adapter.superstate_bin is not None, "daemon arm needs a Rust superstate build"
    assert "agent-rules" not in str(adapter.superstate_bin)
    help_text = subprocess.run(
        [str(adapter.superstate_bin), "state", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout
    assert "daemon" in help_text, "resolved binary exposes no `state daemon` verb"


class _StubDriver:
    """Driver stub returning a canned gate proposal."""

    cli_path = "/usr/bin/agy"
    model = "gemini-3.8-flash-high"

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = 0

    def run(self, *_args: object, **_kwargs: object) -> SimpleNamespace:
        self.calls += 1
        return SimpleNamespace(raw_response=self.response, input_tokens=11, output_tokens=7)


def test_gate_rejects_a_proposal_that_already_passes(tmp_path: Path, derivation_on) -> None:
    """A gate that passes before any work cannot discriminate, so it must be refused.

    This is the failure that made the daemon arm score 0-1/5: with a gate that always
    passed, the daemon completed after one driver turn and never engaged retry.
    """
    adapter = SuperstateDaemonAdapter(driver_preset="agy")
    driver = _StubDriver("echo already-done")
    gate, telemetry = adapter._derive_gate(
        tmp_path, _task_with_verifier("bash /tests/test.sh"), driver, None, 60.0
    )
    assert gate == "true", "a gate that already passes must be rejected"
    # Authoring turn plus critique turn, both costed.
    assert telemetry is not None and telemetry.input_tokens == 22


def test_gate_accepts_a_proposal_that_currently_fails(tmp_path: Path, derivation_on) -> None:
    adapter = SuperstateDaemonAdapter(driver_preset="agy")
    proposed = "test -f ./artifact-the-task-must-produce"
    driver = _StubDriver(proposed)
    gate, _ = adapter._derive_gate(
        tmp_path, _task_with_verifier("bash /tests/test.sh"), driver, None, 60.0
    )
    assert gate == proposed


def test_gate_refuses_to_read_the_sealed_grader(tmp_path: Path, derivation_on) -> None:
    """The driver must never gate on /tests/ -- that is the answer key."""
    adapter = SuperstateDaemonAdapter(driver_preset="agy")
    driver = _StubDriver("bash /tests/test.sh")
    gate, _ = adapter._derive_gate(
        tmp_path, _task_with_verifier("bash /tests/test.sh"), driver, None, 60.0
    )
    assert gate == "true"


def test_driver_wrapper_pins_model_and_captures_usage(tmp_path: Path) -> None:
    """The daemon expands the bare `agy` preset without --model or JSON output.

    Without the wrapper the arm silently ran a different model than every other arm
    and reported $0.00 / 0 tokens.
    """
    adapter = SuperstateDaemonAdapter(driver_preset="agy")
    wrapper = adapter._write_driver_wrapper(tmp_path, _StubDriver(""))
    assert wrapper is not None
    script = wrapper.read_text()
    assert "--model" in script and "gemini-3.8-flash-high" in script
    assert "--output-format" in script and "json" in script

    turns = tmp_path / ".agent-state" / "driver-turns"
    (turns / "turn-1-1.json").write_text(
        json.dumps({"usage": {"input_tokens": 100, "output_tokens": 20}})
    )
    (turns / "turn-2-2.json").write_text(
        json.dumps({"usage": {"input_tokens": 5, "output_tokens": 3}})
    )
    assert adapter._collect_driver_telemetry(tmp_path) == (105, 23, 2)


def test_collect_driver_telemetry_tolerates_corrupt_turns(tmp_path: Path) -> None:
    adapter = SuperstateDaemonAdapter(driver_preset="agy")
    turns = tmp_path / ".agent-state" / "driver-turns"
    turns.mkdir(parents=True)
    (turns / "turn-1-1.json").write_text("not json{{")
    (turns / "turn-2-2.json").write_text(json.dumps({"usage": {"input_tokens": 9}}))
    # The corrupt file still counts as a turn: the worker was invoked, only its usage
    # is unreadable. Dropping it would under-report iteration, which is the failure
    # this accounting was introduced to fix.
    assert adapter._collect_driver_telemetry(tmp_path) == (9, 0, 2)


def test_wrapper_supplies_the_environment_contract_when_containerised(tmp_path: Path) -> None:
    """The daemon's worker must be told where the project environment actually is.

    The Rust daemon renders its own turnkey prompt and never appends the contract the
    Python driver adds, so the worker did not know dependencies lived in the container
    or that `./run-in-container` existed. It worked on the host while its own gate ran
    inside the container -- the two halves of the handoff on different environments.
    """
    adapter = SuperstateDaemonAdapter(driver_preset="agy")
    wrapper = adapter._write_driver_wrapper(tmp_path, _StubDriver(""), container=object())
    assert wrapper is not None
    script = wrapper.read_text()
    assert "environment-contract.md" in script
    contract = (tmp_path / ".agent-state" / "environment-contract.md").read_text()
    assert "./run-in-container" in contract


def test_wrapper_omits_the_contract_without_a_container(tmp_path: Path) -> None:
    adapter = SuperstateDaemonAdapter(driver_preset="agy")
    wrapper = adapter._write_driver_wrapper(tmp_path, _StubDriver(""), container=None)
    assert wrapper is not None
    assert "environment-contract.md" not in wrapper.read_text()


class _ScriptedDriver:
    """Driver stub returning a different response per successive turn."""

    cli_path = "/usr/bin/agy"
    model = "gemini-3.8-flash-high"

    def __init__(self, *responses: str) -> None:
        self.responses = list(responses)
        self.calls = 0

    def run(self, *_args: object, **_kwargs: object) -> SimpleNamespace:
        response = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return SimpleNamespace(raw_response=response, input_tokens=10, output_tokens=5)


def test_critique_widens_an_incomplete_gate(tmp_path: Path, derivation_on) -> None:
    """An incomplete gate is worse than no gate: the worker stops the moment it passes.

    build-cython-ext failed exactly this way -- the gate checked only the snippet the task
    called "at the very least", so the two requirements it omitted were never done and the
    sealed grader failed on precisely those.
    """
    adapter = SuperstateDaemonAdapter(driver_preset="agy")
    narrow = "test -f ./snippet-runs"
    widened = "test -f ./snippet-runs && test -f ./suite-passes"
    driver = _ScriptedDriver(narrow, widened)

    gate, telemetry = adapter._derive_gate(
        tmp_path, _task_with_verifier("bash /tests/test.sh"), driver, None, 60.0
    )
    assert gate == widened, "critique must widen a gate that misses requirements"
    assert driver.calls == 2, "expected one authoring turn and one critique turn"
    # Both turns must be costed, not just the first.
    assert telemetry is not None and telemetry.input_tokens == 20


def test_critique_cannot_weaken_the_gate(tmp_path: Path, derivation_on) -> None:
    """A critique may only strengthen the contract. A no-op reply keeps the original."""
    adapter = SuperstateDaemonAdapter(driver_preset="agy")
    original = "test -f ./artifact"
    driver = _ScriptedDriver(original, "true")

    gate, _ = adapter._derive_gate(
        tmp_path, _task_with_verifier("bash /tests/test.sh"), driver, None, 60.0
    )
    assert gate == original


def test_critique_rejecting_an_already_passing_gate(tmp_path: Path, derivation_on) -> None:
    """A widened gate that already passes cannot discriminate, so the original stands."""
    adapter = SuperstateDaemonAdapter(driver_preset="agy")
    original = "test -f ./artifact"
    driver = _ScriptedDriver(original, "echo always-passes")

    gate, _ = adapter._derive_gate(
        tmp_path, _task_with_verifier("bash /tests/test.sh"), driver, None, 60.0
    )
    assert gate == original


def test_gate_turn_gets_more_than_the_driver_default_timeout() -> None:
    """Gate authoring must not be capped so tightly that it silently degrades to no-gate.

    Regression: the completeness prompt pushed the authoring turn past a 300s cap on all
    five tasks. agy timed out, returned an empty response, and every gate fell back to
    `true` -- a whole run measuring "no gate" while appearing to measure gate quality.
    """
    from lab.engine.adapters.superstate_daemon import GATE_TURN_TIMEOUT_SEC

    assert GATE_TURN_TIMEOUT_SEC > 300.0


def test_timed_out_gate_turn_falls_back_loudly(tmp_path: Path, caplog, derivation_on) -> None:
    """A gate that cannot be derived must be visible in the log, not silent."""
    adapter = SuperstateDaemonAdapter(driver_preset="agy")
    driver = _StubDriver("")  # empty response, as a timed-out turn produces
    with caplog.at_level("WARNING"):
        gate, _ = adapter._derive_gate(
            tmp_path, _task_with_verifier("bash /tests/test.sh"), driver, None, 60.0
        )
    assert gate == "true"
    assert any("no parseable command" in r.message for r in caplog.records)


def test_daemon_does_not_author_its_own_gate_by_default(tmp_path: Path) -> None:
    """The daemon executes against a contract it is handed; it does not invent one.

    superstate_handoff's premise is that the caller states what "done" means. A daemon that
    authors its own gate moves the specification inside the thing being specified, grades
    itself against a contract it wrote, and makes that contract a per-run random variable.
    """
    adapter = SuperstateDaemonAdapter(driver_preset="agy")
    driver = _StubDriver("test -f ./something")
    gate, _ = adapter._derive_gate(
        tmp_path, _task_with_verifier("bash /tests/test.sh"), driver, None, 60.0
    )
    assert gate == "true", "an unsupplied contract must hand off ungated, not be invented"
    assert driver.calls == 0, "the driver must not be consulted to author a gate"


def test_gate_derivation_can_be_re_enabled_for_reproduction() -> None:
    """Retained behind a flag so the 2026-09-15 runs that used it stay reproducible."""
    import os
    from unittest.mock import patch

    from lab.engine.adapters.superstate_daemon import (
        GATE_DERIVATION_ENV_FLAG,
        gate_derivation_enabled,
    )

    with patch.dict(os.environ, {}, clear=True):
        assert gate_derivation_enabled() is False
    with patch.dict(os.environ, {GATE_DERIVATION_ENV_FLAG: "1"}, clear=True):
        assert gate_derivation_enabled() is True


def test_caller_supplied_contract_is_still_honoured(tmp_path: Path) -> None:
    """A fixture, or a task-declared non-sealed verifier, is the caller's contract."""
    adapter = SuperstateDaemonAdapter(driver_preset="agy")
    driver = _StubDriver("")
    gate, _ = adapter._derive_gate(
        tmp_path, _task_with_verifier("pytest tests/local"), driver, None, 60.0
    )
    assert gate == "pytest tests/local"
    assert driver.calls == 0


def test_wrapper_passes_the_task_budget_as_print_timeout(tmp_path: Path) -> None:
    """agy truncates any turn longer than its 5-minute default --print-timeout.

    AgyCliDriver sets this for every other arm. The daemon spawns its own worker and so was
    silently capped at 5 minutes regardless of the budget the task was granted -- which is
    why it held up on short tasks (db-wal-recovery ~2.7 min, openssl ~2.3 min, both 5/5) and
    failed the long one (build-cython-ext, 30-45 min, 0-2/5).
    """
    adapter = SuperstateDaemonAdapter(driver_preset="agy")
    wrapper = adapter._write_driver_wrapper(
        tmp_path, _StubDriver(""), container=None, budget_sec=2400
    )
    assert wrapper is not None
    script = wrapper.read_text()
    assert "--print-timeout 2400s" in script


def test_wrapper_print_timeout_never_below_a_usable_floor(tmp_path: Path) -> None:
    adapter = SuperstateDaemonAdapter(driver_preset="agy")
    wrapper = adapter._write_driver_wrapper(
        tmp_path, _StubDriver(""), container=None, budget_sec=5
    )
    assert wrapper is not None
    script = wrapper.read_text()
    assert "--print-timeout 60s" in script


def test_daemon_records_its_gate_verdict(tmp_path: Path) -> None:
    """Gate precision must be computable for the daemon, not just superstate_mcp.

    run.json derives `gates_failed` from milestone records. The daemon wrote none, so an
    empty list meant either "gate passed" or "gate never ran" and the two could not be
    told apart -- leaving EXP-047's 60%-precision/zero-recall finding measurable on one
    arm only.
    """
    from lab.engine.trace import RunRecorder

    adapter = SuperstateDaemonAdapter(driver_preset="agy", poll_interval_sec=0.01)
    task = TaskSpec(
        id="daemon-gate-trace",
        name="Daemon Gate Trace",
        instruction="Do work",
        docker_image="test:latest",
        verification_cmd="pytest tests/local",
    )

    state_dir = tmp_path / ".agent-state"
    (state_dir / "daemons").mkdir(parents=True, exist_ok=True)
    (state_dir / "daemons" / "default.pid").write_text("999999\n", encoding="utf-8")
    (state_dir / "state.json").write_text(
        '{"status": "completed", "step": 1, "completed_tasks": [{"id": "task-1"}]}',
        encoding="utf-8",
    )

    logs = tmp_path / "logs"
    recorder = RunRecorder(logs, task_id=task.id, arm=adapter.name)

    with patch("lab.engine.adapters.superstate_daemon.is_pid_alive", side_effect=[True, False]), \
         patch.object(adapter, "_init_daemon_state", return_value=True), \
         patch.object(adapter, "_spawn_daemon", return_value=True), \
         patch.object(adapter, "_run_gate_command", return_value=(False, 1, "gate said no")):
        adapter.execute(tmp_path, task, driver=None, recorder=recorder)

    assert recorder.milestones, "the daemon must record a milestone carrying its gate verdict"
    record = recorder.milestones[0]
    assert record.gate_ran is True
    assert record.gate_passed is False
    assert record.gate_exit_code == 1
    assert record.verify_cmd == "pytest tests/local"

    recorder.write_run_record(telemetry=None)
    run_record = json.loads((logs / "run.json").read_text(encoding="utf-8"))
    assert run_record["gates_failed"], "a failing gate must show up in run.json"


def test_fixture_short_circuits_derivation_unless_explicitly_ignored(tmp_path: Path) -> None:
    """Gate authorship cannot be measured while a fixture exists for every task.

    _derive_gate returns the hand-authored fixture before reaching the derivation path, so
    SUPERSTATE_EVAL_DERIVE_GATES=1 alone measures nothing -- GATE_FIXTURES covers all 30
    tasks. The bypass flag is what makes the question testable: can an agent write a gate
    better than its own judgement about when it is done?
    """
    import os

    from lab.engine.adapters.superstate_daemon import (
        IGNORE_FIXTURES_ENV_FLAG,
        ignore_gate_fixtures,
    )
    from lab.benchmarks.gate_fixtures import agent_gate_for

    assert agent_gate_for("db-wal-recovery"), "precondition: this task has a fixture"
    assert not ignore_gate_fixtures(), "the bypass must default OFF"

    src = (
        Path(__file__).resolve().parents[1] / "lab/engine/adapters/superstate_daemon.py"
    ).read_text(encoding="utf-8")
    assert "None if ignore_gate_fixtures() else agent_gate_for" in src, (
        "the fixture lookup must be skippable, or derivation is unreachable"
    )
    assert IGNORE_FIXTURES_ENV_FLAG == "SUPERSTATE_EVAL_IGNORE_GATE_FIXTURES"
    assert os.environ.get(IGNORE_FIXTURES_ENV_FLAG) is None or ignore_gate_fixtures()


def test_daemon_adapter_passes_review_blocking_flags(tmp_path: Path) -> None:
    """When advisory review is enabled, both --advisory-review and --review-blocking must be passed."""
    adapter = SuperstateDaemonAdapter(driver_preset="agy", advisory_review=True)
    assert adapter.advisory_review is True
    assert adapter.review_blocking is True
    assert adapter.get_provenance()["advisory_review"] is True
    assert adapter.get_provenance()["review_blocking"] is True

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = SimpleNamespace(returncode=0)
        adapter._spawn_daemon(tmp_path)  # noqa: SLF001
        called_cmd = mock_run.call_args[0][0]
        assert "--advisory-review" in called_cmd
        assert "--review-blocking" in called_cmd


def test_daemon_adapter_can_disable_review_blocking(tmp_path: Path) -> None:
    """When review_blocking is explicitly False, only --advisory-review is passed."""
    adapter = SuperstateDaemonAdapter(driver_preset="agy", advisory_review=True, review_blocking=False)
    assert adapter.advisory_review is True
    assert adapter.review_blocking is False

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = SimpleNamespace(returncode=0)
        adapter._spawn_daemon(tmp_path)  # noqa: SLF001
        called_cmd = mock_run.call_args[0][0]
        assert "--advisory-review" in called_cmd
        assert "--review-blocking" not in called_cmd


class MockDriver(AgentDriver):
    """Mock agent driver for testing."""

    def run(
        self,
        task: TaskSpec,
        workspace_path: Path,
        prompt_override: Optional[str] = None,
        conversation_id: Optional[str] = None,
        timeout_sec: float = 3600.0,
        container: Any = None,
    ) -> DriverTelemetry:
        return DriverTelemetry(success=True, raw_response="done", duration_seconds=1.0)


def test_daemon_adapter_passes_auto_rollback_flag() -> None:
    """When auto_rollback is True, --auto-rollback is appended to the daemon spawn command."""
    adapter = SuperstateDaemonAdapter(driver=MockDriver(), auto_rollback=True)
    assert adapter.auto_rollback is True
    assert adapter.get_provenance()["auto_rollback"] is True

    cmd = adapter._build_daemon_spawn_cmd()  # noqa: SLF001
    assert "--auto-rollback" in cmd


def test_daemon_adapter_can_disable_auto_rollback() -> None:
    """When auto_rollback is False, --no-auto-rollback is appended to the daemon spawn command."""
    adapter = SuperstateDaemonAdapter(driver=MockDriver(), auto_rollback=False)
    assert adapter.auto_rollback is False
    assert adapter.get_provenance()["auto_rollback"] is False

    cmd = adapter._build_daemon_spawn_cmd()  # noqa: SLF001
    assert "--no-auto-rollback" in cmd
    assert "--auto-rollback" not in cmd


def test_daemon_adapter_auto_rollback_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """AUTO_ROLLBACK_ENV_FLAG controls auto_rollback default when set."""
    monkeypatch.delenv(AUTO_ROLLBACK_ENV_FLAG, raising=False)
    assert auto_rollback_enabled()
    adapter_default = SuperstateDaemonAdapter(driver=MockDriver())
    assert adapter_default.auto_rollback is True
    assert "--auto-rollback" in adapter_default._build_daemon_spawn_cmd()  # noqa: SLF001

    for val in ("1", "true", "yes", "True", "YES"):
        monkeypatch.setenv(AUTO_ROLLBACK_ENV_FLAG, val)
        assert auto_rollback_enabled()
        adapter_enabled = SuperstateDaemonAdapter(driver=MockDriver())
        assert adapter_enabled.auto_rollback is True
        assert "--auto-rollback" in adapter_enabled._build_daemon_spawn_cmd()  # noqa: SLF001

    for val in ("0", "false", "no", "anything_else"):
        monkeypatch.setenv(AUTO_ROLLBACK_ENV_FLAG, val)
        assert not auto_rollback_enabled()
        adapter_disabled = SuperstateDaemonAdapter(driver=MockDriver())
        assert adapter_disabled.auto_rollback is False
        assert "--no-auto-rollback" in adapter_disabled._build_daemon_spawn_cmd()  # noqa: SLF001


def test_daemon_adapter_spawn_daemon_forwards_auto_rollback(tmp_path: Path) -> None:
    """_spawn_daemon includes --auto-rollback or --no-auto-rollback in subprocess.run command."""
    adapter = SuperstateDaemonAdapter(driver=MockDriver(), auto_rollback=True)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = SimpleNamespace(returncode=0)
        adapter._spawn_daemon(tmp_path)  # noqa: SLF001
        called_cmd = mock_run.call_args[0][0]
        assert "--auto-rollback" in called_cmd

    adapter_disabled = SuperstateDaemonAdapter(driver=MockDriver(), auto_rollback=False)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = SimpleNamespace(returncode=0)
        adapter_disabled._spawn_daemon(tmp_path)  # noqa: SLF001
        called_cmd = mock_run.call_args[0][0]
        assert "--no-auto-rollback" in called_cmd


