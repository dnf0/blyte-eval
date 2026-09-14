"""Tests for Evaluation Arm Adapters: Vanilla, Superpowers, and Superstate."""

from __future__ import annotations

from pathlib import Path

from typing import Any, Callable

import pytest

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.base import AgentDriver, DriverTelemetry, TaskRunResult
from lab.engine.adapters.superpowers import SuperpowersAdapter
from lab.engine.adapters.superstate import SuperstateAdapter, _extract_plan_milestones
from lab.engine.adapters.vanilla import VanillaAdapter


class MockDriver(AgentDriver):
    """Predictable mock driver simulating agent behavior."""

    def __init__(
        self,
        responses: list[DriverTelemetry] | None = None,
        side_effect: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.responses = list(responses) if responses is not None else []
        self.side_effect = side_effect
        self.calls: list[dict[str, Any]] = []

    def run(
        self,
        task: TaskSpec,
        workspace_path: Path,
        prompt_override: str | None = None,
        conversation_id: str | None = None,
        timeout_sec: float = 3600.0,
        container: object = None,
    ) -> DriverTelemetry:
        call = {
            "task_id": task.id,
            "workspace": workspace_path,
            "prompt": prompt_override,
            "conversation_id": conversation_id,
            "timeout_sec": timeout_sec,
            "container": container,
        }
        self.calls.append(call)
        if self.side_effect:
            self.side_effect(call)
        if self.responses:
            return self.responses.pop(0)
        return DriverTelemetry(
            success=True,
            raw_response="Task complete.",
            duration_seconds=5.0,
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.001,
            conversation_id="conv-1",
        )


def _make_dummy_task(tmp_path: Path) -> TaskSpec:
    return TaskSpec(
        id="sample/test-task",
        name="test-task",
        instruction="Fix the bug in main.py.",
        docker_image="dummy:latest",
        task_dir=tmp_path,
    )


def test_vanilla_adapter_cleans_workspace_and_executes(tmp_path: Path) -> None:
    # Setup dirty workspace with legacy rules and skills
    (tmp_path / "AGENTS.md").write_text("legacy rules", encoding="utf-8")
    skills_dir = tmp_path / ".agents" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "dummy.md").write_text("dummy", encoding="utf-8")

    driver = MockDriver(
        [
            DriverTelemetry(
                success=True,
                raw_response="Fixed the bug in main.py.",
                duration_seconds=12.0,
                input_tokens=500,
                output_tokens=100,
                cost_usd=0.005,
                conversation_id="conv-vanilla",
            )
        ]
    )
    adapter = VanillaAdapter()
    result = adapter.execute(tmp_path, _make_dummy_task(tmp_path), driver)

    assert isinstance(result, TaskRunResult)
    assert result.harness_name == "vanilla"
    assert result.success is True
    assert result.duration_seconds == 12.0
    assert not (tmp_path / "AGENTS.md").exists(), "Vanilla must remove AGENTS.md"
    assert not skills_dir.exists(), "Vanilla must remove .agents/skills"
    assert len(driver.calls) == 1
    assert driver.calls[0]["prompt"] == "Fix the bug in main.py."


def test_superpowers_adapter_installs_guidance_and_handles_approval(tmp_path: Path) -> None:
    # Driver asks for approval on Turn 1, then completes on Turn 2
    driver = MockDriver(
        [
            DriverTelemetry(
                success=True,
                raw_response="Should I proceed with Option 1?",
                duration_seconds=10.0,
                input_tokens=200,
                output_tokens=50,
                cost_usd=0.002,
                conversation_id="conv-sp",
            ),
            DriverTelemetry(
                success=True,
                raw_response="Implementation finished.",
                duration_seconds=15.0,
                input_tokens=300,
                output_tokens=80,
                cost_usd=0.003,
                conversation_id="conv-sp",
            ),
        ]
    )
    adapter = SuperpowersAdapter()
    result = adapter.execute(tmp_path, _make_dummy_task(tmp_path), driver)

    assert result.harness_name == "superpowers"
    assert result.success is True
    assert result.turns == 2
    assert result.duration_seconds == 25.0
    assert (tmp_path / "AGENTS.md").exists(), "Superpowers must install AGENTS.md"
    assert "Proceed with the recommended option" in str(driver.calls[1]["prompt"])


def test_superstate_adapter_enforces_zero_superpowers_and_bounded_milestones(
    tmp_path: Path,
) -> None:
    # Plan whose per-milestone verification gates pass, so the state machine advances.
    plan_file = tmp_path / "plan.md"
    plan_file.write_text(
        "### Task 1: Module A\n- Verification Command: true\n\n"
        "### Task 2: Module B\n- Verification Command: true\n",
        encoding="utf-8",
    )

    driver = MockDriver(
        [
            DriverTelemetry(
                success=True,
                raw_response="Milestone 1 completed.",
                duration_seconds=8.0,
                input_tokens=150,
                output_tokens=40,
                cost_usd=0.001,
            ),
            DriverTelemetry(
                success=True,
                raw_response="Milestone 2 completed.",
                duration_seconds=9.0,
                input_tokens=180,
                output_tokens=45,
                cost_usd=0.001,
            ),
        ]
    )

    adapter = SuperstateAdapter()
    result = adapter.execute(tmp_path, _make_dummy_task(tmp_path), driver)

    assert result.harness_name == "superstate"
    assert result.success is True
    assert result.turns == 2
    # Verify Superstate never installs or uses .agents/skills
    assert not (tmp_path / ".agents" / "skills").exists(), (
        "Superstate must NOT install .agents/skills"
    )
    # The turnkey prompt must come from the state engine, not from a local
    # template. Generating it is a core function of the control plane, so a
    # hand-rolled substitute would mean the arm measures the substitute.
    prompt_0 = str(driver.calls[0]["prompt"])
    assert "Implementer Subagent" in prompt_0, "prompt did not come from `state prompt`"
    assert "Task 1: Module A" in prompt_0
    assert (tmp_path / ".agent-state" / "state.json").exists(), (
        "Superstate must initialize .agent-state/state.json"
    )


