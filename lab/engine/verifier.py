"""Held-out verification in a separate container.

The benchmark's own contract (task.toml: `[verifier] environment_mode = "separate"`)
puts grading in its own image, built from the task's `tests/` directory, which
layers the hidden tests on top of the task image. The agent never sees that image.

The verifier does NOT grade the agent's workspace. It applies `model.patch` to a
pristine `/app` from the image and runs the hidden suites, so an agent that edited
the tests, left junk in the tree, or tampered with the harness cannot influence
its own grade. Only `/logs` is shared, carrying the patch in and `reward.json` out.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
import re
from typing import Any, Optional
import uuid

from lab.sandbox.docker_manager import DockerManager, ImageBuildError

logger = logging.getLogger("superstate_eval.verifier")

VERIFIER_ENTRYPOINT = "bash /tests/test.sh"
# test.sh writes this sentinel when it crashes before producing a reward.
CRASH_SENTINEL = -1.0


@dataclass
class VerifierOutcome:
    """Result of running the held-out verifier."""

    reward: Optional[float]
    exit_code: int
    output: str
    reward_source: str
    crashed: bool = False
    image_tag: Optional[str] = None
    apply_failed: bool = False
    stats: dict[str, Any] | None = None

    @property
    def passed(self) -> bool:
        """Strict gate: the verifier must have produced a reward of 1.0."""
        return self.reward is not None and self.reward >= 1.0


def _sanitize_tag(task_id: str) -> str:
    """Docker tags allow a restricted character set; task ids do not."""
    slug = re.sub(r"[^a-z0-9_.-]+", "-", task_id.lower()).strip("-._") or "task"
    return slug[:100]


def read_reward_artifacts(logs_dir: Path) -> tuple[Optional[float], str, bool, dict[str, Any] | None]:
    """Read reward.json, falling back to the reward.txt crash sentinel.

    Returns (reward, source, crashed, stats).
    """
    verifier_dir = logs_dir / "verifier"
    reward_json = verifier_dir / "reward.json"
    if reward_json.is_file():
        try:
            data = json.loads(reward_json.read_text(encoding="utf-8"))
            raw = data.get("reward")
            reward = float(raw) if raw is not None else None
            return reward, "reward.json", False, data
        except Exception as err:
            logger.warning("Failed to parse %s: %s", reward_json, err)
            return None, "reward.json:unparseable", False, None

    reward_txt = verifier_dir / "reward.txt"
    if reward_txt.is_file():
        try:
            value = float(reward_txt.read_text(encoding="utf-8").strip())
        except Exception as err:
            logger.warning("Failed to parse %s: %s", reward_txt, err)
            return None, "reward.txt:unparseable", True, None
        # The verifier frame writes -1 when it crashed before grading.
        crashed = value == CRASH_SENTINEL
        return (None if crashed else value), "reward.txt", crashed, None

    return None, "absent", False, None


class HeldOutVerifier:
    """Builds and runs the task's own verifier image."""

    def __init__(
        self,
        docker_manager: DockerManager | None = None,
        build_timeout_sec: int = 1800,
    ) -> None:
        self.docker_manager = docker_manager or DockerManager()
        self.build_timeout_sec = build_timeout_sec

    def build(self, task: Any) -> str:
        """Build the verifier image for `task` and return its tag."""
        tests_dir = task.tests_dir
        if tests_dir is None:
            raise ImageBuildError(
                f"Task '{getattr(task, 'id', '?')}' has no tests/Dockerfile to build a verifier from"
            )
        tag = f"superstate-eval-verifier/{_sanitize_tag(str(task.id))}:latest"
        return self.docker_manager.build_image(
            context_dir=tests_dir, tag=tag, timeout=self.build_timeout_sec
        )

    def run(self, task: Any, logs_dir: Path, network_mode: str | None = "none") -> VerifierOutcome:
        """Run the held-out verifier against the collected patch.

        `logs_dir` must already contain artifacts/model.patch; the verifier writes
        verifier/reward.json back into it.
        """
        image_tag = self.build(task)

        run_id = f"verify-{_sanitize_tag(str(task.id))}-{uuid.uuid4().hex[:8]}"
        nano_cpus = int(task.cpus * 1e9) if getattr(task, "cpus", None) else None
        mem_limit = f"{task.memory_mb}m" if getattr(task, "memory_mb", None) else "4g"

        with self.docker_manager.run_sandbox(
            image=image_tag,
            command="sleep infinity",
            logs_dir=logs_dir,
            container_name=run_id,
            # Deliberately no workspace mount: the verifier grades the patch against
            # a pristine /app, not whatever the agent left behind.
            working_dir="/app",
            network_mode=network_mode,
            nano_cpus=nano_cpus,
            mem_limit=mem_limit,
        ) as container:
            exec_res = container.exec_run(VERIFIER_ENTRYPOINT)
            if isinstance(exec_res, tuple):
                exit_code, raw = exec_res[0], exec_res[1]
            else:
                exit_code = getattr(exec_res, "exit_code", 1)
                raw = getattr(exec_res, "output", b"")
            output = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)

        reward, source, crashed, stats = read_reward_artifacts(logs_dir)
        apply_failed = bool(stats.get("apply_failed")) if isinstance(stats, dict) else False

        if crashed:
            logger.error(
                "Held-out verifier crashed for task=%s (reward.txt sentinel); "
                "this is an infrastructure failure, not an agent failure.",
                task.id,
            )
        elif apply_failed:
            logger.warning("model.patch failed to apply for task=%s; graded 0", task.id)

        return VerifierOutcome(
            reward=reward,
            exit_code=int(exit_code) if exit_code is not None else 1,
            output=output,
            reward_source=source,
            crashed=crashed,
            image_tag=image_tag,
            apply_failed=apply_failed,
            stats=stats,
        )
