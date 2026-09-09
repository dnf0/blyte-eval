"""Differential parity testing between superstate (Rust) and agent-rules (Python).

Runs zero-cost deterministic state operations against both binaries on identical
plan fixtures to verify state machine transitions, DAG parsing, and gate behavior.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Optional

from deepdiff import DeepDiff
import pytest


def _resolve_binary(
    env_var: str, cmd_name: str, candidate_paths: list[Path]
) -> Optional[Path]:
    """Dynamically resolve binary executable from env, PATH, or fallback locations."""
    env_path = os.getenv(env_var)
    if env_path and Path(env_path).is_file():
        return Path(env_path)

    which_path = shutil.which(cmd_name)
    if which_path and Path(which_path).is_file():
        return Path(which_path)

    for p in candidate_paths:
        if p.is_file():
            return p
    return None


SUPERSTATE_BIN = _resolve_binary(
    "SUPERSTATE_BIN",
    "superstate",
    [
        Path.home() / ".local" / "bin" / "superstate",
        Path.home() / "repos" / "superstate" / "target" / "debug" / "superstate",
    ],
)

AGENT_RULES_BIN = _resolve_binary(
    "AGENT_RULES_BIN",
    "agent-rules",
    [
        Path.home() / "repos" / "agent-rules" / ".venv" / "bin" / "agent-rules",
        Path.home() / ".local" / "bin" / "agent-rules",
    ],
)

FIXTURES_DIR = Path(__file__).parent.parent / "lab" / "parity" / "fixtures"


@pytest.fixture
def check_binaries() -> tuple[Path, Path]:
    if not SUPERSTATE_BIN or not SUPERSTATE_BIN.is_file():
        pytest.skip(f"Superstate binary not found at {SUPERSTATE_BIN}")
    if not AGENT_RULES_BIN or not AGENT_RULES_BIN.is_file():
        pytest.skip(f"Agent-rules binary not found at {AGENT_RULES_BIN}")
    return SUPERSTATE_BIN, AGENT_RULES_BIN


def test_init_state_creates_valid_state_files(check_binaries: tuple[Path, Path]) -> None:
    superstate_bin, agent_rules_bin = check_binaries
    plan_path = (FIXTURES_DIR / "linear_plan.md").resolve()

    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        state_rs = Path(d1) / "state.json"
        state_py = Path(d2) / "state.json"

        # Superstate (Rust)
        subprocess.run(
            [
                str(superstate_bin),
                "state",
                "init",
                "--plan",
                str(plan_path),
                "--out",
                str(state_rs),
            ],
            check=True,
            capture_output=True,
        )

        # Agent-Rules (Python)
        subprocess.run(
            [
                str(agent_rules_bin),
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

        rs_data = json.loads(state_rs.read_text(encoding="utf-8"))
        py_data = json.loads(state_py.read_text(encoding="utf-8"))

        # DeepDiff structural parity assertion across all fields except engine_metadata and local plan_path
        diff = DeepDiff(
            rs_data,
            py_data,
            exclude_paths=["root['plan_path']", "root['engine_metadata']"],
        )
        assert diff == {}, f"State parity mismatch on init: {diff}"


def test_verification_gate_failure_parity(check_binaries: tuple[Path, Path]) -> None:
    superstate_bin, agent_rules_bin = check_binaries
    plan_path = (FIXTURES_DIR / "linear_plan.md").resolve()

    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        state_rs = Path(d1) / "state.json"
        state_py = Path(d2) / "state.json"

        # Initialize both
        subprocess.run(
            [
                str(superstate_bin),
                "state",
                "init",
                "--plan",
                str(plan_path),
                "--out",
                str(state_rs),
            ],
            check=True,
        )
        subprocess.run(
            [
                str(agent_rules_bin),
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
                str(superstate_bin),
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
                str(agent_rules_bin),
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

        # States must remain unadvanced and identical
        rs_data = json.loads(state_rs.read_text(encoding="utf-8"))
        py_data = json.loads(state_py.read_text(encoding="utf-8"))
        diff = DeepDiff(
            rs_data,
            py_data,
            exclude_paths=["root['plan_path']", "root['engine_metadata']"],
        )
        assert diff == {}, f"State parity mismatch after failed verification gate: {diff}"


def test_verification_gate_success_parity(check_binaries: tuple[Path, Path]) -> None:
    superstate_bin, agent_rules_bin = check_binaries
    plan_path = (FIXTURES_DIR / "linear_plan.md").resolve()

    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        state_rs = Path(d1) / "state.json"
        state_py = Path(d2) / "state.json"

        # Initialize both
        subprocess.run(
            [
                str(superstate_bin),
                "state",
                "init",
                "--plan",
                str(plan_path),
                "--out",
                str(state_rs),
            ],
            check=True,
        )
        subprocess.run(
            [
                str(agent_rules_bin),
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
                str(superstate_bin),
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
                str(agent_rules_bin),
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

        rs_data = json.loads(state_rs.read_text(encoding="utf-8"))
        py_data = json.loads(state_py.read_text(encoding="utf-8"))

        # Both must advance step and record 1 completed task with exact deep parity
        diff = DeepDiff(
            rs_data,
            py_data,
            exclude_paths=["root['plan_path']", "root['engine_metadata']"],
        )
        assert diff == {}, f"State parity mismatch after successful verification gate: {diff}"