def test_superstate_milestone_verification_gate_blocks_advancement(tmp_path: Path) -> None:
    # A milestone whose targeted verification command fails must not advance.
    plan_file = tmp_path / "plan.md"
    plan_file.write_text(
        "### Task 1: Module A\n- Verification Command: false\n\n"
        "### Task 2: Module B\n- Verification Command: true\n",
        encoding="utf-8",
    )

    driver = MockDriver(
        [
            DriverTelemetry(
                success=True,
                raw_response="Milestone 1 completed.",
                duration_seconds=8.0,
            ),
        ]
    )

    adapter = SuperstateAdapter()
    result = adapter.execute(tmp_path, _make_dummy_task(tmp_path), driver)

    assert result.success is False
    assert "Verification gate failed" in str(result.error_message)
    # Execution stopped at the failed gate after exhausting retries rather than running Task 2.
    assert result.turns == adapter.max_turns_per_milestone


def test_superstate_extracts_per_milestone_verification_commands() -> None:
    milestones = _extract_plan_milestones(
        "### Task 1: Alpha\n- Verification Command: `pytest tests/test_alpha.py`\n\n"
        "### Task 2: Beta\n- Files: b.py\n"
    )
    assert [m.title for m in milestones] == ["Task 1: Alpha", "Task 2: Beta"]
    assert milestones[0].verify_cmd == "pytest tests/test_alpha.py"
    assert milestones[1].verify_cmd is None


def test_superstate_records_python_fallback_when_binary_missing(tmp_path: Path) -> None:
    # No binary available: the arm must still run, but must declare that the
    # system under test was NOT the superstate binary.
    plan_file = tmp_path / "plan.md"
    plan_file.write_text("### Task 1: Module A\n- Files: a.py\n", encoding="utf-8")

    driver = MockDriver([DriverTelemetry(success=True, raw_response="Done.", duration_seconds=1.0)])
    adapter = SuperstateAdapter(superstate_bin=Path("/nonexistent/superstate"))
    adapter.superstate_bin = None  # simulate discovery failure
    result = adapter.execute(tmp_path, _make_dummy_task(tmp_path), driver)

    assert result.success is True
    assert result.provenance["state_engine"] == "python_fallback"
    assert result.provenance["superstate_bin"] is None


