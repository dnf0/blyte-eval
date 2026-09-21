"""Sealed-grader detection. The hand-authored gate fixtures that lived here are gone.

WHY THEY WERE REMOVED (2026-09-21)
----------------------------------
Manifesto Invariant V: "Autonomous software engineering cannot rely on synthetic
hand-authored scaffolds or answer-key leakage. Pre-seeding maintainer reproduction tests is
cheating; it turns an open-ended engineering diagnosis into a narrow test-passing game."

A fixture hands the worker the function names, argument shapes and assertion values. What
remains is passing someone else's test, not diagnosing an issue -- and diagnosis is the
capability the benchmark exists to measure.

They also failed on their own terms. Of thirty entries, `anko-typed-variable-bindings` and
`meriyah-explicit-resource-declarations` emitted source that could not compile, so they
tested nothing while three runs were recorded `completed` through the advisory-advance path;
`expr-try-catch-errors` asserted behaviour the task's own reference solution does not
implement; `arktype-json-schema-refs-dependencies` used an object schema its own library
rejects. On the datacurve family their precision was 17%, and superstate -- which stops when
the gate says done -- scored 11pp BELOW an ungated baseline. See FINDINGS.md 13.3.

WHAT REPLACED THEM
------------------
`docs/EVALUATION-PHILOSOPHY.md` Invariant 2 allows exactly two sources for a verification
command, and `lab/engine/adapters/superstate_daemon.py::_derive_gate` chooses between them:

  1. The repository's own test runner, when the task ships one that is not the sealed
     grader -- the broken-on-turn-0 case, where the native suite already discriminates.
  2. Autonomous TDD, otherwise: `superstate state handoff --tdd` derives a RED/GREEN DAG
     from the repository inside the engine. The worker authors its own reproduction test;
     the gate proves it compiles and FAILS, then that it and the existing suite PASS.

Do not reintroduce a fixture table here. If a task cannot be gated by either source, that is
a fact about the task -- record it rather than papering over it with a hand-written gate.
"""

from __future__ import annotations

import re
from typing import Optional

# The sealed grader lives at `/tests/` in the container ROOT. A package's own suite at
# `/app/<pkg>/tests/` is a legitimate gate and must not be confused with it -- a plain
# `"/tests/" in cmd` substring test rejects exactly the gate build-cython-ext needs,
# since its instruction explicitly asks for the repository's own tests to keep passing.
SEALED_GRADER_RE = re.compile(r"(?:^|[\s;&|(<'\"])/tests/|(?:^|[\s;&|(])bash\s+/tests\b")


def references_sealed_grader(command: Optional[str]) -> bool:
    """Whether a command reads the sealed held-out grader at the container root."""
    if not command:
        return False
    return bool(SEALED_GRADER_RE.search(command))


# Tasks whose SEALED GRADER cannot run, so every arm scores zero regardless of its work.
# These are not hard tasks -- they are unmeasurable, and including them silently depresses
# every arm's pass rate and shrinks the paired-comparison denominator.
UNMEASURABLE_TASKS: dict[str, str] = {
    # Ships no tests/ directory, so task_loader falls back to `pytest tests/` -- and pytest
    # is not installed in the image. Observed exit 127 for vanilla, solo and daemon alike:
    #   OCI runtime exec failed: exec: "pytest": executable file not found in $PATH
    # Re-include once the task carries a verifier that actually executes.
    "sqlite-db-truncate": "grader exits 127: pytest not present in the task image",
    # The seven below ship no held-out tests/ directory at all. task_loader falls back to
    # `pytest tests/`, which the harness then runs INSIDE THE AGENT'S OWN CONTAINER -- so
    # whatever the agent wrote into tests/ becomes the grader. That is self-grading, and it
    # is not symmetrical between arms: measured 2026-09-16 over 55 paired runs, these tasks
    # went vanilla 0/7 and superstate_mcp 7/7, because superstate's handoff prompt asks the
    # worker to produce and run a verification command while the baseline gets no such
    # instruction. They supplied 7 of the 18 discordant pairs behind the headline lift.
    #
    # Where the agent writes no tests/, the same fallback instead exits 127 (pytest absent)
    # and scores zero for every arm. So these tasks are simultaneously a source of spurious
    # passes and spurious failures. extractor.py now refuses to grade them at all.
    "largest-eigenval": "no held-out tests/; grading would run the agent's own tests",
    "log-summary-date-ranges": "no held-out tests/; grading would run the agent's own tests",
    "merge-diff-arc-agi-task": "no held-out tests/; grading would run the agent's own tests",
    "modernize-scientific-stack": "no held-out tests/; grading would run the agent's own tests",
    "multi-source-data-merger": "no held-out tests/; grading would run the agent's own tests",
    "polyglot-c-py": "no held-out tests/; grading would run the agent's own tests",
    "sanitize-git-repo": "no held-out tests/; grading would run the agent's own tests",
}


def is_unmeasurable(task_name: str) -> Optional[str]:
    """Reason a task cannot be scored, or None if it can."""
    return UNMEASURABLE_TASKS.get(task_name)
