"""An offline agent keeps an online grader: Terminal-Bench tests install curl and uv at grading
time, so a container started with network_mode="none" could not be graded (2026-09-26)."""

from pathlib import Path
from unittest.mock import MagicMock

from lab.benchmarks.task_loader import load_task_from_dir
from lab.engine.adapters.base import AgentDriver, DriverTelemetry
from lab.engine.runner import AblationRunner
from lab.sandbox.docker_manager import OFFLINE_NETWORK, DockerManager


class StubDriver(AgentDriver):
    def run(self, task, workspace_path, prompt_override=None, conversation_id=None,
            timeout_sec=3600.0, container=None) -> DriverTelemetry:
        return DriverTelemetry(success=True, raw_response="Done.", duration_seconds=1.0,
                               input_tokens=10, output_tokens=5, cost_usd=0.01)


def _task_dir(tmp_path: Path, in_container: bool) -> Path:
    t = tmp_path / "task"
    (t / "tests").mkdir(parents=True)
    (t / "instruction.md").write_text("Do it.")
    (t / "tests" / "test.sh").write_text("#!/bin/bash\necho ok\n")
    if not in_container:
        (t / "tests" / "Dockerfile").write_text("FROM scratch\n")
    (t / "task.toml").write_text(
        '[task]\nname = "suite/t"\n\n[environment]\ndocker_image = "img:1"\n'
        'network_mode = "no-network"\n\n[agent]\ntimeout_sec = 60.0\n'
    )
    return t


def _run(tmp_path: Path, in_container: bool) -> tuple[MagicMock, MagicMock, list[str]]:
    events: list[str] = []
    mgr = MagicMock()
    container = MagicMock()
    container.exec_run.side_effect = lambda *a, **k: (events.append(f"exec:{a[0]}") or (0, b""))

    def fake_run_sandbox(**kwargs):
        from contextlib import contextmanager

        @contextmanager
        def _ctx():
            yield container
        return _ctx()

    mgr.run_sandbox.side_effect = fake_run_sandbox
    mgr.ensure_offline_network.return_value = OFFLINE_NETWORK
    mgr.connect_for_grading.side_effect = lambda c: events.append("connect")
    governor = MagicMock()
    governor.calculate_max_concurrency.return_value = 1
    runner = AblationRunner(docker_manager=mgr, workspace_root=tmp_path / "ws",
                            default_driver=StubDriver(), governor=governor, verifier=MagicMock())
    runner.run_task(task_id="suite/t", arm="vanilla", image="img:1", base_budget_sec=60.0,
                    task_spec=load_task_from_dir(_task_dir(tmp_path, in_container)))
    return mgr, container, events


def test_an_in_container_task_runs_its_agent_on_the_internal_network(tmp_path: Path) -> None:
    mgr, _, _ = _run(tmp_path, in_container=True)
    kwargs = mgr.run_sandbox.call_args.kwargs
    assert kwargs.get("network") == OFFLINE_NETWORK
    assert kwargs.get("network_mode") is None


def test_grading_gets_the_network_back_before_the_tests_run(tmp_path: Path) -> None:
    _, _, events = _run(tmp_path, in_container=True)
    assert "connect" in events
    first_test_exec = next(i for i, e in enumerate(events) if e.startswith("exec:") and "test" in e)
    assert events.index("connect") < first_test_exec, events


def test_a_held_out_verifier_task_is_unchanged(tmp_path: Path) -> None:
    mgr, _, events = _run(tmp_path, in_container=False)
    kwargs = mgr.run_sandbox.call_args.kwargs
    assert kwargs.get("network_mode") == "none"
    assert not kwargs.get("network")
    assert "connect" not in events


def test_the_offline_network_is_internal_and_created_once() -> None:
    client = MagicMock()
    client.networks.list.return_value = []
    mgr = DockerManager(client=client)
    assert mgr.ensure_offline_network() == OFFLINE_NETWORK
    client.networks.create.assert_called_once_with(OFFLINE_NETWORK, driver="bridge", internal=True)
    client.networks.list.return_value = [MagicMock()]
    mgr.ensure_offline_network()
    assert client.networks.create.call_count == 1


def test_connect_for_grading_joins_the_default_bridge() -> None:
    client = MagicMock()
    container = MagicMock()
    DockerManager(client=client).connect_for_grading(container)
    client.networks.get.assert_called_with("bridge")
    client.networks.get.return_value.connect.assert_called_once_with(container)
