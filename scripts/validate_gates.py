#!/usr/bin/env python3
"""Validate each agent-facing gate in BOTH directions inside the task container.

A gate is only useful if it can tell done from not-done, which is two claims, not one:

  NEGATIVE  it must FAIL on a pristine workspace. A gate that already passes certifies
            work nobody has done. This is the failure measured in EXP-047, where the gate
            ran 20 times, passed 20 times, and was wrong on 8 of them.

  POSITIVE  it must PASS once the task's own reference solution is applied. A gate that
            rejects the reference fix cannot be satisfied by any correct implementation.

Only the negative direction was checked until 2026-09-21, and three gates reached
production that could never pass: `anko-typed-variable-bindings` and
`meriyah-explicit-resource-declarations` emitted source with a raw newline inside a string
literal and failed to compile, while `expr-try-catch-errors` asserted behaviour the
reference solution does not implement. All three failed pristine, so all three looked
healthy. See FINDINGS.md 13.3.

The positive direction runs only where the task ships a readable
`solution/solution.patch` (8 of the 9 `SWE_CORE_TASKS`).

    scripts/validate_gates.py                    # both directions, every local image
    scripts/validate_gates.py dna-insert ...     # named tasks only
    scripts/validate_gates.py --negative-only    # skip the reference-solution pass

Exit status is non-zero if any gate passes on a pristine container, or fails with the
reference solution applied.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lab.benchmarks.gate_fixtures import GATE_FIXTURES, agent_gate_for  # noqa: E402
from lab.benchmarks.task_loader import load_benchmark_tasks  # noqa: E402

TASKS_ROOT = Path.home() / ".cache/agent-rules/frontier-eval/tasks"
BODY = re.compile(r"\| \./run-in-container sh -s\n(.*)\nGATEEOF\Z", re.S)
NOISE = ("platform", "WARNING:")


def image_present(image: str) -> bool:
    out = subprocess.run(
        ["docker", "image", "inspect", image], capture_output=True, text=True
    )
    return out.returncode == 0


PATCH_SENTINEL = "SUPERSTATE_SOLUTION_PATCH_EOF"

# Generator inputs whose compiled output is a separate checked-in file. A reference patch that
# edits one of these without shipping the regenerated artefact cannot be built by applying the
# patch alone, so the gate's verdict against it says nothing about the gate.
# `anko-typed-variable-bindings` is the live example: its patch rewrites `parser/parser.go.y`
# but not the goyacc-generated `parser/parser.go`, so the new `var x: int64` syntax never parses.
GENERATOR_INPUTS = {".y": ".go", ".proto": ".pb.go", ".pegjs": ".js", ".l": ".go"}


def patched_paths(patch: str) -> list[str]:
    """Repository paths a unified diff writes to."""
    return [
        line[6:].strip()
        for line in patch.splitlines()
        if line.startswith("+++ b/")
    ]


def unbuildable_reason(patch: str) -> Optional[str]:
    """Why applying this patch cannot yield a working tree, or None if it can.

    Only detects the case we have actually been bitten by: a generator input edited without
    its generated output. It is deliberately narrow -- a wrong "unverifiable" hides a real
    broken gate, which is the defect this whole check exists to catch.
    """
    paths = patched_paths(patch)
    for path in paths:
        for src_ext, out_ext in GENERATOR_INPUTS.items():
            if not path.endswith(src_ext):
                continue
            stem = path[: -len(src_ext)]
            # goyacc and friends name the input after the output (`parser.go.y` -> `parser.go`),
            # so only append the output extension when the stem does not already carry one.
            generated = stem if stem.endswith(out_ext) else stem + out_ext
            if generated not in paths:
                return f"patches {path} but not the generated {generated}"
    return None


def solution_patch_for(name: str) -> Optional[str]:
    """Reference fix shipped with the task, or None when it is absent or unreadable.

    The sealed grader at `tests/` is permission-locked, but `solution/solution.patch` is
    not: it is the maintainer's own fix, which any honest gate must accept.
    """
    path = TASKS_ROOT / name / "solution" / "solution.patch"
    try:
        text = path.read_text()
    except (OSError, UnicodeDecodeError):
        return None
    return text if text.strip() else None


def run_with_reference_solution(image: str, body: str, patch: str) -> subprocess.CompletedProcess:
    """Apply the task's reference fix, then run the gate body over the fixed tree.

    `git apply` is tried first and `patch -p1` second, because the task images do not agree
    on which is available.
    """
    script = (
        "set -e\n"
        "cd /app\n"
        f"cat > /tmp/solution.patch <<'{PATCH_SENTINEL}'\n"
        f"{patch}\n"
        f"{PATCH_SENTINEL}\n"
        "git apply /tmp/solution.patch 2>/dev/null "
        "|| patch -p1 --batch --forward < /tmp/solution.patch >/dev/null\n"
        "set +e\n"
        f"{body}\n"
    )
    return subprocess.run(
        ["docker", "run", "--rm", "-i", "--entrypoint", "sh", image, "-s"],
        input=script, capture_output=True, text=True, timeout=1800,
    )


def main() -> int:
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    negative_only = "--negative-only" in sys.argv[1:]
    tasks = {t.name: t for t in load_benchmark_tasks(TASKS_ROOT)}
    names = argv or sorted(n for n in GATE_FIXTURES if n in tasks)

    bad, skipped, inconclusive = [], [], []
    rejects_reference, no_reference, unverifiable = [], [], []
    for name in names:
        task = tasks.get(name)
        if task is None or not task.docker_image:
            skipped.append((name, "no task or image declared"))
            continue
        if not image_present(task.docker_image):
            skipped.append((name, f"image not local: {task.docker_image}"))
            continue

        gate = agent_gate_for(name) or ""
        match = BODY.search(gate)
        body = match.group(1) if match else gate
        proc = subprocess.run(
            ["docker", "run", "--rm", "-i", "--entrypoint", "sh", task.docker_image, "-s"],
            input=body, capture_output=True, text=True, timeout=600,
        )
        lines = [
            ln for ln in (proc.stderr or proc.stdout).strip().splitlines()
            if not any(n in ln for n in NOISE)
        ]
        detail = lines[-1][:120] if lines else ""
        if "run-in-container: not found" in (proc.stderr or ""):
            # The gate nests a further ./run-in-container call, which exists only in a
            # prepared workspace. Exit 127 here says nothing about whether the gate can
            # discriminate, so it must not be reported as a pass.
            inconclusive.append(name)
            print(f"  ?       {name:34s} INCONCLUSIVE -- needs a prepared workspace")
            # The positive direction would fail on the same missing bridge script, which
            # would read as "the gate rejects the reference solution" and be a false
            # accusation. Neither direction is testable here.
            continue
        elif proc.returncode == 0:
            bad.append(name)
            print(f"  PASSES  {name:34s} <- CANNOT DISCRIMINATE {detail}")
            continue
        else:
            limitation = " [LIMITATION]" if "GATE LIMITATION" in proc.stdout else ""
            print(f"  fails   {name:34s} exit={proc.returncode}{limitation} {detail}")

        # Positive direction: the gate must accept the maintainer's own fix. A gate that
        # fails pristine AND fails with the reference solution applied is not strict --
        # it is broken, and nothing the worker writes can satisfy it.
        if negative_only:
            continue
        patch = solution_patch_for(name)
        if patch is None:
            no_reference.append(name)
            print(f"          {name:34s} (no reference solution; positive direction unchecked)")
            continue
        unbuildable = unbuildable_reason(patch)
        if unbuildable:
            unverifiable.append((name, unbuildable))
            print(f"  ?       {name:34s} UNVERIFIABLE -- reference {unbuildable}")
            continue
        try:
            pos = run_with_reference_solution(task.docker_image, body, patch)
        except subprocess.TimeoutExpired:
            no_reference.append(name)
            print(f"          {name:34s} (reference-solution run timed out)")
            continue
        pos_lines = [
            ln for ln in (pos.stderr or pos.stdout).strip().splitlines()
            if not any(n in ln for n in NOISE)
        ]
        pos_detail = pos_lines[-1][:120] if pos_lines else ""
        if pos.returncode == 0:
            print(f"  ok      {name:34s} accepts the reference solution")
        else:
            rejects_reference.append(name)
            print(
                f"  REJECTS {name:34s} <- FAILS WITH THE REFERENCE SOLUTION APPLIED "
                f"exit={pos.returncode} {pos_detail}"
            )

    for name, why in skipped:
        print(f"  skip    {name:34s} {why}")
    tested = len(names) - len(skipped) - len(inconclusive)
    print(
        f"\n{tested} gate(s) actually tested, {len(bad)} pass on a pristine container, "
        f"{len(inconclusive)} inconclusive, {len(skipped)} skipped"
    )
    if inconclusive:
        print(
            "\nInconclusive gates nest their own ./run-in-container call and can only be "
            "validated inside a prepared workspace:"
        )
        for name in inconclusive:
            print(f"  - {name}")
    if bad:
        print("\nA gate that passes before any work cannot tell done from not-done:")
        for name in bad:
            print(f"  - {name}")
    if rejects_reference:
        print(
            "\nGates that disagree with the task's own reference solution. Usually the gate is "
            "wrong and cannot be satisfied by any correct implementation -- but the reference "
            "can also lag the instruction the worker is given, so adjudicate before weakening "
            "a gate (see the arktype note in gate_fixtures.py):"
        )
        for name in rejects_reference:
            print(f"  - {name}")
    if unverifiable:
        print(
            "\nReference solutions that cannot be built by applying the patch, so their gates "
            "are still unvalidated in the positive direction:"
        )
        for name, why in unverifiable:
            print(f"  - {name}: {why}")
    if no_reference and not negative_only:
        print(
            f"\n{len(no_reference)} gate(s) ship no readable reference solution, so only the "
            "negative direction was checked."
        )
    return 1 if (bad or rejects_reference) else 0


if __name__ == "__main__":
    sys.exit(main())
