"""Which tasks a comparison should actually run.

The 30-task corpus does not contain 30 usable tasks. Measured 2026-09-16 by pooling every
recorded run:

    8   ungradeable   ship no held-out tests/. The harness used to fall back to running
                      `pytest tests/` in the agent's own container, grading the agent
                      against tests it wrote. See UNMEASURABLE_TASKS and extractor.py.
    7   at ceiling    every arm solves them, every time. openssl-selfsigned-cert is
                      22/22 for vanilla alone.
    1   at floor      no arm has ever solved it (fastapi-deprecation-response-headers).
    ---
    14  usable        gradeable, and at least one arm varies.

A run over the full corpus therefore spends more than half its budget on tasks that cannot
move the result, and reports a pass rate diluted by them. That dilution is not neutral: it
compresses every arm toward the middle and makes a real difference look smaller than it is.

The split by family is stark, and it is the practical finding:

    datacurve        8 of 9 tasks usable
    terminal-bench   6 of 21 usable

WHAT "USABLE" MEANS, AND WHAT IT COSTS
--------------------------------------
Usable is a statement about measurement capacity, not about task quality. A task qualifies
when it is *gradeable* (`TaskSpec.tests_dir is not None`, so a sealed verifier exists) and
*discriminating* (pooled across every recorded run, not every arm passes and not every arm
fails). `openssl-selfsigned-cert` is excluded not because it is a poor task but because
vanilla solves it 22 times out of 22, so no arm can separate from another on it.

**Filtering to this set inflates the measured gap, by construction.** Excluding tasks where
both arms tie at a ceiling removes zero-difference cases, which raises the average
difference whether or not anything improved. Measured on the same paired runs:

    everything (incl. ungradeable)      n=55   vanilla 56%   mcp 85%   +29pp
    gradeable only                      n=48   vanilla 65%   mcp 83%   +19pp
    gradeable AND discriminating        n=26   vanilla 38%   mcp 69%   +31pp

These are two different quantities and must not be mixed:

  * **lift on the benchmark** -> the gradeable set, +19pp. This is the honest headline.
  * **lift where lift is possible** -> this set, +31pp. More sensitive, and the right set for
    mechanism work or for buying statistical power cheaply. Never quote it as a benchmark
    result.

Further limits: the 10%/90% thresholds are a judgement call, not a derived boundary; and
"ceiling" means ceiling *for gemini-3.8-flash-high* -- a weaker driver moves tasks back into
range, which is why every exclusion below states its reason rather than being deleted.

CAVEAT ON THE RATES BELOW
-------------------------
Membership here was decided by pooling runs with different models, budgets and prompt
settings, so the pooled pass rates are sound for spotting a ceiling or a floor and are NOT
effect-size estimates. Several tasks show vanilla ahead of superstate purely because early
runs carried the prompt-contract confound. Do not quote them as lift.
"""

from __future__ import annotations

# Gradeable, and at least one arm varies. Ordered by how sharply they separated the arms
# in pooled history -- see the caveat above before reading anything into that order.
DISCRIMINATING_TASKS: tuple[str, ...] = (
    # datacurve / tier-1 repository tasks: 8 of 9 usable, and the hardest in the corpus
    "scc-bounded-memory-spilling",
    "expr-try-catch-errors",
    "python-statemachine-state-data-scoping",
    "meriyah-explicit-resource-declarations",
    "httpx-multipart-response-parsing",
    "arktype-json-schema-refs-dependencies",
    "katex-multicolumn-array-spans",
    "anko-typed-variable-bindings",
    # terminal-bench: only 6 of 21 survive, the rest being ungradeable or at ceiling
    "regex-log",
    "vulnerable-secret",
    "dna-insert",
    "extract-elf",
    "build-cython-ext",
    "chess-best-move",
)

# Kept out, with the reason, so a task is never silently dropped and can be reinstated if a
# stronger driver moves it off its ceiling or floor.
EXCLUDED_TASKS: dict[str, str] = {
    "db-wal-recovery": "ceiling: 95% vanilla, 97% superstate",
    "openssl-selfsigned-cert": "ceiling: 100% vanilla over 22 runs",
    "git-leak-recovery": "ceiling: 100% vanilla over 11 runs",
    "code-from-image": "ceiling: 100% for every arm",
    "constraints-scheduling": "ceiling: 100% for every arm",
    "gcode-to-text": "ceiling: 100% vanilla over 10 runs",
    "kv-store-grpc": "ceiling: 100% vanilla over 9 runs",
    "fastapi-deprecation-response-headers": "floor: 0% vanilla, 6% superstate",
}


def is_discriminating(task_name: str) -> bool:
    """Whether a task can contribute signal to an arm-vs-arm comparison."""
    return task_name in DISCRIMINATING_TASKS


def excluded_reason(task_name: str) -> str | None:
    """Why a gradeable task is kept out of the core set, or None if it is in."""
    return EXCLUDED_TASKS.get(task_name)
