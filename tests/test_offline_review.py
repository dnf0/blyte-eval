"""Tests for offline code review evaluation script."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.eval_offline_review import (
    clean_json_response,
    get_task_instruction,
    run_review_single,
)


def test_clean_json_response() -> None:
    """Test extracting clean JSON from LLM responses."""
    assert clean_json_response('{"foo": "bar"}') == '{"foo": "bar"}'
    assert clean_json_response('```json\n{"foo": "bar"}\n```') == '{"foo": "bar"}'
    assert clean_json_response('```\n{"foo": "bar"}\n```') == '{"foo": "bar"}'
    assert clean_json_response('  {"foo": "bar"}  ') == '{"foo": "bar"}'


def test_get_task_instruction_fallback() -> None:
    """Test fallback when task instruction does not exist."""
    res = get_task_instruction("nonexistent/task-xyz-123")
    assert "missing" in res.lower()


def test_run_review_single_from_cache(tmp_path: Path) -> None:
    """Test reading review from cache if present."""
    cached_data = {
        "run_id": "test-run-123",
        "task_id": "test-task",
        "has_blocking_issues": True,
        "findings": [{"severity": "Critical", "problem": "Broken logic"}],
    }
    with patch("scripts.eval_offline_review.CACHE_DIR", tmp_path):
        cache_file = tmp_path / "test-run-123_gemini_3_8_flash_low.json"
        cache_file.write_text(json.dumps(cached_data), encoding="utf-8")

        run_record = {
            "run_id": "test-run-123",
            "task_id": "test-task",
            "git_diff": "diff --git a/a.py b/a.py",
        }
        res = run_review_single(run_record, model="gemini-3.8-flash-low")
        assert res["has_blocking_issues"] is True
        assert res["findings"][0]["severity"] == "Critical"


def test_run_review_single_parses_severity(tmp_path: Path) -> None:
    """Test severity threshold elevates has_blocking_issues if Critical or High."""
    raw_llm_output = json.dumps({
        "response": json.dumps({
            "summary": "Found bug",
            "findings": [
                {
                    "severity": "High",
                    "file": "foo.py",
                    "line_range": [1, 2],
                    "problem": "Bad parameter",
                    "suggested_fix": "Fix parameter",
                }
            ],
            "has_blocking_issues": False,  # Should be overridden because severity is High
        })
    })

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = raw_llm_output

    with patch("scripts.eval_offline_review.CACHE_DIR", tmp_path), \
         patch("subprocess.run", return_value=mock_proc):
        run_record = {
            "run_id": "test-run-456",
            "task_id": "test-task",
            "arm": "superstate_mcp",
            "git_diff": "diff --git a/b.py b/b.py",
            "gate_passed": True,
            "grader_passed": False,
        }
        res = run_review_single(run_record, model="gemini-3.8-flash-low")
        assert res["has_blocking_issues"] is True
        assert res["blocking_findings_count"] == 1
        assert res["total_findings_count"] == 1
        assert res["arm"] == "superstate_mcp"
        assert res["gate_passed"] is True
        assert res["grader_passed"] is False


def test_run_review_single_error_preserves_metadata(tmp_path: Path) -> None:
    """Test that subprocess timeouts and non-zero exits preserve metadata."""
    run_record = {
        "run_id": "test-run-err",
        "task_id": "test-task-err",
        "arm": "superstate_daemon",
        "git_diff": "diff --git a/err.py b/err.py",
        "gate_passed": True,
        "grader_passed": True,
    }

    # Test timeout
    with patch("scripts.eval_offline_review.CACHE_DIR", tmp_path), \
         patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="agy", timeout=5)):
        res = run_review_single(run_record, model="gemini-3.8-flash-low")
        assert "timed out" in res["error"]
        assert res["arm"] == "superstate_daemon"
        assert res["gate_passed"] is True
        assert res["grader_passed"] is True

    # Test non-zero exit code
    mock_fail = MagicMock()
    mock_fail.returncode = 2
    mock_fail.stderr = "Out of memory"
    with patch("scripts.eval_offline_review.CACHE_DIR", tmp_path), \
         patch("subprocess.run", return_value=mock_fail):
        res = run_review_single(run_record, model="gemini-3.8-flash-low")
        assert "exited with 2" in res["error"]
        assert res["arm"] == "superstate_daemon"
        assert res["gate_passed"] is True
        assert res["grader_passed"] is True


def test_run_review_single_handles_malformed_report(tmp_path: Path) -> None:
    """Test safe handling when LLM returns non-dict or null findings."""
    raw_llm_output = json.dumps({
        "response": json.dumps("A raw string response rather than a dict")
    })
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = raw_llm_output

    with patch("scripts.eval_offline_review.CACHE_DIR", tmp_path), \
         patch("subprocess.run", return_value=mock_proc):
        run_record = {
            "run_id": "test-malformed",
            "task_id": "test-task",
            "git_diff": "diff --git a/c.py b/c.py",
        }
        res = run_review_single(run_record, model="gemini-3.8-flash-low")
        assert res["has_blocking_issues"] is False
        assert res["findings"] == []
