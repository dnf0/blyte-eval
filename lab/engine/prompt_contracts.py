"""Portable execution discipline prompt rules, OFF by default.

The five rules below are the ones that are both true and meaningful without a state
machine. Giving these to an arm tests whether the discipline is portable:

  * if they lift vanilla, the discipline rules are doing the work;
  * if they do not, the discipline only pays off when there is a gate to stop at
    and a milestone to scope to.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("superstate_eval.prompt_contracts")

GENERIC_EXECUTION_RULES = (
    "## EXECUTION DISCIPLINE\n"
    "1. **SCOPE BOUNDARY:** Modify ONLY files directly related to this task. Do not touch unrelated files.\n"
    "2. **ZERO GLOBAL EXPLORATION:** Do not run recursive grep/find across the whole codebase or dump whole directories.\n"
    "3. **ZERO-READ EXECUTION:** Use targeted symbol lookup or line-bounded reads. Never cat entire files into context.\n"
    "4. **NO EXTERNAL LINTER PROBING:** Do not run external linters or formatters. Focus solely on making tests pass.\n"
    "5. **DO NOT READ SKILL OR RULES FILES:** Do not inspect GEMINI.md, AGENTS.md, or .cursorrules."
)

GENERIC_RULES_ENV_FLAG = "SUPERSTATE_EVAL_GENERIC_RULES"


def generic_rules_enabled() -> bool:
    """Whether the portable discipline rules are injected into arms."""
    return os.environ.get(GENERIC_RULES_ENV_FLAG, "0").strip().lower() in ("1", "true", "yes", "on")


def apply_generic_rules(prompt: str, arm: str) -> str:
    """Append the portable discipline rules to an arm's prompt, if enabled."""
    if not generic_rules_enabled():
        return prompt
    logger.info("Injecting generic execution rules for %s (%s=1)", arm, GENERIC_RULES_ENV_FLAG)
    return f"{prompt}\n\n{GENERIC_EXECUTION_RULES}"
