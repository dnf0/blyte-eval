from pathlib import Path
from unittest.mock import MagicMock, patch

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.superstate_daemon import SuperstateDaemonAdapter


def test_daemon_adapter_initialization():
    adapter = SuperstateDaemonAdapter(driver_preset="agy")
    assert adapter.name == "superstate_daemon"
    assert adapter.driver_preset == "agy"


def test_daemon_adapter_run_mocked(tmp_path: Path):
    adapter = SuperstateDaemonAdapter(driver_preset="agy", poll_interval_sec=0.01)
    task = TaskSpec(
        id="daemon-test",
        name="Daemon Test",
        instruction="Complete task autonomously",
        docker_image="test:latest",
        verification_cmd="pytest /tests",
    )

    state_dir = tmp_path / ".agent-state"
    daemons_dir = state_dir / "daemons"
    daemons_dir.mkdir(parents=True, exist_ok=True)
    pid_file = daemons_dir / "default.pid"
    pid_file.write_text("999999\n", encoding="utf-8")

    state_file = state_dir / "state.json"
    state_file.write_text('{"status": "completed", "step": 1, "completed_tasks": [{"id": "task-1"}]}', encoding="utf-8")

    with patch("lab.engine.adapters.superstate_daemon.is_pid_alive", side_effect=[True, False]), \
         patch("time.sleep"), \
         patch.object(adapter, "_init_daemon_state", return_value=True), \
         patch.object(adapter, "_spawn_daemon", return_value=True), \
         patch.object(adapter, "_run_gate_command", return_value=(True, 0, "pass")):
        
        # Test execute method
        result = adapter.execute(
            workspace_path=tmp_path,
            task=task,
            driver=MagicMock(),
            timeout_sec=60.0,
        )

    assert result.success is True
    assert result.harness_name == "superstate_daemon"
    assert result.task_id == "daemon-test"

    with patch("lab.engine.adapters.superstate_daemon.is_pid_alive", side_effect=[True, False]), \
         patch("time.sleep"), \
         patch.object(adapter, "_init_daemon_state", return_value=True), \
         patch.object(adapter, "_spawn_daemon", return_value=True), \
         patch.object(adapter, "_run_gate_command", return_value=(True, 0, "pass")):
        
        # Test run_task alias
        result2 = adapter.run_task(
            workspace_path=tmp_path,
            task=task,
            driver=MagicMock(),
            timeout_sec=60.0,
        )
        
    assert result2.success is True


def test_init_daemon_state_filters_held_out_verifier(tmp_path: Path):
    adapter = SuperstateDaemonAdapter(driver_preset="agy")
    task_held_out = TaskSpec(
        id="daemon-held-out",
        name="Daemon Held Out",
        instruction="Do work",
        docker_image="test:latest",
        verification_cmd="bash /tests/test.sh",
    )

    with patch("subprocess.run") as mock_run:
        adapter._init_daemon_state(tmp_path, task_held_out)
        args, kwargs = mock_run.call_args
        cmd = args[0]
        assert "--verify-cmd" in cmd
        idx = cmd.index("--verify-cmd")
        assert cmd[idx + 1] == "true"


def test_init_daemon_state_preserves_local_verifier(tmp_path: Path):
    adapter = SuperstateDaemonAdapter(driver_preset="agy")
    task_local = TaskSpec(
        id="daemon-local",
        name="Daemon Local",
        instruction="Do work",
        docker_image="test:latest",
        verification_cmd="pytest tests/local",
    )

    with patch("subprocess.run") as mock_run:
        adapter._init_daemon_state(tmp_path, task_local)
        args, kwargs = mock_run.call_args
        cmd = args[0]
        assert "--verify-cmd" in cmd
        idx = cmd.index("--verify-cmd")
        assert cmd[idx + 1] == "pytest tests/local"

