"""Blind patch extraction and held-out verifier scoring.

Executes uniformly across Vanilla, Superpowers, and Superstate arms.
Extracts git diff patches against the task base commit and grades
using the held-out verification command and verifier/reward.json.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
import shutil
from typing import Any

logger = logging.getLogger("superstate_eval.extractor")


@dataclass
class EvaluationResult:
    """Outcome of blind verification and patch extraction."""

    task_id: str
    arm: str
    passed: bool
    reward: float | None
    exit_code: int
    patch_path: Path | None
    state_json_path: Path | None
    failure_reason: str | None = None


def extract_and_grade(
    container: Any,
    task: Any,
    arm: str,
    logs_dir: Path,
    workspace_path: Path | None = None,
) -> EvaluationResult:
    """Execute blind grading against the container and extract patches/telemetry.

    This function operates identically across Vanilla, Superpowers, and Superstate.
    It executes patch creation, runs the held-out verification command, and parses reward.json.
    """
    artifacts_dir = logs_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    patch_file = artifacts_dir / "model.patch"

    task_id = getattr(task, "id", None) or getattr(task, "task_id", "unknown_task")

    # 1. Commit unstaged changes in /app and extract diff against task base_commit
    base_commit = getattr(task, "base_commit", None)
    container.exec_run(
        'bash -c "'
        "git config --global --add safe.directory /app && "
        "git -C /app add -A && "
        "git -C /app -c user.name='Eval' -c user.email='eval@local' commit -m 'Auto-commit agent solution' || true"
        '"'
    )
    if base_commit:
        diff_cmd = f"git -C /app diff --binary {base_commit} HEAD > /logs/artifacts/model.patch || true"
    else:
        diff_cmd = (
            "BASE=$(git -C /app rev-list --max-parents=0 HEAD 2>/dev/null || echo 'HEAD~1') && "
            "git -C /app diff --binary $BASE HEAD > /logs/artifacts/model.patch || true"
        )
    container.exec_run(f'bash -c "mkdir -p /logs/artifacts && {diff_cmd}"')

    # 2. Run held-out verification command
    verification_cmd = getattr(task, "verification_cmd", None) or "pytest"
    exec_res = container.exec_run(verification_cmd)
    if isinstance(exec_res, tuple):
        exit_code, output = exec_res
    else:
        exit_code = getattr(exec_res, "exit_code", 1)
        output = getattr(exec_res, "output", b"")

    output_str = output.decode("utf-8", errors="replace") if isinstance(output, bytes) else str(output)

    # 3. Parse reward artifact from logs_dir / verifier / reward.json
    reward_json_path = logs_dir / "verifier" / "reward.json"
    reward: float | None = None
    if reward_json_path.is_file():
        try:
            data = json.loads(reward_json_path.read_text(encoding="utf-8"))
            if "reward" in data and data["reward"] is not None:
                reward = float(data["reward"])
        except Exception as err:
            logger.warning("Failed to parse %s: %s", reward_json_path, err)

    # 4. Strict evaluation gate:
    # PASS requires exit_code == 0 AND reward is defined AND reward >= 1.0.
    # Missing reward.json or exit_code != 0 counts as a failure.
    if exit_code == 0 and reward is not None and reward >= 1.0:
        passed = True
        failure_reason = None
    else:
        passed = False
        reasons: list[str] = []
        if exit_code != 0:
            reasons.append(f"Verification exit code {exit_code}")
        if reward is None:
            reasons.append("Missing or invalid verifier/reward.json")
        elif reward < 1.0:
            reasons.append(f"Reward was {reward} < 1.0")
        failure_reason = f"Verification failed: {', '.join(reasons)}\nOutput: {output_str[-500:]}"

    # 5. Archive state.json if present
    state_json_path: Path | None = None
    if workspace_path is not None:
        source_state = workspace_path / ".agent-state" / "state.json"
        if source_state.is_file():
            state_json_path = logs_dir / "state.json"
            shutil.copy2(source_state, state_json_path)

    actual_patch_path = patch_file if patch_file.is_file() else None

    logger.info(
        "Evaluation finished for task=%s arm=%s: passed=%s, reward=%s, exit_code=%s",
        task_id,
        arm,
        passed,
        reward,
        exit_code,
    )

    return EvaluationResult(
        task_id=task_id,
        arm=arm,
        passed=passed,
        reward=reward,
        exit_code=exit_code,
        patch_path=actual_patch_path,
        state_json_path=state_json_path,
        failure_reason=failure_reason,
    )
