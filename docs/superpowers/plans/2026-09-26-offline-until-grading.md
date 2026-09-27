# Offline Agent, Online Grader — Implementation Plan

> **For agentic workers:** Implement exactly one task. Do NOT `git push`, open PRs, start any benchmark or paid run, or call any model API; commit locally only. Do not stop, remove or prune any Docker container, image, volume or network you did not create in a test. This plan is shadow-run: agy and blyte each implement it independently.

**Goal:** A task that declares `network_mode = "no-network"` and is graded **inside the agent's
container** (Terminal-Bench style: `has_verifier_dockerfile` is False) runs its agent with no internet
access, and gets network access back only for grading. Tasks graded by a held-out verifier image
(DeepSWE style) are unchanged.

**Why (2026-09-26):** FrontierHarness v1.0 runs every task offline. Terminal-Bench tasks are graded
in the agent's own container by `tests/test.sh`, which installs `curl` and `uv` from the internet
before testing. Starting that container with `network_mode="none"` therefore also cut off the grader:
`constraints-scheduling` could not be graded at all ("Temporary failure resolving…", "curl: command
not found"). A container started with `network_mode="none"` cannot later be given a network, so the
agent must instead start on an **internal** Docker network (no route out) and be connected to the
default `bridge` network just before grading.

**Tech Stack:** Python 3, docker SDK, pytest, ruff, pyright, `uv`.

## Global Constraints

- Work only in your own worktree (already on its own branch). Run `uv sync` first.
- Do NOT edit `FINDINGS.md`, `EXPERIMENTS.md`, `CLAUDE.md`/`AGENTS.md` or anything under `results/`.
- Existing tests must pass unmodified.
- DeepSWE-style tasks (a held-out verifier image) must behave exactly as before: agent `network_mode="none"`, verifier unchanged.
- Commit with `--no-gpg-sign` and the exact message below.

---

### Task 1: Internal network for the agent, bridge for grading

**What to build** (names are part of the contract; the tests below check them):

`lab/sandbox/docker_manager.py`:
- `OFFLINE_NETWORK = "superstate-eval-offline"` (module constant).
- `DockerManager.ensure_offline_network() -> str`: returns `OFFLINE_NETWORK`, creating it first with
  `self.client.networks.create(OFFLINE_NETWORK, driver="bridge", internal=True)` if
  `self.client.networks.list(names=[OFFLINE_NETWORK])` finds none.
- `DockerManager.connect_for_grading(container) -> None`: connects the container to the default
  `bridge` network (`self.client.networks.get("bridge").connect(container)`).
- `run_sandbox` gains an optional `network: str | None = None` parameter, passed to
  `containers.run(network=...)` only when set.

`lab/engine/runner.py`, in `run_task`:
- When the task's resolved agent network mode is `"none"` **and** the task is graded in its own
  container (`active_task.has_verifier_dockerfile` is False), start the sandbox with
  `network=self.docker_manager.ensure_offline_network()` and `network_mode=None`, and pass
  `enable_network=lambda: self.docker_manager.connect_for_grading(container)` to `extract_and_grade`.
- Otherwise start the sandbox exactly as today and pass no `enable_network`.

`lab/engine/extractor.py`, `extract_and_grade`:
- New optional parameter `enable_network: Callable[[], None] | None = None`. In the in-container
  grading branch, call it (if given) before injecting the tests and before running the verification
  command. If it raises, log the error and continue (grading will then fail visibly, as today).

- [ ] **Step 1: Write the failing test.** Create `tests/test_offline_until_grading.py`:

```python
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
```

- [ ] **Step 2: Run to confirm it fails.** Run: `uv run pytest -q tests/test_offline_until_grading.py`. Expected: import error (`OFFLINE_NETWORK` missing), then failures.

- [ ] **Step 3: Implement** the additions above.

- [ ] **Step 4: Verify.** Run `uv run pytest -q tests/test_offline_until_grading.py tests/test_container_symlink_setup.py tests/test_runner.py tests/test_extractor.py` (all pass), then `make lint`.

- [ ] **Step 5: Commit.**

```bash
git add -A lab tests
git commit --no-gpg-sign -m "feat(eval): an offline agent keeps an online grader (internal network, bridge for grading)"
```
