"""Tests for Evaluation Arm Adapters: Vanilla, Superpowers, and Superstate."""

from __future__ import annotations

from pathlib import Path

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.base import AgentDriver, DriverTelemetry, TaskRunResult
from lab.engine.adapters.superpowers import SuperpowersAdapter
from lab.engine.adapters.superstate import SuperstateAdapter, _extract_plan_milestones
from lab.engine.adapters.vanilla import VanillaAdapter


class MockDriver(AgentDriver):
    """Predictable mock driver simulating agent behavior."""

    def __init__(self, responses: list[DriverTelemetry]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def run(
        self,
        task: TaskSpec,
        workspace_path: Path,
        prompt_override: str | None = None,
        conversation_id: str | None = None,
        timeout_sec: float = 3600.0,
        container: object = None,
    ) -> DriverTelemetry:
        self.calls.append(
            {
                "task_id": task.id,
                "workspace": workspace_path,
                "prompt": prompt_override,
                "conversation_id": conversation_id,
                "timeout_sec": timeout_sec,
                "container": container,
            }
        )
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
    # Verify prompt contains targeted negative constraints
    prompt_0 = str(driver.calls[0]["prompt"])
    assert "TARGETED EXECUTION CONTRACT" in prompt_0
    assert "ZERO GLOBAL EXPLORATION" in prompt_0
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
    # Execution stopped at the failed gate rather than running Task 2.
    assert result.turns == 1


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
    assert "TARGETED EXECUTION CONTRACT" in turns[0]["prompt"]
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
