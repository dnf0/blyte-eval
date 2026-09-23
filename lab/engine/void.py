"""Runs that produce no measurement, and must not be scored as failures.

Two different things can make a run unscoreable, and neither is the agent's doing:

* **UNMEASURABLE** -- nobody can grade the task. It ships no sealed grader, so there is no
  verifier to run. This is a property of the TASK and applies to every arm equally.
* **UNGATEABLE** -- this arm could not derive a verification command for a task that is
  otherwise perfectly gradeable. This is a property of the ARM, not the task: the same task
  may run fine under another arm.

Both were previously recorded as `passed=False`, which is wrong in the same way and for the
same reason: a task nobody could mark, and a task this arm could not start, both get counted
as work the agent failed to do. Measured consequence -- `build-cython-ext` passed 17 of 18
runs, then failed seven consecutive canaries in 5-8 seconds at $0.00 because autonomous TDD
cannot derive a gate from the empty `/app` the task deliberately ships. Every canary pass rate
from EXP-074 to EXP-080 is over three tasks of which one was a guaranteed zero. See
FINDINGS.md 13.20.

The distinction matters for what you do about it. An UNMEASURABLE task should leave the corpus.
An UNGATEABLE run is a gap in the arm and should be fixed in the arm.
"""

from __future__ import annotations

from typing import Optional

#: The task cannot be graded by anyone -- no sealed grader exists.
UNMEASURABLE_PREFIX = "UNMEASURABLE:"

#: This arm could not derive a verification command. The task itself is gradeable.
UNGATEABLE_PREFIX = "UNGATEABLE:"

_VOID_PREFIXES = (UNMEASURABLE_PREFIX, UNGATEABLE_PREFIX)


def is_void(failure_reason: Optional[str]) -> bool:
    """Whether this run produced no measurement and must be kept out of pass rates.

    Matches anywhere in the string rather than only at the start: the runner composes a
    failure reason from the agent-side cause and the grading message, so the marker can end
    up mid-string.
    """
    if not failure_reason:
        return False
    return any(p in failure_reason for p in _VOID_PREFIXES)


def void_kind(failure_reason: Optional[str]) -> Optional[str]:
    """`"unmeasurable"`, `"ungateable"`, or None when the run was actually measured."""
    if not failure_reason:
        return None
    if UNGATEABLE_PREFIX in failure_reason:
        return "ungateable"
    if UNMEASURABLE_PREFIX in failure_reason:
        return "unmeasurable"
    return None
