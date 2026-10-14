"""Tests for Task E3: per-process spend cap via BLYTE_EVAL_MAX_COST and --max-cost."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest

from lab.engine.drivers.blyte_native import BlyteNativeDriver, read_max_cost
from lab.engine.drivers.blyte_pair import BlytePairDriver
from lab.engine.drivers.container_exec_mcp import ContainerExec
from scripts.paired_run import build_parser, export_max_cost, main


@pytest.fixture(autouse=True)
def _mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    # ContainerExec._sh runs shell commands inside a container; mock to avoid needing Docker.
    monkeypatch.setattr(ContainerExec, "_sh", lambda self, script: (0, ""))


# --- 1. Helper: read_max_cost ---


def test_read_max_cost_unset_or_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BLYTE_EVAL_MAX_COST", raising=False)
    assert read_max_cost() is None

    monkeypatch.setenv("BLYTE_EVAL_MAX_COST", "")
    assert read_max_cost() is None

    monkeypatch.setenv("BLYTE_EVAL_MAX_COST", "   ")
    assert read_max_cost() is None


def test_read_max_cost_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLYTE_EVAL_MAX_COST", "2.5")
    assert read_max_cost() == 2.5

    monkeypatch.setenv("BLYTE_EVAL_MAX_COST", " 10.0 ")
    assert read_max_cost() == 10.0


def test_read_max_cost_rejects_non_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLYTE_EVAL_MAX_COST", "0")
    with pytest.raises(ValueError, match="positive"):
        read_max_cost()

    monkeypatch.setenv("BLYTE_EVAL_MAX_COST", "-1.5")
    with pytest.raises(ValueError, match="positive"):
        read_max_cost()


def test_read_max_cost_rejects_invalid_string(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLYTE_EVAL_MAX_COST", "not-a-number")
    with pytest.raises(ValueError):
        read_max_cost()


# --- 2. BlyteNativeDriver.build_command ---


def test_blyte_native_driver_max_cost_when_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("BLYTE_EVAL_MAX_COST", "2.5")
    fake_bin = tmp_path / "blyte"
    fake_bin.touch(mode=0o755)

    driver = BlyteNativeDriver(model="test-model", blyte_bin=fake_bin)
    cmd = driver.build_command(
        prompt="Fix the bug.",
        container_id="cnt-1",
        report_path=tmp_path / "report.json",
        timeout_sec=60.0,
    )

    assert "--max-cost" in cmd
    idx = cmd.index("--max-cost")
    assert cmd[idx + 1] == "2.5"
    assert idx < cmd.index("--")


def test_blyte_native_driver_max_cost_when_unset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("BLYTE_EVAL_MAX_COST", raising=False)
    fake_bin = tmp_path / "blyte"
    fake_bin.touch(mode=0o755)

    driver = BlyteNativeDriver(model="test-model", blyte_bin=fake_bin)
    cmd = driver.build_command(
        prompt="Fix the bug.",
        container_id="cnt-1",
        report_path=tmp_path / "report.json",
        timeout_sec=60.0,
    )

    assert "--max-cost" not in cmd


# --- 3. BlytePairDriver.build_command ---


def test_blyte_pair_driver_max_cost_when_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("BLYTE_EVAL_MAX_COST", "2.5")
    fake_bin = tmp_path / "blyte"
    fake_bin.touch(mode=0o755)

    driver = BlytePairDriver(
        model="test-model",
        implementer_model="impl-model",
        blyte_bin=fake_bin,
    )
    cmd = driver.build_command(
        prompt="Fix the bug.",
        container_id="cnt-1",
        report_path=tmp_path / "report.json",
        timeout_sec=60.0,
    )

    assert "--max-cost" in cmd
    idx = cmd.index("--max-cost")
    assert cmd[idx + 1] == "2.5"
    assert idx < cmd.index("--")


def test_blyte_pair_driver_max_cost_when_unset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("BLYTE_EVAL_MAX_COST", raising=False)
    fake_bin = tmp_path / "blyte"
    fake_bin.touch(mode=0o755)

    driver = BlytePairDriver(
        model="test-model",
        implementer_model="impl-model",
        blyte_bin=fake_bin,
    )
    cmd = driver.build_command(
        prompt="Fix the bug.",
        container_id="cnt-1",
        report_path=tmp_path / "report.json",
        timeout_sec=60.0,
    )

    assert "--max-cost" not in cmd


# --- 4. ContainerExec.dispatch and build_command ---


def test_container_exec_dispatch_max_cost_when_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("BLYTE_EVAL_MAX_COST", "2.5")
    monkeypatch.setenv("BLYTE_EVAL_CONTAINER", "cnt-test-123")
    monkeypatch.setenv("BLYTE_EVAL_WORKDIR", "/workspace")
    monkeypatch.setenv("BLYTE_IMPLEMENTER_MODEL", "gemini-3.8-flash-high")
    monkeypatch.setenv("BLYTE_DISPATCH_DIR", str(tmp_path / "dispatches"))

    captured_cmd: list[str] = []

    def mock_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured_cmd.extend(cmd)
        report_idx = cmd.index("--report")
        report_file = Path(cmd[report_idx + 1])
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_file.write_text(json.dumps({"outcome": "verified"}))
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", mock_run)

    executor = ContainerExec()

    out_text, is_err = executor.dispatch("implement feature", "pytest tests/test_feature.py")
    assert is_err is False

    assert "--max-cost" in captured_cmd
    idx = captured_cmd.index("--max-cost")
    assert captured_cmd[idx + 1] == "2.5"
    assert idx < captured_cmd.index("--")

    # Also check direct build_command
    direct_cmd = executor.build_command("implement feature", "pytest tests/test_feature.py")
    assert "--max-cost" in direct_cmd
    idx = direct_cmd.index("--max-cost")
    assert direct_cmd[idx + 1] == "2.5"


def test_container_exec_dispatch_max_cost_when_unset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("BLYTE_EVAL_MAX_COST", raising=False)
    monkeypatch.setenv("BLYTE_EVAL_CONTAINER", "cnt-test-123")
    monkeypatch.setenv("BLYTE_EVAL_WORKDIR", "/workspace")
    monkeypatch.setenv("BLYTE_IMPLEMENTER_MODEL", "gemini-3.8-flash-high")
    monkeypatch.setenv("BLYTE_DISPATCH_DIR", str(tmp_path / "dispatches"))

    captured_cmd: list[str] = []

    def mock_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured_cmd.extend(cmd)
        report_idx = cmd.index("--report")
        report_file = Path(cmd[report_idx + 1])
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_file.write_text(json.dumps({"outcome": "verified"}))
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", mock_run)

    executor = ContainerExec()

    out_text, is_err = executor.dispatch("implement feature", "pytest tests/test_feature.py")
    assert is_err is False

    assert "--max-cost" not in captured_cmd

    direct_cmd = executor.build_command("implement feature", "pytest tests/test_feature.py")
    assert "--max-cost" not in direct_cmd


# --- 5. paired_run CLI argument and export ---


def test_paired_run_parser_argument() -> None:
    parser = build_parser()
    args = parser.parse_args(["--max-cost", "2.5"])
    assert args.max_cost == 2.5

    args_default = parser.parse_args([])
    assert args_default.max_cost is None


def test_paired_run_help_text() -> None:
    parser = build_parser()
    action = next(a for a in parser._actions if "--max-cost" in a.option_strings)
    help_text = action.help or ""
    assert "cap is per process" in help_text.lower()
    assert "worst case" in help_text.lower()


def test_export_max_cost_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BLYTE_EVAL_MAX_COST", raising=False)
    export_max_cost(2.5)
    assert os.environ.get("BLYTE_EVAL_MAX_COST") == "2.5"

    with pytest.raises(ValueError, match="positive"):
        export_max_cost(0.0)

    with pytest.raises(ValueError, match="positive"):
        export_max_cost(-1.0)


def test_paired_run_main_exports_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BLYTE_EVAL_MAX_COST", raising=False)
    monkeypatch.setattr(sys, "argv", ["paired_run.py", "--max-cost", "2.5", "--keep-mcp"])
    monkeypatch.setattr("scripts.paired_run._run", lambda args: 0)

    ret = main()
    assert ret == 0
    assert os.environ.get("BLYTE_EVAL_MAX_COST") == "2.5"


def test_paired_run_main_rejects_non_positive_cost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "argv", ["paired_run.py", "--max-cost", "0", "--keep-mcp"])
    with pytest.raises(SystemExit):
        main()
