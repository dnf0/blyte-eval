"""The held-out tests must be unreadable while a host-side agent is working."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lab.sandbox.answer_key import AnswerKeyGuard, is_readable


@pytest.fixture
def tests_dir(tmp_path: Path) -> Path:
    d = tmp_path / "tests"
    d.mkdir()
    (d / "test.patch").write_text("THE ANSWER KEY", encoding="utf-8")
    return d


def _guard(tmp_path: Path) -> AnswerKeyGuard:
    return AnswerKeyGuard(state_file=tmp_path / "state.json")


def test_sealed_directory_cannot_be_read_even_by_its_owner(
    tests_dir: Path, tmp_path: Path
) -> None:
    guard = _guard(tmp_path)
    assert is_readable(tests_dir)

    with guard.sealed([tests_dir]):
        assert not is_readable(tests_dir)
        with pytest.raises(PermissionError):
            (tests_dir / "test.patch").read_text()

    assert is_readable(tests_dir)
    assert (tests_dir / "test.patch").read_text() == "THE ANSWER KEY"


def test_original_mode_is_restored_not_guessed(tests_dir: Path, tmp_path: Path) -> None:
    tests_dir.chmod(0o750)
    with _guard(tmp_path).sealed([tests_dir]):
        pass
    assert oct(tests_dir.stat().st_mode)[-3:] == "750"


def test_directory_is_unsealed_even_when_the_run_raises(
    tests_dir: Path, tmp_path: Path
) -> None:
    guard = _guard(tmp_path)
    with pytest.raises(RuntimeError):
        with guard.sealed([tests_dir]):
            raise RuntimeError("agent crashed")
    assert is_readable(tests_dir), "a failed run must not leave the task cache locked"


def test_a_hard_kill_is_healed_by_the_next_run(tests_dir: Path, tmp_path: Path) -> None:
    # Simulate a SIGKILL: sealed on disk, mode recorded, no restore ever ran.
    state = tmp_path / "state.json"
    state.write_text(json.dumps({str(tests_dir): 0o755}), encoding="utf-8")
    tests_dir.chmod(0o000)
    assert not is_readable(tests_dir)

    _guard(tmp_path).restore_all()

    assert is_readable(tests_dir)
    assert json.loads(state.read_text()) == {}


def test_sealing_survives_a_missing_directory(tmp_path: Path) -> None:
    with _guard(tmp_path).sealed([tmp_path / "does-not-exist"]) as sealed:
        assert sealed == []


def test_nothing_is_sealed_when_there_is_nothing_to_protect(tmp_path: Path) -> None:
    with _guard(tmp_path).sealed([]) as sealed:
        assert sealed == []
