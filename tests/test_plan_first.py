"""Offload v2 gives both arms the same plan, written once by a planning run (2026-09-28)."""

import json
from pathlib import Path

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.plan_first import PLAN_HEADER, PLANNING_PROMPT, final_response, planning_task, with_plan


def _task(tmp_path: Path) -> TaskSpec:
    return TaskSpec(id="org/t", name="t", instruction="Add a feature.", docker_image="img", task_dir=tmp_path)


def test_planning_task_prefixes_the_prompt(tmp_path: Path) -> None:
    t = planning_task(_task(tmp_path))
    assert t.instruction == f"{PLANNING_PROMPT}\n\n## Task\n\nAdd a feature."
    assert "do not create, modify or delete any file" in PLANNING_PROMPT


def test_with_plan_appends_the_plan(tmp_path: Path) -> None:
    t = with_plan(_task(tmp_path), "  1. change x\n")
    assert t.instruction == f"Add a feature.\n\n{PLAN_HEADER}\n\n1. change x"


def test_final_response_is_the_last_non_empty_one(tmp_path: Path) -> None:
    lines = [{"turn": 1, "response": "first"}, {"turn": 2, "response": "  the plan  "}, {"turn": 3, "response": ""}]
    (tmp_path / "transcript.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    assert final_response(tmp_path) == "the plan"


def test_final_response_missing(tmp_path: Path) -> None:
    assert final_response(tmp_path) is None
