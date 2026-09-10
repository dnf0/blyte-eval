"""The superstate adapter driving a real state engine through a full loop.

Every other adapter test stubs the engine. This drives the actual binary through
init -> ready -> prompt -> note -> next across several milestones, which is the
only way to catch the class of bug that has dominated this harness: the pieces
each work and the seam between them does not.

Runs against both engines, so an eval configured for either is covered.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.base import AgentDriver, DriverTelemetry
from lab.engine.adapters.superstate import (
    ENGINE_PYTHON,
    ENGINE_RUST,
    SuperstateAdapter,
    find_superstate_binary,
)

PLAN = """### Task 1: Alpha
- **Depends on:** none
- Verification Command: true

### Task 2: Beta
- **Depends on:** Task 1
- Verification Command: true

### Task 3: Gamma
- **Depends on:** Task 2
- Verification Command: true
"""


class ScriptedDriver(AgentDriver):
    """Succeeds every turn, recording the prompts it was given."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def run(self, task, workspace_path, prompt_override=None, conversation_id=None,
            timeout_sec=3600.0, container=None) -> DriverTelemetry:
        self.prompts.append(prompt_override or "")
        return DriverTelemetry(
            success=True,
            raw_response=f"Implemented milestone {len(self.prompts)}.",
            duration_seconds=1.0,
            input_tokens=100,
            output_tokens=20,
            cost_usd=0.01,
        )


def _engines() -> list[str]:
    return [e for e in (ENGINE_PYTHON, ENGINE_RUST) if find_superstate_binary(e)]


requires_engine = pytest.mark.skipif(not _engines(), reason="no state engine binary available")


def _workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "plan.md").write_text(PLAN, encoding="utf-8")
    subprocess.run(["git", "init", "-q", "."], cwd=ws, check=True)
    subprocess.run(["git", "config", "user.email", "e@l"], cwd=ws, check=True)
    subprocess.run(["git", "config", "user.name", "E"], cwd=ws, check=True)
    subprocess.run(["git", "add", "-A"], cwd=ws, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=ws, check=True)
    return ws


@requires_engine
@pytest.mark.parametrize("engine", _engines())
def test_every_milestone_executes_and_advances(tmp_path: Path, engine: str) -> None:
    ws = _workspace(tmp_path)
    driver = ScriptedDriver()

    result = SuperstateAdapter(engine=engine).execute(
        ws, TaskSpec(id="t", name="t", instruction="go", docker_image="x"), driver,
        timeout_sec=600.0,
    )

    assert result.success is True, result.error_message
    assert result.turns == 3, f"expected one turn per milestone, got {result.turns}"
    assert result.provenance["decomposed"] is True
    assert result.provenance["milestones_planned"] == 3

    state = json.loads((ws / ".agent-state" / "state.json").read_text())
    completed = state["completed_tasks"]
    assert len(completed) == 3, f"engine did not advance through every task: {completed}"


@requires_engine
@pytest.mark.parametrize("engine", _engines())
def test_prompts_come_from_the_engine_and_carry_the_ledger(tmp_path: Path, engine: str) -> None:
    # The engine writes the turnkey prompt and replays recorded findings; if the
    # harness substituted its own template, the arm would measure the template.
    ws = _workspace(tmp_path)
    driver = ScriptedDriver()

    SuperstateAdapter(engine=engine).execute(
        ws, TaskSpec(id="t", name="t", instruction="go", docker_image="x"), driver,
        timeout_sec=600.0,
    )

    assert driver.prompts, "no prompts issued"
    assert any("Implementer Subagent" in p for p in driver.prompts), driver.prompts[0][:200]
    # By the last milestone, earlier findings must be visible.
    assert "Implemented milestone 1" in driver.prompts[-1], (
        "the epistemic ledger was not replayed into later prompts"
    )


@requires_engine
@pytest.mark.parametrize("engine", _engines())
def test_a_failing_gate_stops_the_run_and_is_reported(tmp_path: Path, engine: str) -> None:
    ws = _workspace(tmp_path)
    (ws / "plan.md").write_text(
        "### Task 1: Alpha\n- **Depends on:** none\n- Verification Command: false\n",
        encoding="utf-8",
    )
    driver = ScriptedDriver()

    result = SuperstateAdapter(engine=engine).execute(
        ws, TaskSpec(id="t", name="t", instruction="go", docker_image="x"), driver,
        timeout_sec=600.0,
    )

    assert result.success is False
    assert "Verification gate failed" in str(result.error_message)
    state = json.loads((ws / ".agent-state" / "state.json").read_text())
    assert state["completed_tasks"] == [], "a failed gate must not advance the state"


@requires_engine
def test_both_engines_produce_the_same_arm_outcome(tmp_path: Path) -> None:
    # The eval must be able to swap engines without changing what it measures.
    engines = _engines()
    if len(engines) < 2:
        pytest.skip("needs both engines installed")

    outcomes = {}
    for engine in engines:
        (tmp_path / engine).mkdir(exist_ok=True)
        ws = _workspace(tmp_path / engine)
        ws_result = SuperstateAdapter(engine=engine).execute(
            ws, TaskSpec(id="t", name="t", instruction="go", docker_image="x"),
            ScriptedDriver(), timeout_sec=600.0,
        )
        state = json.loads((ws / ".agent-state" / "state.json").read_text())
        outcomes[engine] = (ws_result.success, ws_result.turns, len(state["completed_tasks"]))

    assert len(set(outcomes.values())) == 1, f"engines disagree on arm outcome: {outcomes}"
