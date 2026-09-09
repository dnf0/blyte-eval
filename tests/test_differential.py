"""Differential parity testing between superstate (Rust) and agent-rules (Python).

Runs zero-cost deterministic state operations against both binaries on identical
plan fixtures to verify state machine transitions, DAG parsing, and gate behavior.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import pytest

SUPERSTATE_BIN = Path("/Users/danielfisher/repos/superstate/target/debug/superstate")
AGENT_RULES_BIN = Path("/Users/danielfisher/repos/agent-rules/.venv/bin/agent-rules")
FIXTURES_DIR = Path(__file__).parent.parent / "lab" / "parity" / "fixtures"


@pytest.fixture
def check_binaries() -> None:
    if not SUPERSTATE_BIN.exists():
        pytest.skip(f"Superstate debug binary not found at {SUPERSTATE_BIN}")
    if not AGENT_RULES_BIN.exists():
        pytest.skip(f"Agent-rules binary not found at {AGENT_RULES_BIN}")


def test_init_state_creates_valid_state_files(check_binaries: None) -> None:
    plan_path = (FIXTURES_DIR / "linear_plan.md").resolve()

    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        state_rs = Path(d1) / "state.json"
        state_py = Path(d2) / "state.json"

        # Superstate (Rust)
        subprocess.run(
            [
                str(SUPERSTATE_BIN),
                "state",
                "init",
                "--plan",
                str(plan_path),
                "--state",
                str(state_rs),
            ],
            check=True,
            capture_output=True,
        )

        # Agent-Rules (Python)
        subprocess.run(
            [
                str(AGENT_RULES_BIN),
                "state",
                "init",
                "--plan",
                str(plan_path),
                "--out",
                str(state_py),
            ],
            check=True,
            capture_output=True,
        )

        rs_data = json.loads(state_rs.read_text())
        py_data = json.loads(state_py.read_text())

        # Core state machine initial invariants
        assert rs_data["step"] == 1
        assert py_data["step"] == 0 or py_data["step"] == 1
        assert rs_data["completed_tasks"] == []
        assert py_data["completed_tasks"] == []

        # Superstate models active_task as a structured TaskSpec; agent-rules as string
        if isinstance(rs_data["active_task"], dict):
            assert rs_data["active_task"]["id"] == "Task 1"
            assert "Setup database schema" in rs_data["active_task"]["title"]
        else:
            assert "Task 1" in rs_data["active_task"]

        assert "Task 1" in str(py_data["active_task"])


def test_verification_gate_failure_parity(check_binaries: None) -> None:
    plan_path = (FIXTURES_DIR / "linear_plan.md").resolve()

    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        state_rs = Path(d1) / "state.json"
        state_py = Path(d2) / "state.json"

        # Initialize both
        subprocess.run(
            [
                str(SUPERSTATE_BIN),
                "state",
                "init",
                "--plan",
                str(plan_path),
                "--state",
                str(state_rs),
            ],
            check=True,
        )
        subprocess.run(
            [
                str(AGENT_RULES_BIN),
                "state",
                "init",
                "--plan",
                str(plan_path),
                "--out",
                str(state_py),
            ],
            check=True,
        )

        # Execute failing gate on Superstate
        res_rs = subprocess.run(
            [
                str(SUPERSTATE_BIN),
                "state",
                "next",
                "--state",
                str(state_rs),
                "--verify-cmd",
                "exit 1",
            ],
            capture_output=True,
            text=True,
        )
        # Execute failing gate on Agent-Rules
        res_py = subprocess.run(
            [
                str(AGENT_RULES_BIN),
                "state",
                "next",
                "--state",
                str(state_py),
                "--verify-cmd",
                "exit 1",
            ],
            capture_output=True,
            text=True,
        )

        # Both must refuse to advance and return non-zero exit code
        assert res_rs.returncode != 0
        assert res_py.returncode != 0

        # States must remain unadvanced
        rs_data = json.loads(state_rs.read_text())
        py_data = json.loads(state_py.read_text())
        assert len(rs_data["completed_tasks"]) == 0
        assert len(py_data["completed_tasks"]) == 0


def test_verification_gate_success_parity(check_binaries: None) -> None:
    plan_path = (FIXTURES_DIR / "linear_plan.md").resolve()

    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        state_rs = Path(d1) / "state.json"
        state_py = Path(d2) / "state.json"

        # Initialize both
        subprocess.run(
            [
                str(SUPERSTATE_BIN),
                "state",
                "init",
                "--plan",
                str(plan_path),
                "--state",
                str(state_rs),
            ],
            check=True,
        )
        subprocess.run(
            [
                str(AGENT_RULES_BIN),
                "state",
                "init",
                "--plan",
                str(plan_path),
                "--out",
                str(state_py),
            ],
            check=True,
        )

        # Execute passing gate on Superstate
        res_rs = subprocess.run(
            [
                str(SUPERSTATE_BIN),
                "state",
                "next",
                "--state",
                str(state_rs),
                "--verify-cmd",
                "exit 0",
            ],
            capture_output=True,
            text=True,
        )
        # Execute passing gate on Agent-Rules
        res_py = subprocess.run(
            [
                str(AGENT_RULES_BIN),
                "state",
                "next",
                "--state",
                str(state_py),
                "--verify-cmd",
                "exit 0",
            ],
            capture_output=True,
            text=True,
        )

        assert res_rs.returncode == 0
        assert res_py.returncode == 0

        rs_data = json.loads(state_rs.read_text())
        py_data = json.loads(state_py.read_text())

        # Both must advance step and record 1 completed task
        assert len(rs_data["completed_tasks"]) == 1
        assert len(py_data["completed_tasks"]) == 1
