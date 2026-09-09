"""Benchmark task specification and loader module.

Parses SWE-bench / Harbor style benchmark task definitions (task.toml and instruction.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
import tomllib
from typing import Any

logger = logging.getLogger("superstate_eval.task_loader")


@dataclass
class TaskSpec:
    """Specification of an evaluation benchmark task."""

    id: str
    name: str
    instruction: str
    docker_image: str
    timeout_sec: float = 900.0
    agent_timeout_sec: float | None = None
    env: dict[str, str] = field(default_factory=dict)
    verifier_env: dict[str, str] = field(default_factory=dict)
    task_dir: Path | None = None
    collect_commands: list[str] = field(default_factory=list)
    base_commit: str | None = None
    verification_cmd: str | None = None

    @property
    def task_id(self) -> str:
        return self.id


def _extract_collect_commands(verifier_meta: dict[str, Any]) -> list[str]:
    """Ingest collector command sequences used to extract test or run artifacts."""
    collect_meta = verifier_meta.get("collect", [])
    commands: list[str] = []
    if isinstance(collect_meta, list):
        for item in collect_meta:
            if isinstance(item, str):
                commands.append(item)
            elif isinstance(item, dict):
                cmd = item.get("command") or item.get("cmd")
                if cmd is not None:
                    commands.append(str(cmd))
    elif isinstance(collect_meta, str):
        commands.append(collect_meta)
    return commands


def load_task_from_dir(task_dir: Path) -> TaskSpec:
    """Parse task.toml and instruction.md from task_dir into a TaskSpec."""
    toml_path = task_dir / "task.toml"
    if not toml_path.is_file():
        raise FileNotFoundError(f"Missing task.toml in {task_dir}")

    meta = tomllib.loads(toml_path.read_text(encoding="utf-8"))

    task_meta = meta.get("task", {})
    environment_meta = meta.get("environment", {})
    verifier_meta = meta.get("verifier", {})
    agent_meta = meta.get("agent", {})
    metadata_table = meta.get("metadata", {})

    task_name = task_meta.get("name", task_dir.name)
    task_id = task_name

    instruction_path = task_dir / "instruction.md"
    instruction = (
        instruction_path.read_text(encoding="utf-8").strip()
        if instruction_path.is_file()
        else task_meta.get("description", "")
    )

    docker_image = environment_meta.get("docker_image") or meta.get("docker_image", "")
    base_commit = metadata_table.get("base_commit_hash") or meta.get("base_commit_hash")

    timeout_sec = float(verifier_meta.get("timeout_sec") or task_meta.get("timeout_sec") or 900.0)
    agent_timeout_sec = (
        float(agent_meta.get("timeout_sec"))
        if agent_meta.get("timeout_sec") is not None
        else timeout_sec
    )

    collect_commands = _extract_collect_commands(verifier_meta)

    # Resolve verification command from verifier table or standard test files
    verification_cmd = verifier_meta.get("command")
    if not verification_cmd:
        if (task_dir / "tests" / "test.sh").is_file():
            verification_cmd = "bash /tests/test.sh"
        elif (task_dir / "tests" / "test_outputs.py").is_file():
            verification_cmd = "pytest /tests/test_outputs.py"
        else:
            verification_cmd = "pytest tests/"

    return TaskSpec(
        id=task_id,
        name=task_dir.name,
        instruction=instruction,
        docker_image=docker_image,
        timeout_sec=timeout_sec,
        agent_timeout_sec=agent_timeout_sec,
        env=environment_meta.get("env", {}),
        verifier_env=verifier_meta.get("env", {}),
        task_dir=task_dir,
        collect_commands=collect_commands,
        base_commit=base_commit,
        verification_cmd=verification_cmd,
    )


def load_benchmark_tasks(tasks_root: Path) -> list[TaskSpec]:
    """Scan directory tree for benchmark task directories containing task.toml."""
    tasks: list[TaskSpec] = []
    if not tasks_root.is_dir():
        return tasks

    for entry in sorted(tasks_root.iterdir()):
        if entry.is_dir() and (entry / "task.toml").is_file():
            try:
                tasks.append(load_task_from_dir(entry))
            except Exception as e:
                logger.warning("Failed to load task from %s: %s", entry, e)

    return tasks
