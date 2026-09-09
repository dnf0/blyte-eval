"""Integration tests exercising a real Docker daemon.

The unit suite mocks `run_sandbox` entirely, which is how a bind mount that
shadowed the task repository at /app shipped undetected. These tests build a
throwaway image that ships a git repo at /app and assert the workspace the
agent writes to and the workspace the grader reads are the same populated repo.

Skipped automatically when Docker is unavailable.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
import shutil
import subprocess

import pytest

from lab.sandbox.docker_manager import DockerManager, WorkspaceSeedError

IMAGE_TAG = "superstate-eval-itest"

DOCKERFILE = """FROM alpine:latest
RUN apk add --no-cache git bash >/dev/null && mkdir -p /app && cd /app && \\
    echo "print('original source')" > main.py && \\
    git init -q && git config user.email e@l && git config user.name E && \\
    git add -A && git commit -q -m "base commit"
"""


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    return subprocess.run(["docker", "info"], capture_output=True).returncode == 0


requires_docker = pytest.mark.skipif(
    not _docker_available(), reason="Docker daemon is not available"
)


@pytest.fixture(scope="module")
def task_image() -> Iterator[str]:
    build_dir = Path(__file__).parent / "_itest_build"
    build_dir.mkdir(exist_ok=True)
    (build_dir / "Dockerfile").write_text(DOCKERFILE, encoding="utf-8")
    try:
        subprocess.run(
            ["docker", "build", "-q", "-t", IMAGE_TAG, str(build_dir)],
            check=True,
            capture_output=True,
        )
        yield IMAGE_TAG
    finally:
        shutil.rmtree(build_dir, ignore_errors=True)
        subprocess.run(["docker", "rmi", "-f", IMAGE_TAG], capture_output=True)


@requires_docker
def test_seeded_workspace_preserves_task_repo_under_bind_mount(
    task_image: str, tmp_path: Path
) -> None:
    """The regression this suite exists for.

    A bind mount shadows the image's /app. Without seeding, the agent and the
    grader both see an empty directory and every task fails.
    """
    manager = DockerManager()
    workspace = tmp_path / "workspace"

    manager.seed_workspace_from_image(image=task_image, dest=workspace)

    # The repo is on the host, where the adapters and ProgressTracker operate.
    assert (workspace / "main.py").is_file()
    assert (workspace / ".git").is_dir()

    with manager.run_sandbox(
        image=task_image,
        volumes={str(workspace.resolve()): {"bind": "/app", "mode": "rw"}},
        working_dir="/app",
        logs_dir=tmp_path / "logs",
    ) as container:
        # The container sees the same populated repo, not an empty mount point.
        code, out = container.exec_run("git -C /app rev-parse HEAD")
        assert code == 0, f"grader cannot resolve HEAD in /app: {out!r}"

        # Host-side agent edits are visible to the container-side grader.
        (workspace / "main.py").write_text("print('agent edit')\n", encoding="utf-8")
        code, out = container.exec_run("cat /app/main.py")
        assert b"agent edit" in out


@requires_docker
def test_no_network_mode_actually_blocks_egress(task_image: str, tmp_path: Path) -> None:
    """A task declaring no-network must not hand the agent internet access."""
    manager = DockerManager()
    with manager.run_sandbox(
        image=task_image,
        network_mode="none",
        logs_dir=tmp_path / "logs",
    ) as container:
        code, _ = container.exec_run("ping -c1 -W1 1.1.1.1")
        assert code != 0, "container reached the network despite network_mode=none"


@requires_docker
def test_seeding_fails_loudly_when_image_has_no_repo(task_image: str, tmp_path: Path) -> None:
    manager = DockerManager()
    with pytest.raises(WorkspaceSeedError):
        manager.seed_workspace_from_image(
            image=task_image, dest=tmp_path / "ws", source_path="/nonexistent"
        )


@requires_docker
def test_seeding_fails_loudly_when_image_is_missing(tmp_path: Path) -> None:
    manager = DockerManager()
    with pytest.raises(WorkspaceSeedError, match="unavailable"):
        manager.seed_workspace_from_image(
            image="superstate-eval-no-such-image:v0", dest=tmp_path / "ws"
        )


@requires_docker
def test_held_out_verifier_builds_and_grades_in_its_own_container(tmp_path: Path) -> None:
    """End-to-end: build the verifier image and have it write reward.json.

    Mirrors the real contract -- Dockerfile FROM the task image with hidden tests
    layered on, /logs shared, no workspace mount.
    """
    from lab.engine.verifier import HeldOutVerifier

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "Dockerfile").write_text(
        f"FROM {IMAGE_TAG}\nCOPY test.sh /tests/test.sh\nRUN chmod +x /tests/test.sh\n",
        encoding="utf-8",
    )
    # Stand-in for grader.py: apply the patch to a pristine /app, then grade.
    (tests_dir / "test.sh").write_text(
        "#!/bin/bash\n"
        "mkdir -p /logs/verifier\n"
        "cd /app || exit 6\n"
        "if [ -f /logs/artifacts/model.patch ]; then git apply /logs/artifacts/model.patch; fi\n"
        'if grep -q FIXED /app/main.py; then echo \'{"reward": 1}\' > /logs/verifier/reward.json;\n'
        'else echo \'{"reward": 0}\' > /logs/verifier/reward.json; fi\n',
        encoding="utf-8",
    )

    class Task:
        id = "org/itest"
        cpus = None
        memory_mb = None

        def __init__(self, td: Path) -> None:
            self.tests_dir = td

    manager = DockerManager()
    verifier = HeldOutVerifier(docker_manager=manager)
    logs_dir = tmp_path / "logs"
    (logs_dir / "artifacts").mkdir(parents=True)

    try:
        # No patch -> the pristine repo fails the hidden check.
        outcome = verifier.run(task=Task(tests_dir), logs_dir=logs_dir)
        assert outcome.reward == 0.0
        assert outcome.passed is False

        # A patch that makes the change -> passes.
        (logs_dir / "artifacts" / "model.patch").write_text(
            "diff --git a/main.py b/main.py\n"
            "--- a/main.py\n"
            "+++ b/main.py\n"
            "@@ -1 +1 @@\n"
            "-print('original source')\n"
            "+print('FIXED')\n",
            encoding="utf-8",
        )
        outcome = verifier.run(task=Task(tests_dir), logs_dir=logs_dir)
        assert outcome.reward == 1.0
        assert outcome.passed is True
        assert outcome.reward_source == "reward.json"
    finally:
        if outcome.image_tag:
            subprocess.run(["docker", "rmi", "-f", outcome.image_tag], capture_output=True)


@requires_docker
def test_verifier_crash_sentinel_is_not_treated_as_a_score(tmp_path: Path) -> None:
    """reward.txt == -1 is an infrastructure failure, not a legitimate 0."""
    from lab.engine.verifier import read_reward_artifacts

    logs_dir = tmp_path / "logs"
    (logs_dir / "verifier").mkdir(parents=True)
    (logs_dir / "verifier" / "reward.txt").write_text("-1", encoding="utf-8")

    reward, source, crashed, _stats = read_reward_artifacts(logs_dir)
    assert crashed is True
    assert reward is None, "a crashed verifier must not be scored"
    assert source == "reward.txt"
