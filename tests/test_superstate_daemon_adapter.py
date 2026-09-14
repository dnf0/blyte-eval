import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.superstate_daemon import SuperstateDaemonAdapter


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


def test_gate_rejects_a_proposal_that_already_passes(tmp_path: Path) -> None:
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


def test_gate_accepts_a_proposal_that_currently_fails(tmp_path: Path) -> None:
    adapter = SuperstateDaemonAdapter(driver_preset="agy")
    proposed = "test -f ./artifact-the-task-must-produce"
    driver = _StubDriver(proposed)
    gate, _ = adapter._derive_gate(
        tmp_path, _task_with_verifier("bash /tests/test.sh"), driver, None, 60.0
    )
    assert gate == proposed


def test_gate_refuses_to_read_the_sealed_grader(tmp_path: Path) -> None:
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
    assert adapter._collect_driver_telemetry(tmp_path) == (105, 23)


def test_collect_driver_telemetry_tolerates_corrupt_turns(tmp_path: Path) -> None:
    adapter = SuperstateDaemonAdapter(driver_preset="agy")
    turns = tmp_path / ".agent-state" / "driver-turns"
    turns.mkdir(parents=True)
    (turns / "turn-1-1.json").write_text("not json{{")
    (turns / "turn-2-2.json").write_text(json.dumps({"usage": {"input_tokens": 9}}))
    assert adapter._collect_driver_telemetry(tmp_path) == (9, 0)


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


def test_critique_widens_an_incomplete_gate(tmp_path: Path) -> None:
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


def test_critique_cannot_weaken_the_gate(tmp_path: Path) -> None:
    """A critique may only strengthen the contract. A no-op reply keeps the original."""
    adapter = SuperstateDaemonAdapter(driver_preset="agy")
    original = "test -f ./artifact"
    driver = _ScriptedDriver(original, "true")

    gate, _ = adapter._derive_gate(
        tmp_path, _task_with_verifier("bash /tests/test.sh"), driver, None, 60.0
    )
    assert gate == original


def test_critique_rejecting_an_already_passing_gate(tmp_path: Path) -> None:
    """A widened gate that already passes cannot discriminate, so the original stands."""
    adapter = SuperstateDaemonAdapter(driver_preset="agy")
    original = "test -f ./artifact"
    driver = _ScriptedDriver(original, "echo always-passes")

    gate, _ = adapter._derive_gate(
        tmp_path, _task_with_verifier("bash /tests/test.sh"), driver, None, 60.0
    )
    assert gate == original
