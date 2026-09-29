"""Plan-first mode: generate a plan once, and run every arm from that plan."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Optional

from lab.benchmarks.task_loader import TaskSpec

PLANNING_PROMPT: str = (
    "This run only plans; it does not implement. Explore the repository as much as you need, "
    "but do not create, modify or delete any file. Your final message is the plan, and it goes "
    "to an engineer who has not seen the repository. Include: the files to change and what to "
    "change in each; the required behaviour, including every edge case the task describes; the "
    "tests to add or update; and one shell command, run from the repository root, that checks "
    "the work. Be precise and complete. Do not ask questions."
)

# The parallel offload comparison (2026-09-29): a plan whose parts can be dispatched at once.
PARALLEL_PLAN_PROMPT: str = (
    "Divide the work into numbered parts. Put everything the other parts depend on (shared types, "
    "interfaces, the core logic) in part 1. Make the remaining parts independent of one another: "
    "each changes different files and can be implemented and checked on its own, at the same time "
    "as the others, once part 1 is done. For each part give its files, its behaviour and its own "
    "check command."
)

PLAN_HEADER: str = "## Plan\n\nA plan for this task has already been written. Follow it."


def planning_task(task: TaskSpec, parallel: bool = False) -> TaskSpec:
    prompt = f"{PLANNING_PROMPT} {PARALLEL_PLAN_PROMPT}" if parallel else PLANNING_PROMPT
    return dataclasses.replace(task, instruction=f"{prompt}\n\n## Task\n\n{task.instruction}")


def with_plan(task: TaskSpec, plan: str) -> TaskSpec:
    return dataclasses.replace(task, instruction=f"{task.instruction}\n\n{PLAN_HEADER}\n\n{plan.strip()}")


def final_response(logs_dir: Path) -> Optional[str]:
    transcript = logs_dir / "transcript.jsonl"
    if not transcript.is_file():
        return None
    last_resp: Optional[str] = None
    try:
        content = transcript.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            resp = record.get("response")
            if isinstance(resp, str) and resp.strip():
                last_resp = resp.strip()
    return last_resp