def test_superstate_strips_pre_existing_guidance_files(tmp_path: Path) -> None:
    # Arm C must start from the same blank slate as Arm A, or it inherits an advantage.
    (tmp_path / "AGENTS.md").write_text("inherited rules", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("inherited rules", encoding="utf-8")
    plan_file = tmp_path / "plan.md"
    plan_file.write_text("### Task 1: Module A\n- Verification Command: true\n", encoding="utf-8")

    driver = MockDriver([DriverTelemetry(success=True, raw_response="Done.", duration_seconds=1.0)])
    SuperstateAdapter().execute(tmp_path, _make_dummy_task(tmp_path), driver)

    assert not (tmp_path / "AGENTS.md").exists()
    assert not (tmp_path / "CLAUDE.md").exists()


def test_budget_hook_extends_budget_mid_run(tmp_path: Path) -> None:
    # A run that earns progress must actually get the extra runway, not merely
    # have it recorded after the fact.
    from lab.engine.budget_policy import BudgetPolicy

    policy = BudgetPolicy(base_timeout_sec=10.0, lease_extension_sec=100.0)

    def budget_hook() -> float:
        policy.record_milestone_progress("commit")
        return policy.current_granted_budget_sec

    # Each turn burns 8s; without extensions the second turn would exceed the 10s budget.
    driver = MockDriver(
        [
            DriverTelemetry(success=True, raw_response="Should I proceed?", duration_seconds=8.0),
            DriverTelemetry(success=True, raw_response="Should I proceed?", duration_seconds=8.0),
            DriverTelemetry(success=True, raw_response="All done.", duration_seconds=8.0),
        ]
    )
    result = VanillaAdapter().execute(
        tmp_path, _make_dummy_task(tmp_path), driver, timeout_sec=10.0, budget_hook=budget_hook
    )

    assert result.success is True
    assert result.turns == 3
    assert policy.extensions_granted_count == 3


def test_adapter_passes_container_handle_to_driver(tmp_path: Path) -> None:
    sentinel = object()
    driver = MockDriver([DriverTelemetry(success=True, raw_response="Done.", duration_seconds=1.0)])
    VanillaAdapter().execute(
        tmp_path, _make_dummy_task(tmp_path), driver, container=sentinel
    )
    assert driver.calls[0]["container"] is sentinel


def test_turn_loop_breaker_reports_failure(tmp_path: Path) -> None:
    # The turn cap is a loop-breaker, not a budget. Set it explicitly rather than
    # depending on the production value, which must stay high enough not to bind.
    driver = MockDriver(
        [
            DriverTelemetry(
                success=True,
                raw_response="Should I proceed with Option 1?",
                duration_seconds=1.0,
            )
            for _ in range(12)
        ]
    )
    adapter = VanillaAdapter()
    adapter.max_turns = 4
    result = adapter.execute(tmp_path, _make_dummy_task(tmp_path), driver)

    assert result.success is False
    assert result.turns == 4
    assert "Exhausted maximum turns (4)" in str(result.error_message)


def test_production_turn_caps_do_not_bind_on_ordinary_runs() -> None:
    # Guard against a future edit quietly turning the loop-breakers back into
    # budgets that decide evaluation outcomes.
    assert VanillaAdapter().max_turns >= 50
    assert SuperpowersAdapter().max_turns >= 50
    assert SuperstateAdapter().max_milestones >= 50


def test_superstate_never_silently_truncates_a_long_plan(tmp_path: Path) -> None:
    # Dropping milestones and still reporting success would score an agent as
    # having solved work it never attempted.
    adapter = SuperstateAdapter()
    adapter.max_milestones = 3
    plan = "\n\n".join(
        f"### Task {i}: M{i}\n- Verification Command: true" for i in range(1, 6)
    )
    (tmp_path / "plan.md").write_text(plan, encoding="utf-8")

    driver = MockDriver([])
    result = adapter.execute(tmp_path, _make_dummy_task(tmp_path), driver)

    assert result.success is False
    assert "exceeding the max_milestones" in str(result.error_message)
    assert result.turns == 0, "must refuse before spending any budget"


def test_superstate_executes_every_milestone_in_a_long_plan(tmp_path: Path) -> None:
    # A flawless agent with a long plan must complete every milestone.
    plan = "\n\n".join(
        f"### Task {i}: M{i}\n- Verification Command: true" for i in range(1, 16)
    )
    (tmp_path / "plan.md").write_text(plan, encoding="utf-8")

    driver = MockDriver([])
    result = SuperstateAdapter().execute(tmp_path, _make_dummy_task(tmp_path), driver)

    assert result.success is True
    assert result.turns == 15, "every milestone must get its turn"


def test_superstate_planning_failure_aborts_immediately(tmp_path: Path) -> None:
    driver = MockDriver(
        [
            DriverTelemetry(
                success=False,
                raw_response="Model failed to generate plan.",
                duration_seconds=2.0,
                error_message="Model context overflow during planning",
            )
        ]
    )
    adapter = SuperstateAdapter()
    result = adapter.execute(tmp_path, _make_dummy_task(tmp_path), driver)

    assert result.success is False
    assert result.turns == 1
    assert "Model context overflow during planning" in str(result.error_message)


def test_recorder_captures_prompts_responses_and_gate_verdicts(tmp_path: Path) -> None:
    """The trace must explain a failure, not merely report one."""
    import json

    from lab.engine.trace import RunRecorder

    logs = tmp_path / "logs"
    recorder = RunRecorder(logs_dir=logs, task_id="t", arm="superstate")

    (tmp_path / "plan.md").write_text(
        "### Task 1: Alpha\n- Verification Command: false\n", encoding="utf-8"
    )
    driver = MockDriver(
        [DriverTelemetry(success=True, raw_response="Did the thing.", duration_seconds=1.0)]
    )
    result = SuperstateAdapter().execute(
        tmp_path, _make_dummy_task(tmp_path), driver, recorder=recorder
    )

    assert result.success is False

    turns = [json.loads(ln) for ln in (logs / "transcript.jsonl").read_text().splitlines()]
    assert turns[0]["phase"] == "milestone"
    assert "Implementer Subagent" in turns[0]["prompt"]
    assert turns[0]["response"] == "Did the thing."

    milestones = [json.loads(ln) for ln in (logs / "milestones.jsonl").read_text().splitlines()]
    assert milestones[0]["verify_cmd"] == "false"
    assert milestones[0]["gate_ran"] is True
    assert milestones[0]["gate_passed"] is False
    assert milestones[0]["advanced"] is False

    run_record_path = recorder.write_run_record(result)
    assert run_record_path is not None
    record = json.loads(run_record_path.read_text())
    assert record["gates_failed"] == ["Task 1: Alpha"]


def test_gate_command_strips_a_host_bridge_wrapper_when_run_in_container() -> None:
    """Regression from the first live run.

    The agy driver hands the agent `./run-in-container` -- a host script that shells
    to `docker exec`. The agent wrote its verification command in that form, but the
    gate runs INSIDE the container, where there is no docker binary. The gate failed
    with exit 127, milestone 1 never advanced, and the arm scored 0/9 on a bug rather
    than on its merits.
    """
    normalize = SuperstateAdapter.normalize_gate_command
    wrapped = "./run-in-container goyacc -o parser/parser.go x.y && ./run-in-container go test ./parser/..."

    inside = normalize(wrapped, in_container=True)
    assert "run-in-container" not in inside
    assert inside == "goyacc -o parser/parser.go x.y && go test ./parser/..."

    # On the host the bridge is the correct way to reach the sandbox: leave it alone.
    assert normalize(wrapped, in_container=False) == wrapped

    # A plain command is untouched either way.
    assert normalize("go test ./vm", in_container=True) == "go test ./vm"


def test_planning_prompt_asks_for_unwrapped_verification_commands(tmp_path: Path) -> None:
    driver = MockDriver([DriverTelemetry(success=True, raw_response="### Task 1: X", duration_seconds=1.0)])
    SuperstateAdapter().execute(tmp_path, _make_dummy_task(tmp_path), driver)

    planning_prompt = str(driver.calls[0]["prompt"])
    assert "PLAIN command" in planning_prompt
    assert "Do not prefix it with" in planning_prompt


def test_planning_budget_scales_with_the_run_budget(tmp_path: Path) -> None:
    """Planning time is a share of the budget, not a hardcoded constant.

    The original code capped planning at a literal 600s regardless of the budget
    granted, and a planning turn that exceeded it killed the entire run.
    """
    driver = MockDriver([DriverTelemetry(success=True, raw_response="### Task 1: X", duration_seconds=1.0)])
    adapter = SuperstateAdapter()
    adapter.execute(tmp_path, _make_dummy_task(tmp_path), driver, timeout_sec=3600.0)

    # 50% of 3600s, not 600s.
    assert driver.calls[0]["timeout_sec"] == pytest.approx(1800.0)


def test_planning_can_be_given_the_whole_budget(tmp_path: Path) -> None:
    driver = MockDriver([DriverTelemetry(success=True, raw_response="### Task 1: X", duration_seconds=1.0)])
    adapter = SuperstateAdapter()
    adapter.planning_budget_fraction = None
    adapter.execute(tmp_path, _make_dummy_task(tmp_path), driver, timeout_sec=1200.0)

    assert driver.calls[0]["timeout_sec"] == pytest.approx(1200.0)


def test_planning_timeout_is_reported_as_a_budget_share_not_an_agent_failure(
    tmp_path: Path,
) -> None:
    driver = MockDriver(
        [
            DriverTelemetry(
                success=False,
                raw_response="",
                duration_seconds=500.0,
                error_message="Agent turn exceeded 450s and was terminated",
            )
        ]
    )
    result = SuperstateAdapter().execute(
        tmp_path, _make_dummy_task(tmp_path), driver, timeout_sec=900.0
    )

    assert result.success is False
    assert "share of the 900s budget" in str(result.error_message)


def test_undecomposed_run_fails_instead_of_impersonating_the_baseline(tmp_path: Path) -> None:
    """A run that parsed no milestones is not a control-plane run.

    Live regression: the agent wrote plan.md outside the workspace, the harness fell
    back to the response prose, found no '### Task N:' heading, synthesized one
    ungated milestone, and would have recorded baseline behaviour under this arm's
    label -- a wrong result with no error anywhere.
    """
    driver = MockDriver(
        [DriverTelemetry(success=True, raw_response="I wrote the plan elsewhere.", duration_seconds=1.0)]
    )
    result = SuperstateAdapter().execute(tmp_path, _make_dummy_task(tmp_path), driver)

    assert result.success is False
    assert "no parseable milestones" in str(result.error_message)
    assert result.provenance["decomposed"] is False
    assert result.provenance["milestones_planned"] == 1


def test_provenance_records_a_real_decomposition(tmp_path: Path) -> None:
    (tmp_path / "plan.md").write_text(
        "### Task 1: A\n- Verification Command: true\n\n### Task 2: B\n- Verification Command: true\n",
        encoding="utf-8",
    )
    driver = MockDriver([])
    result = SuperstateAdapter().execute(tmp_path, _make_dummy_task(tmp_path), driver)

    assert result.provenance["decomposed"] is True
    assert result.provenance["milestones_planned"] == 2
    assert result.provenance["plan_source"] is None  # plan pre-existed; no planning turn


def test_agents_plan_is_never_overwritten(tmp_path: Path) -> None:
    # The agent's plan is evidence; the engine's normalised copy goes elsewhere.
    original = "Some prose plan with no headings at all."
    driver = MockDriver([DriverTelemetry(success=True, raw_response=original, duration_seconds=1.0)])
    adapter = SuperstateAdapter()
    adapter.require_decomposition = False
    adapter.execute(tmp_path, _make_dummy_task(tmp_path), driver)

    assert (tmp_path / "plan.md").read_text() == original
    assert (tmp_path / "plan.normalized.md").is_file()


def test_superstate_active_worktree_helper(tmp_path: Path) -> None:
    adapter = SuperstateAdapter()
    assert adapter.active_worktree(tmp_path) is None

    state_dir = tmp_path / ".agent-state"
    state_dir.mkdir(parents=True)
    state_file = state_dir / "state.json"

    # Non-existent worktree path
    state_file.write_text('{"active_worktree": ".wt/task-1"}', encoding="utf-8")
    assert adapter.active_worktree(tmp_path) is None

    # Existent relative worktree path
    wt_dir = tmp_path / ".wt" / "task-1"
    wt_dir.mkdir(parents=True)
    assert adapter.active_worktree(tmp_path) == wt_dir

    # Existent absolute worktree path
    state_file.write_text(f'{{"active_worktree": "{wt_dir.resolve()}"}}', encoding="utf-8")
    assert adapter.active_worktree(tmp_path) == wt_dir


def test_superstate_adapter_executes_in_worktree(tmp_path: Path) -> None:
    from lab.engine.adapters.superstate import ENGINE_RUST, find_superstate_binary

    bin_path = find_superstate_binary(ENGINE_RUST) or (Path.home() / "repos/superstate/target/release/superstate")
    if not bin_path.exists():
        pytest.skip("superstate release binary not found")

    import subprocess

    subprocess.run(["git", "init", "-b", "main"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.local"], cwd=str(tmp_path), check=True, capture_output=True)
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=str(tmp_path), check=True, capture_output=True)

    plan_file = tmp_path / "plan.md"
    plan_file.write_text(
        "### Task 1: Module A\n- Verification Command: true\n\n"
        "### Task 2: Module B\n- Verification Command: true\n",
        encoding="utf-8",
    )

    driver = MockDriver([])
    adapter = SuperstateAdapter(superstate_bin=bin_path, worktree=True)
    result = adapter.execute(tmp_path, _make_dummy_task(tmp_path), driver)

    assert result.success is True
    assert len(driver.calls) == 2
    for call in driver.calls:
        workspace = call["workspace"]
        assert isinstance(workspace, Path)
        assert workspace != tmp_path
        assert ".wt" in str(workspace)


def test_superstate_run_gate_command_container_worktree(tmp_path: Path) -> None:
    import json
    from unittest.mock import MagicMock

    wt_dir = tmp_path / ".wt" / "task-1"
    wt_dir.mkdir(parents=True)
    state_file = tmp_path / ".agent-state" / "state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(json.dumps({"active_worktree": str(wt_dir)}), encoding="utf-8")

    adapter = SuperstateAdapter()

    # 1. Container supporting workdir parameter
    container_normal = MagicMock()
    container_normal.exec_run.return_value = (0, b"all tests pass")
    passed, code, out = adapter._run_gate_command(tmp_path, "pytest", container=container_normal)
    assert passed is True
    assert code == 0
    assert out == "all tests pass"
    container_normal.exec_run.assert_called_once_with(["/bin/sh", "-c", "pytest"], workdir="/app")

    # 2. Container raising TypeError when kwargs passed (e.g. mock or legacy client)
    container_legacy = MagicMock()
    def mock_exec_run(cmd: object, **kwargs: object) -> tuple[int, bytes]:
        if kwargs:
            raise TypeError("unexpected keyword argument 'workdir'")
        return 0, b"fallback ok"
    container_legacy.exec_run.side_effect = mock_exec_run
    passed, code, out = adapter._run_gate_command(tmp_path, "pytest", container=container_legacy)
    assert passed is True
    assert code == 0
    assert out == "fallback ok"
    assert container_legacy.exec_run.call_count == 2
    fallback_call = container_legacy.exec_run.call_args_list[1][0][0]
    import shlex
    assert fallback_call == ["/bin/sh", "-c", f"cd {shlex.quote('/app')} && pytest"]


def test_superstate_adapter_executes_in_place(tmp_path: Path) -> None:
    from lab.engine.adapters.superstate import ENGINE_RUST, find_superstate_binary

    bin_path = find_superstate_binary(ENGINE_RUST) or (Path.home() / "repos/superstate/target/release/superstate")
    if not bin_path.exists():
        pytest.skip("superstate release binary not found")

    import subprocess

    subprocess.run(["git", "init", "-b", "main"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.local"], cwd=str(tmp_path), check=True, capture_output=True)
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=str(tmp_path), check=True, capture_output=True)

    plan_file = tmp_path / "plan.md"
    plan_file.write_text(
        "### Task 1: Module A\n- Verification Command: true\n\n"
        "### Task 2: Module B\n- Verification Command: true\n",
        encoding="utf-8",
    )

    driver = MockDriver([])
    adapter = SuperstateAdapter(superstate_bin=bin_path, no_worktree=True)
    result = adapter.execute(tmp_path, _make_dummy_task(tmp_path), driver)

    assert result.success is True
    assert len(driver.calls) == 2
    for call in driver.calls:
        workspace = call["workspace"]
        assert isinstance(workspace, Path)
        assert workspace == tmp_path
        assert ".wt" not in str(workspace)

    assert not (tmp_path / ".wt").exists()


def test_runner_resolves_inplace_arm() -> None:
    from lab.engine.runner import AblationRunner
    runner = AblationRunner(workspace_root=Path("/tmp"))
    adapter = runner._get_adapter("superstate_rust_inplace")
    assert isinstance(adapter, SuperstateAdapter)
    assert adapter.engine == "superstate-rust"
    assert adapter.no_worktree is True


def test_distill_finding_compacts_summary_and_limits_length() -> None:
    raw_markdown = (
        "### Task 1: Analyze WAL and Database Corruption - Summary\n\n"
        "#### Changes Implemented\n"
        "1. Discovered that the WAL file is obfuscated with a repeating XOR byte 0x42.\n"
        "2. Verified that 11 records exist once decrypted.\n\n"
        "#### Verification\n"
        "Ran 10 tests in 0.046s OK\n"
    )
    distilled = SuperstateAdapter._distill_finding(raw_markdown)
    assert "XOR byte 0x42" in distilled
    assert "11 records exist" in distilled
    assert len(distilled) <= 250
    assert "\n" not in distilled


def test_execution_contract_demands_minimal_direct_fix() -> None:
    from lab.engine.adapters.superstate import (
        TARGETED_EXECUTION_CONTRACT,
        TARGETED_EXECUTION_CONTRACT_INPLACE,
    )
    assert "HARD STOP UPON PASSING" in TARGETED_EXECUTION_CONTRACT
    assert "HARD STOP UPON PASSING" in TARGETED_EXECUTION_CONTRACT_INPLACE
    assert "MINIMAL DIRECT FIX" in TARGETED_EXECUTION_CONTRACT
    assert "MINIMAL DIRECT FIX" in TARGETED_EXECUTION_CONTRACT_INPLACE
    assert "speculative CLI flags" in TARGETED_EXECUTION_CONTRACT_INPLACE




def test_zero_turn_direct_state_init_produces_no_markdown_file(tmp_path: Path) -> None:
    import subprocess
    from unittest.mock import patch
    from lab.engine.adapters.superstate import ENGINE_RUST, find_superstate_binary

    bin_path = find_superstate_binary(ENGINE_RUST) or (Path.home() / "repos/superstate/target/release/superstate")
    if not bin_path.exists():
        pytest.skip("superstate release binary not found")

    subprocess.run(["git", "init", "-b", "main"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.local"], cwd=str(tmp_path), check=True, capture_output=True)
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=str(tmp_path), check=True, capture_output=True)

    task = _make_dummy_task(tmp_path)
    task.instruction = "Fix bug in main.py"
    task.verification_cmd = "true"

    driver = MockDriver([])
    adapter = SuperstateAdapter(superstate_bin=bin_path, engine=ENGINE_RUST, zero_turn_planning=True, no_worktree=True)

    with patch("subprocess.run", wraps=subprocess.run) as mock_subproc:
        result = adapter.execute(tmp_path, task, driver)

    assert result.success is True

    # Asserts that superstate state init is called with --goal and --verify-cmd
    init_calls = [
        call for call in mock_subproc.call_args_list
        if len(call[0]) > 0 and isinstance(call[0][0], list) and "state" in call[0][0] and "init" in call[0][0]
    ]
    assert len(init_calls) > 0, "superstate state init was not called"
    init_cmd = init_calls[0][0][0]
    assert "--goal" in init_cmd, "--goal flag missing from state init call"
    assert "--verify-cmd" in init_cmd, "--verify-cmd flag missing from state init call"

    # Asserts that NO plan.md or plan.normalized.md file exists in the workspace
    assert not (tmp_path / "plan.md").exists(), "plan.md must not exist"
    assert not (tmp_path / "plan.normalized.md").exists(), "plan.normalized.md must not exist"

    # Asserts provenance contains "plan_source": "direct_state_handoff"
    assert result.provenance["plan_source"] == "direct_state_handoff"


@pytest.mark.parametrize("failure_mode", ["none_bin", "exception", "nonzero_exit"])
def test_zero_turn_direct_state_init_fallback_when_binary_none_or_fails(
    tmp_path: Path, failure_mode: str
) -> None:
    import json
    import subprocess
    from unittest.mock import patch
    from lab.engine.adapters.superstate import ENGINE_PYTHON_FALLBACK

    task = _make_dummy_task(tmp_path)
    task.instruction = "Fix bug in main.py"
    task.verification_cmd = "true"

    driver = MockDriver([])

    if failure_mode == "none_bin":
        adapter = SuperstateAdapter(
            zero_turn_planning=True,
            no_worktree=True,
        )
        adapter.superstate_bin = None  # simulate binary not found
        result = adapter.execute(tmp_path, task, driver)

    elif failure_mode == "exception":
        adapter = SuperstateAdapter(
            superstate_bin=Path("/mock/superstate"),
            zero_turn_planning=True,
            no_worktree=True,
        )
        with patch("subprocess.run", side_effect=subprocess.SubprocessError("exec failure")):
            result = adapter.execute(tmp_path, task, driver)
    elif failure_mode == "nonzero_exit":
        adapter = SuperstateAdapter(
            superstate_bin=Path("/mock/superstate"),
            zero_turn_planning=True,
            no_worktree=True,
        )
        failed_res = subprocess.CompletedProcess(
            args=["superstate", "state", "init"],
            returncode=1,
            stdout="",
            stderr="binary init failed",
        )
        with patch("subprocess.run", return_value=failed_res):
            result = adapter.execute(tmp_path, task, driver)
    else:
        raise ValueError(f"Unknown failure mode {failure_mode}")

    assert result.success is True
    assert result.provenance["plan_source"] == "direct_state_handoff"
    assert result.provenance["state_engine"] == ENGINE_PYTHON_FALLBACK

    # Asserts that NO plan.md or plan.normalized.md file exists in the workspace
    assert not (tmp_path / "plan.md").exists(), "plan.md must not exist"
    assert not (tmp_path / "plan.normalized.md").exists(), "plan.normalized.md must not exist"

    # Asserts valid state JSON exists directly in Python fallback without markdown plan
    state_file = tmp_path / ".agent-state" / "state.json"
    assert state_file.is_file(), "state.json was not created"
    state_data = json.loads(state_file.read_text(encoding="utf-8"))
    assert state_data["status"] == "in_progress"
    assert state_data["step"] == 1
    assert state_data["active_task"]["id"] == "task-1"
    assert state_data["active_task"]["title"] == "Fix bug in main.py"
    assert state_data["active_task"]["verification_cmd"] == "true"
    assert state_data["no_worktree"] is True


def test_superstate_zero_turn_init_without_verification_cmd(tmp_path: Path) -> None:
    import json

    task = _make_dummy_task(tmp_path)
    task.instruction = "Fix bug without pre-declared verification command"
    task.verification_cmd = None  # Sealed tests

    driver = MockDriver([])
    adapter = SuperstateAdapter(
        zero_turn_planning=True,
        no_worktree=True,
    )

    result = adapter.execute(tmp_path, task, driver)

    assert result.success is True
    assert result.provenance["plan_source"] == "direct_state_handoff"

    # Verify no plan.md was generated
    assert not (tmp_path / "plan.md").exists()

    # Verify driver was only called once for execution (no Phase 1 planning turn)
    assert len(driver.calls) == 1
    call_prompt = str(driver.calls[0]["prompt"])
    assert "PRE-ASSESSMENT & ADAPTIVE DECOMPOSITION PROTOCOL" not in call_prompt

    # Verify state.json was created with fallback verify_cmd="true" and goal set
    state_file = tmp_path / ".agent-state" / "state.json"
    assert state_file.is_file()
    state_data = json.loads(state_file.read_text(encoding="utf-8"))
    assert state_data["status"] == "completed"
    assert state_data["goal"] == task.instruction
    assert state_data["completed_tasks"][0]["id"] == "task-1"
    assert state_data["completed_tasks"][0]["verification_cmd"] == "true"


def test_mcp_adapters_exported_and_provenance_properties() -> None:
    """Verify Superstate MCP adapters export from lab.engine.adapters and provenance structure."""
    from lab.engine.adapters import SuperstateAgentMcpAdapter, SuperstateMcpAdapter

    # Test SuperstateMcpAdapter provenance
    mcp_adapter = SuperstateMcpAdapter(no_worktree=True, zero_turn_planning=True)
    assert mcp_adapter.name == "superstate_mcp"
    prov_mcp = mcp_adapter.get_provenance()
    assert prov_mcp["engine"] == "superstate_rust_mcp"
    assert prov_mcp["transport"] == "mcp_stdio"
    assert prov_mcp["no_worktree"] is True
    assert prov_mcp["worktree"] is False
    assert prov_mcp["zero_turn_planning"] is True
    assert "mcp_tools_discovered" in prov_mcp

    # Test worktree and planned configurations
    mcp_wt = SuperstateMcpAdapter(no_worktree=False, worktree=True, zero_turn_planning=True)
    prov_wt = mcp_wt.get_provenance()
    assert prov_wt["no_worktree"] is False
    assert prov_wt["worktree"] is True

    mcp_planned = SuperstateMcpAdapter(no_worktree=True, zero_turn_planning=False)
    prov_planned = mcp_planned.get_provenance()
    assert prov_planned["zero_turn_planning"] is False

    # Test SuperstateAgentMcpAdapter provenance
    agent_mcp_adapter = SuperstateAgentMcpAdapter()
    assert agent_mcp_adapter.name == "superstate_agent_mcp"
    prov_agent = agent_mcp_adapter.get_provenance()
    assert prov_agent["engine"] == "superstate_agent_mcp"
    assert prov_agent["transport"] == "mcp_agent_tooling"
    assert prov_agent["autonomous"] is True
    assert "mcp_tools_discovered" in prov_agent


def test_runner_resolves_mcp_adapters() -> None:
    """Verify AblationRunner resolves superstate_mcp and superstate_agent_mcp adapters."""
    from lab.engine.adapters import SuperstateAgentMcpAdapter, SuperstateMcpAdapter
    from lab.engine.runner import AblationRunner

    runner = AblationRunner(workspace_root=Path("/tmp"))

    # Test resolution of superstate_mcp
    adapter_mcp = runner._get_adapter("superstate_mcp")
    assert isinstance(adapter_mcp, SuperstateMcpAdapter)
    assert adapter_mcp.no_worktree is True
    assert adapter_mcp.worktree is False
    assert adapter_mcp.zero_turn_planning is True

    # Test resolution of superstate_agent_mcp
    adapter_agent = runner._get_adapter("superstate_agent_mcp")
    assert isinstance(adapter_agent, SuperstateAgentMcpAdapter)

    # Test resolution of superstate_daemon
    from lab.engine.adapters import SuperstateDaemonAdapter, SuperstateAdapter
    adapter_daemon = runner._get_adapter("superstate_daemon")
    assert isinstance(adapter_daemon, SuperstateDaemonAdapter)

    # Test resolution of superstate_solo
    adapter_solo = runner._get_adapter("superstate_solo")
    assert isinstance(adapter_solo, SuperstateAdapter)


def test_is_transient_stream_interruption_detection() -> None:
    """Verify is_transient_stream_interruption correctly classifies transport vs logical errors."""
    from lab.engine.adapters.base import is_transient_stream_interruption

    assert is_transient_stream_interruption("The stream was interrupted. Please continue the task you were working on.")
    assert is_transient_stream_interruption("connection reset by peer")
    assert is_transient_stream_interruption("gRPC deadline exceeded during token streaming")
    assert is_transient_stream_interruption("HTTP 503 Service Unavailable from upstream API")
    assert is_transient_stream_interruption("Transport error: socket closed unexpectedly")
    assert not is_transient_stream_interruption("Fatal syntax error in main.py: line 42")
    assert not is_transient_stream_interruption("AssertionError at test_runner.py:503: test failed")
    assert not is_transient_stream_interruption("Process exited with code 503")
    assert not is_transient_stream_interruption("Timed out after 3600.0s")
    assert not is_transient_stream_interruption(None)
    assert not is_transient_stream_interruption("")


def test_turn_based_adapter_recovers_from_transient_stream_interruption(tmp_path: Path) -> None:
    """Verify TurnBasedAdapter resumes conversation when a transient API stream drop occurs."""
    task = _make_dummy_task(tmp_path)
    adapter = VanillaAdapter(max_turns=5)

    driver = MockDriver(
        [
            DriverTelemetry(
                success=False,
                raw_response="",
                error_message="The stream was interrupted. Please continue the task you were working on.",
                duration_seconds=30.0,
                input_tokens=500,
                output_tokens=100,
                cost_usd=0.01,
                conversation_id="conv-transient-1",
            ),
            DriverTelemetry(
                success=True,
                raw_response="Task complete.",
                duration_seconds=20.0,
                input_tokens=300,
                output_tokens=50,
                cost_usd=0.005,
                conversation_id="conv-transient-1",
            ),
        ]
    )

    result = adapter.execute(tmp_path, task, driver, timeout_sec=300.0)

    assert result.success is True
    assert result.turns == 2
    assert result.duration_seconds == 50.0
    assert result.input_tokens == 800
    assert result.output_tokens == 150
    assert result.cost_usd == pytest.approx(0.015)
    assert len(driver.calls) == 2
    # Second turn must resume the interrupted conversation
    assert driver.calls[0]["conversation_id"] is None
    assert driver.calls[1]["conversation_id"] == "conv-transient-1"
    assert "stream was interrupted" in str(driver.calls[1]["prompt"]).lower()


def test_turn_based_adapter_recovers_without_conversation_id(tmp_path: Path) -> None:
    """Verify TurnBasedAdapter retries with initial prompt when conversation_id is None."""
    task = _make_dummy_task(tmp_path)
    adapter = VanillaAdapter(max_turns=5)

    driver = MockDriver(
        [
            DriverTelemetry(
                success=False,
                raw_response="",
                error_message="Connection reset by peer",
                duration_seconds=10.0,
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                conversation_id=None,
            ),
            DriverTelemetry(
                success=True,
                raw_response="Fixed the bug in main.py.",
                duration_seconds=15.0,
                input_tokens=300,
                output_tokens=50,
                cost_usd=0.005,
                conversation_id="conv-recovered-2",
            ),
        ]
    )

    result = adapter.execute(tmp_path, task, driver, timeout_sec=300.0)

    assert result.success is True
    assert result.turns == 2
    assert len(driver.calls) == 2
    # When conversation_id was None, it must re-send the task instruction, NOT a resume string
    assert driver.calls[1]["conversation_id"] is None
    assert driver.calls[1]["prompt"] == "Fix the bug in main.py."


def test_turn_based_adapter_aborts_when_stream_retries_exhausted(tmp_path: Path) -> None:
    """Verify TurnBasedAdapter halts after exhausting max_stream_retries."""
    task = _make_dummy_task(tmp_path)
    adapter = VanillaAdapter(max_turns=10, max_stream_retries=2)

    driver = MockDriver(
        [
            DriverTelemetry(
                success=False,
                raw_response="",
                error_message="stream was interrupted",
                duration_seconds=10.0,
                conversation_id="conv-drop",
            ),
            DriverTelemetry(
                success=False,
                raw_response="",
                error_message="stream was interrupted",
                duration_seconds=10.0,
                conversation_id="conv-drop",
            ),
            DriverTelemetry(
                success=False,
                raw_response="",
                error_message="stream was interrupted",
                duration_seconds=10.0,
                conversation_id="conv-drop",
            ),
        ]
    )

    result = adapter.execute(tmp_path, task, driver, timeout_sec=300.0)

    assert result.success is False
    assert result.turns == 3  # 1 initial + 2 retries
    assert "stream was interrupted" in str(result.error_message)


def test_turn_based_adapter_does_not_retry_non_transient_failure(tmp_path: Path) -> None:
    """Verify TurnBasedAdapter does not retry non-transient model/logic failures."""
    task = _make_dummy_task(tmp_path)
    adapter = VanillaAdapter(max_turns=5)

    driver = MockDriver(
        [
            DriverTelemetry(
                success=False,
                raw_response="",
                error_message="Fatal error: compilation failed with exit code 2",
                duration_seconds=15.0,
                input_tokens=200,
                output_tokens=50,
                cost_usd=0.002,
                conversation_id="conv-fail-1",
            ),
        ]
    )

    result = adapter.execute(tmp_path, task, driver, timeout_sec=300.0)

    assert result.success is False
    assert result.turns == 1
    assert "compilation failed" in str(result.error_message)
    assert len(driver.calls) == 1


def test_superstate_adapter_gate_failure_stateless_retry(tmp_path: Path) -> None:
    """Test gate command failure, stateless turn (conv=None), diff stat, and recovery on retry."""
    import subprocess
    subprocess.run(["git", "init", "-b", "main"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.local"], cwd=str(tmp_path), check=True, capture_output=True)
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=str(tmp_path), check=True, capture_output=True)

    target_file = tmp_path / "repaired.txt"
    (tmp_path / "plan.md").write_text(
        f"### Task 1: Create repaired.txt\n- Verification Command: test -f {target_file.name}\n",
        encoding="utf-8",
    )
    task = _make_dummy_task(tmp_path)
    task.instruction = "Create repaired.txt"
    task.verification_cmd = f"test -f {target_file.name}"

    turn_count = 0

    def driver_action(call: dict[str, Any]) -> None:
        nonlocal turn_count
        turn_count += 1
        if turn_count == 1:
            # Turn 1: creates an unrelated file to test diff stat, but not target_file
            (tmp_path / "work_in_progress.py").write_text("# partial\n", encoding="utf-8")
        elif turn_count == 2:
            # Turn 2: checks retry prompt and stateless turn
            prompt = str(call.get("prompt", ""))
            assert "VERIFICATION GATE FAILED" in prompt
            assert f"test -f {target_file.name}" in prompt
            assert "Modified Files on Disk" in prompt
            assert "work_in_progress.py" in prompt
            assert call.get("conversation_id") is None
            target_file.write_text("repaired content\n", encoding="utf-8")

    driver = MockDriver(side_effect=driver_action)
    adapter = SuperstateAdapter(max_turns_per_milestone=3)

    result = adapter.execute(tmp_path, task, driver)

    assert result.success is True
    assert result.turns == 2
    assert target_file.is_file()


