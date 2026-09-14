import subprocess
from pathlib import Path
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
