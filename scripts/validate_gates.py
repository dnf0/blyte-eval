#!/usr/bin/env python3
"""Check every task image can be decomposed into the autonomous TDD DAG.

WHAT THIS CHECKS, AND WHY IT CHANGED
------------------------------------
Until 2026-09-21 this script validated the hand-authored `GATE_FIXTURES` table. Manifesto
Invariant V removed that table: a pre-seeded reproduction test leaks the function names,
argument shapes and assertion values, turning an open-ended diagnosis into a narrow
test-passing game. A verification command may now come only from the repository's own
runner, or from the RED/GREEN DAG `superstate state handoff --tdd` derives.

That replacement introduced one new pre-run failure mode. Detection in
`superstate_core::tdd` is deliberately fail-closed: a repository with no recognised runner
returns `UnknownRunner` rather than a permissive command, because degrading to `true` would
restore the vacuous gate the whole change removes. Fail-closed is right, but it means a task
whose image has no recognised marker aborts at run time rather than quietly mis-measuring.

This finds those tasks before a run spends money on them, by listing each image's repository
root and applying the engine's own detection order.

    scripts/validate_gates.py                 # every task with a local image
    scripts/validate_gates.py anko-... ...    # named tasks only

Exit status is non-zero if any task's repository cannot be classified.

WHAT IT DELIBERATELY DOES NOT CHECK
-----------------------------------
Whether the generated RED gate fails on a pristine repository, and whether GREEN passes on a
fixed one. RED requires a reproduction test that does not exist yet, so it fails by
construction, and the command shapes are pinned by unit tests in `superstate-core/src/tdd.rs`
-- including that every runner proves compilation before asserting failure, which is what
stops a syntax error satisfying RED. Confirming them against real repositories needs a seeded
workspace and belongs to a canary run, not here.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lab.benchmarks.task_loader import load_benchmark_tasks  # noqa: E402

TASKS_ROOT = Path.home() / ".cache/agent-rules/frontier-eval/tasks"

# Mirrors the detection order in superstate_core::tdd::detect_profile. Order matters: a Go
# repository that also carries a package.json for tooling is still a Go project.
DETECTION_ORDER: list[tuple[str, tuple[str, ...]]] = [
    ("go test", ("go.mod",)),
    ("npm/vitest", ("package.json",)),
    ("pytest", ("pyproject.toml", "setup.py", "setup.cfg", "pytest.ini", "tox.ini")),
]


def image_present(image: str) -> bool:
    return subprocess.run(
        ["docker", "image", "inspect", image], capture_output=True, text=True
    ).returncode == 0


def repo_root_listing(image: str) -> list[str]:
    """Names directly under /app in the task image."""
    proc = subprocess.run(
        ["docker", "run", "--rm", "--entrypoint", "sh", image, "-c", "ls -A /app 2>/dev/null"],
        capture_output=True, text=True, timeout=300,
    )
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def classify(entries: list[str]) -> str | None:
    """The runner the engine would select, or None if it would fail closed."""
    present = set(entries)
    for runner, markers in DETECTION_ORDER:
        if present.intersection(markers):
            return runner
    # The engine's last resort: a bare tests/ directory holding Python files.
    if "tests" in present:
        return "pytest (bare tests/)"
    return None


def main() -> int:
    tasks = {t.name: t for t in load_benchmark_tasks(TASKS_ROOT)}
    names = sys.argv[1:] or sorted(tasks)

    unclassified: list[str] = []
    skipped: list[tuple[str, str]] = []

    for name in names:
        task = tasks.get(name)
        if task is None or not task.docker_image:
            skipped.append((name, "no task or image declared"))
            continue
        if not image_present(task.docker_image):
            skipped.append((name, f"image not local: {task.docker_image}"))
            continue

        declared = getattr(task, "verification_cmd", None)
        entries = repo_root_listing(task.docker_image)
        runner = classify(entries)

        if runner:
            print(f"  ok      {name:40s} TDD via {runner}")
        elif declared and str(declared).strip():
            # The task ships its own runner, so TDD decomposition is never reached for it.
            print(f"  ok      {name:40s} native runner declared by the task")
        else:
            unclassified.append(name)
            sample = ", ".join(sorted(entries)[:8]) or "<empty /app>"
            print(f"  UNKNOWN {name:40s} no recognised runner; /app holds: {sample}")

    for name, why in skipped:
        print(f"  skip    {name:40s} {why}")

    tested = len(names) - len(skipped)
    print(
        f"\n{tested} task(s) checked, {len(unclassified)} cannot be decomposed, "
        f"{len(skipped)} skipped"
    )
    if unclassified:
        print(
            "\nThese repositories match no runner the engine recognises, so a run would abort "
            "at handoff. Either teach superstate_core::tdd their layout, or record them as "
            "unmeasurable:"
        )
        for name in unclassified:
            print(f"  - {name}")
    return 1 if unclassified else 0


if __name__ == "__main__":
    sys.exit(main())
