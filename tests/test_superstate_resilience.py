"""Tests for Superstate milestone retry loops and greenfield resilience."""

from __future__ import annotations

from pathlib import Path
import subprocess


from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.base import AgentDriver, DriverTelemetry
from lab.engine.adapters.superstate import (
    ENGINE_PYTHON,
    SuperstateAdapter,
)

PLAN_WITH_FAILING_GATE = """### Task 1: FlakyStep
- **Depends on:** none
- Verification Command: test -f marker.txt

### Task 2: SecondStep
- **Depends on:** Task 1
- Verification Command: true
"""


class FlakyGateDriver(AgentDriver):
    """Fails on turn 1 by not creating marker.txt, then creates it on turn 2 after seeing diagnostic prompt."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.prompts: list[str] = []

    def run(
        self,
        task,
        workspace_path,
        prompt_override=None,
        conversation_id=None,
        timeout_sec=3600.0,
        container=None,
    ) -> DriverTelemetry:
        self.prompts.append(prompt_override or "")
        turn = len(self.prompts)
        if turn == 1:
            # Turn 1: Don't create marker.txt, gate will fail
            return DriverTelemetry(
                success=True,
                raw_response="I think I finished task 1 but did not create marker.",
                duration_seconds=1.0,
                input_tokens=50,
                output_tokens=20,
                cost_usd=0.001,
            )
        elif turn == 2:
            # Turn 2: Verify diagnostic prompt received, create marker
            (self.workspace / "marker.txt").write_text("fixed\n", encoding="utf-8")
            return DriverTelemetry(
                success=True,
                raw_response="Fixed the issue by creating marker.txt.",
                duration_seconds=1.0,
                input_tokens=50,
                output_tokens=20,
                cost_usd=0.001,
            )
        else:
            return DriverTelemetry(
                success=True,
                raw_response="Task 2 completed.",
                duration_seconds=1.0,
                input_tokens=50,
                output_tokens=20,
                cost_usd=0.001,
            )


def test_milestone_retry_loop_on_failed_gate(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "plan.md").write_text(PLAN_WITH_FAILING_GATE, encoding="utf-8")
    subprocess.run(["git", "init", "-q", "."], cwd=ws, check=True)
    subprocess.run(["git", "config", "user.email", "agent@local"], cwd=ws, check=True)
    subprocess.run(["git", "config", "user.name", "Agent"], cwd=ws, check=True)
    subprocess.run(["git", "add", "-A"], cwd=ws, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=ws, check=True)

    driver = FlakyGateDriver(ws)
    adapter = SuperstateAdapter(engine=ENGINE_PYTHON)
    adapter.max_turns_per_milestone = 3

    result = adapter.execute(
        ws,
        TaskSpec(id="flaky-task", name="flaky-task", instruction="Fix everything", docker_image="test"),
        driver,
        timeout_sec=600.0,
    )

    assert result.success is True, f"Expected retry loop to succeed, got: {result.error_message}"
    assert len(driver.prompts) == 3, f"Expected 3 turns (1 retry on task 1 + 1 on task 2), got {len(driver.prompts)}"
    # Turn 2 prompt must contain diagnostic feedback
    assert "VERIFICATION GATE FAILED" in driver.prompts[1]
    assert "test -f marker.txt" in driver.prompts[1]


def test_greenfield_workspace_advances_without_git(tmp_path: Path) -> None:
    """Verify that a greenfield workspace without .git does not crash when advancing state."""
    ws = tmp_path / "greenfield_workspace"
    ws.mkdir()
    (ws / "plan.md").write_text("### Task 1: Green\n- Verification Command: true\n", encoding="utf-8")
    # Note: no git init!

    adapter = SuperstateAdapter(engine=ENGINE_PYTHON)
    adapter._init_state(ws, ws / "plan.md")

    # Advancing state on non-git workspace should succeed without crashing on --verify-git-clean
    advanced = adapter._advance_state(ws, "Task 1: Green", verify_cmd="true")
    assert advanced is True
