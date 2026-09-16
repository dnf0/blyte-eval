#!/usr/bin/env python3
"""Run each agent-facing gate inside a pristine task container.

A gate that PASSES on an untouched workspace cannot discriminate: it certifies work
nobody has done. `gate_fixtures.py` asserts in prose that every entry was validated this
way; this makes the claim checkable.

It is the cheapest guard we have against the failure measured in EXP-047, where the gate
ran 20 times, passed 20 times, and was wrong on 8 of them -- zero recall against bad work.

    scripts/validate_gates.py                 # every gate with a local image
    scripts/validate_gates.py dna-insert ...  # named tasks only

Exit status is non-zero if any gate passes on a pristine container.
"""

from __future__ import annotations

from pathlib import Path
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


def main() -> int:
    tasks = {t.name: t for t in load_benchmark_tasks(TASKS_ROOT)}
    names = sys.argv[1:] or sorted(n for n in GATE_FIXTURES if n in tasks)

    bad, skipped, inconclusive = [], [], []
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
        elif proc.returncode == 0:
            bad.append(name)
            print(f"  PASSES  {name:34s} <- CANNOT DISCRIMINATE {detail}")
        else:
            limitation = " [LIMITATION]" if "GATE LIMITATION" in proc.stdout else ""
            print(f"  fails   {name:34s} exit={proc.returncode}{limitation} {detail}")

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
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
