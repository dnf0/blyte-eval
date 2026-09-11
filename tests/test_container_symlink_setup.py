from pathlib import Path
from unittest.mock import MagicMock
import pytest

from lab.engine.adapters.base import AgentDriver, DriverTelemetry
from lab.engine.runner import CONTAINER_MOUNT_ROOT, CONTAINER_WORKSPACE, AblationRunner
from lab.engine.drivers.agy_cli import AgyCliDriver


def test_runner_mounts_workspace_root_and_inits_symlink(tmp_path: Path) -> None:
    class StubDriver(AgentDriver):
        def run(
            self,
            task,
            workspace_path,
            prompt_override=None,
            conversation_id=None,
            timeout_sec=3600.0,
            container=None,
        ) -> DriverTelemetry:
            return DriverTelemetry(
                success=True,
                raw_response="Done.",
                duration_seconds=1.0,
                input_tokens=10,
                output_tokens=5,
                cost_usd=0.01,
            )

    mock_docker_mgr = MagicMock()
    mock_container = MagicMock()
    
    def fake_run_sandbox(**kwargs):
        from contextlib import contextmanager
        @contextmanager
        def _ctx():
            yield mock_container
        return _ctx()

    mock_docker_mgr.run_sandbox.side_effect = fake_run_sandbox

    runner = AblationRunner(
        docker_manager=mock_docker_mgr,
        workspace_root=tmp_path / "workspaces",
        default_driver=StubDriver(),
    )

    runner.run_task(
        task_id="test/symlink-task",
        arm="vanilla",
        image="test:latest",
        base_budget_sec=60.0,
    )

    # 1. Mount must be to CONTAINER_MOUNT_ROOT (/workspace_root)
    assert CONTAINER_MOUNT_ROOT == "/workspace_root"
    assert CONTAINER_WORKSPACE == "/app"
    call_kwargs = mock_docker_mgr.run_sandbox.call_args[1]
    volumes = call_kwargs["volumes"]
    host_path, bind_spec = next(iter(volumes.items()))
    assert bind_spec == {"bind": CONTAINER_MOUNT_ROOT, "mode": "rw"}

    # 2. Container must execute symlink initialization command
    expected_cmd = ["sh", "-c", f"rm -rf {CONTAINER_WORKSPACE} && ln -s {CONTAINER_MOUNT_ROOT} {CONTAINER_WORKSPACE}"]
    mock_container.exec_run.assert_any_call(expected_cmd)


def test_agy_cli_driver_run_in_container_sets_workdir(tmp_path: Path) -> None:
    import sys
    driver = AgyCliDriver(cli_path=sys.executable)
    mock_container = MagicMock()
    mock_container.id = "c12345"

    driver._setup_container_bridge(workspace_path=tmp_path, container=mock_container)

    script_path = tmp_path / "run-in-container"
    assert script_path.is_file()
    content = script_path.read_text(encoding="utf-8")
    assert "-w /app" in content
