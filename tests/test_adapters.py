"""Tests for Evaluation Arm Adapters: Vanilla, Superpowers, and Superstate."""

from __future__ import annotations

from pathlib import Path

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.base import AgentDriver, DriverTelemetry, TaskRunResult
from lab.engine.adapters.superpowers import SuperpowersAdapter
from lab.engine.adapters.superstate import SuperstateAdapter
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
    ) -> DriverTelemetry:
        self.calls.append(
            {
                "task_id": task.id,
                "workspace": workspace_path,
                "prompt": prompt_override,
                "conversation_id": conversation_id,
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
    # Prepare dummy plan
    plan_file = tmp_path / "plan.md"
    plan_file.write_text(
        "### Task 1: Module A\n- Verification Command: pytest tests/test_a.py\n\n"
        "### Task 2: Module B\n- Verification Command: pytest tests/test_b.py\n",
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
