"""The gate fixtures are the contract of record, so their shape is worth pinning."""

from __future__ import annotations

import subprocess

from lab.benchmarks.gate_fixtures import (
    GATE_FIXTURES,
    agent_gate_for,
    references_sealed_grader,
)

PILOT_TASKS = [
    "sqlite-db-truncate",
    "db-wal-recovery",
    "openssl-selfsigned-cert",
    "build-cython-ext",
    "fastapi-deprecation-response-headers",
]


def test_every_pilot_task_has_a_fixture() -> None:
    missing = [t for t in PILOT_TASKS if not agent_gate_for(t)]
    assert not missing, f"tasks without a fixed contract: {missing}"


def test_no_fixture_reads_the_sealed_grader() -> None:
    """Gating on /tests/ would let the agent read the answer key it is scored against."""
    leaking = [n for n, g in GATE_FIXTURES.items() if references_sealed_grader(g)]
    assert not leaking, f"fixtures referencing the sealed grader: {leaking}"


def test_no_fixture_is_a_no_op() -> None:
    """A gate that cannot fail cannot discriminate, and the worker stops the moment it passes."""
    for name, gate in GATE_FIXTURES.items():
        stripped = gate.strip()
        assert stripped not in ("true", ":", "exit 0"), f"{name} has a vacuous gate"
        assert len(stripped) > 40, f"{name} gate is suspiciously thin: {stripped!r}"


def test_every_fixture_is_valid_shell() -> None:
    """A fixture with a quoting error fails for the wrong reason and looks like a hard task."""
    for name, gate in GATE_FIXTURES.items():
        # Strip the host-side bridge prefix; `sh -n` parses without executing.
        body = gate.replace("./run-in-container ", "", 1)
        res = subprocess.run(
            ["sh", "-n", "-c", body], capture_output=True, text=True, timeout=30
        )
        assert res.returncode == 0, f"{name} gate is not valid shell: {res.stderr.strip()}"


def test_fixtures_exercise_behaviour_not_mere_presence() -> None:
    """A derived gate once reduced to `test -f <file> && not-on-main`, satisfiable by touch.

    Each fixture must actually run something -- import the module, execute the suite,
    inspect the artifact's contents -- rather than only assert a path exists.
    """
    # Either execute something, or inspect the CONTENT of what was produced. A gate that
    # only asserts a path exists is satisfiable by `touch`, which is the failure mode this
    # guards against -- a derived gate once reduced to `test -f <file> && not-on-main`.
    runners = ("python", "pytest", "openssl", "go build", "go test", "go run",
               "node", "npm", "npx", "git ", "gcc ")
    content_checks = ("grep ", "cmp -s", "[ \"$(")
    for name, gate in GATE_FIXTURES.items():
        assert any(tok in gate for tok in runners + content_checks), (
            f"{name} gate only checks for presence, not behaviour or content"
        )


def test_unmeasurable_tasks_are_documented_with_a_reason() -> None:
    """A task whose grader cannot run scores every arm zero and shrinks the denominator.

    sqlite-db-truncate ships no tests/ dir, so the loader falls back to `pytest tests/`
    and the image has no pytest -- exit 127 for vanilla, solo and daemon alike. Recording
    it stops it silently creeping back into a run.
    """
    from lab.benchmarks.gate_fixtures import UNMEASURABLE_TASKS, is_unmeasurable

    assert UNMEASURABLE_TASKS, "expected at least the known-broken task to be recorded"
    for name, reason in UNMEASURABLE_TASKS.items():
        assert reason.strip(), f"{name} excluded without a stated reason"
        assert is_unmeasurable(name) == reason
    assert is_unmeasurable("db-wal-recovery") is None
