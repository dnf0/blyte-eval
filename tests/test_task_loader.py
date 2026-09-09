"""Tests for Benchmark Task Loader in lab/benchmarks/task_loader.py."""

from __future__ import annotations

from pathlib import Path

from lab.benchmarks.task_loader import TaskSpec, load_benchmark_tasks, load_task_from_dir


def test_load_task_from_dir_parses_task_toml_and_instruction(tmp_path: Path) -> None:
    task_dir = tmp_path / "sample-task"
    task_dir.mkdir()
    toml_content = """
schema_version = "1.3"
[task]
name = "datacurve/sample-task"
[metadata]
base_commit_hash = "abc1234"
[agent]
timeout_sec = 3600.0
[environment]
docker_image = "sample/repo:v1"
[verifier]
timeout_sec = 600.0
[[verifier.collect]]
command = "git diff abc1234 HEAD > /logs/artifacts/model.patch"
"""
    (task_dir / "task.toml").write_text(toml_content, encoding="utf-8")
    (task_dir / "instruction.md").write_text(
        "Implement feature X with full test coverage.", encoding="utf-8"
    )

    task = load_task_from_dir(task_dir)

    assert isinstance(task, TaskSpec)
    assert task.id == "datacurve/sample-task"
    assert task.name == "sample-task"
    assert task.docker_image == "sample/repo:v1"
    assert task.timeout_sec == 600.0
    assert task.agent_timeout_sec == 3600.0
    assert task.base_commit == "abc1234"
    assert "Implement feature X" in task.instruction
    assert len(task.collect_commands) == 1
    assert "git diff abc1234" in task.collect_commands[0]


def test_load_benchmark_tasks_scans_multiple_directories(tmp_path: Path) -> None:
    root = tmp_path / "tasks"
    root.mkdir()
    for name in ["task-1", "task-2"]:
        td = root / name
        td.mkdir()
        (td / "task.toml").write_text(
            f'[task]\nname = "test/{name}"\n[environment]\ndocker_image = "img:{name}"\n',
            encoding="utf-8",
        )
        (td / "instruction.md").write_text(f"Instruction for {name}", encoding="utf-8")

    tasks = load_benchmark_tasks(root)
    assert len(tasks) == 2
    task_ids = {t.id for t in tasks}
    assert "test/task-1" in task_ids
    assert "test/task-2" in task_ids
