"""Blind patch extraction and held-out verifier scoring.

Executes uniformly across Vanilla, Superpowers, and Superstate arms.
Extracts git diff patches against the task base commit and grades
using the held-out verification command and verifier/reward.json.
"""

from __future__ import annotations

from dataclasses import dataclass
import io
import json
import logging
from pathlib import Path
import shutil
import tarfile
from typing import Any

logger = logging.getLogger("superstate_eval.extractor")

# Files the harness itself writes into the workspace. They differ by arm
# (Superpowers installs AGENTS.md and a skills library, Superstate writes plan.md
# and .agent-state), so leaving them in the diff makes the archived patch an
# arm-dependent artifact rather than a comparable record of the agent's work.
HARNESS_ARTIFACTS = (
    "AGENTS.md",
    "GEMINI.md",
    "CLAUDE.md",
    ".cursorrules",
    ".windsurfrules",
    ".agents/",
    "plan.md",
    ".agent-state/",
    # Bridge script the agy driver writes so the agent can reach the container.
    # It is harness scaffolding, and the task verifiers record an out-of-scope
    # signal for files outside the expected fix scope.
    "run-in-container",
)


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
    stats: dict[str, Any] | None = None


def compute_test_metrics(stats: dict[str, Any] | None, passed: bool) -> dict[str, Any]:
    """Compute normalized test pass fractions and counts from verifier statistics.

    Extracts granular Fail-to-Pass (F2P) and Pass-to-Pass (P2P) statistics when
    available, falling back to top-level pass/fail status when test telemetry is absent.

    Parameters:
        stats: Raw dictionary of verifier output metrics (e.g. from reward.json), or None.
        passed: Boolean indicating whether evaluation strictly passed.

    Returns:
        Dictionary containing:
            - test_pass_fraction: Float in [0.0, 1.0] representing overall test passing fraction.
            - f2p_fraction: Float in [0.0, 1.0] or None if F2P tests are absent.
            - p2p_fraction: Float in [0.0, 1.0] or None if P2P tests are absent.
            - tests_passed: Total integer count of passed tests or None if absent.
            - tests_total: Total integer count of executed tests or None if absent.
    """
    if stats is None:
        # Fallback when no granular test statistics exist in reward.json.
        return {
            "test_pass_fraction": 1.0 if passed else 0.0,
            "f2p_fraction": None,
            "p2p_fraction": None,
            "tests_passed": None,
            "tests_total": None,
        }

    # Check for CTRF / SWE-bench f2p and p2p metrics in the statistics dictionary.
    has_f2p = stats.get("f2p_total") is not None
    has_p2p = stats.get("p2p_total") is not None

    if has_f2p or has_p2p:
        f2p_total = int(stats.get("f2p_total") or 0)
        f2p_passed = int(stats.get("f2p_passed") or 0)
        p2p_total = int(stats.get("p2p_total") or 0)
        p2p_passed = int(stats.get("p2p_passed") or 0)

        # Calculate suite fractions, returning None when no tests were present in that suite.
        f2p_fraction = (f2p_passed / f2p_total) if f2p_total > 0 else None
        p2p_fraction = (p2p_passed / p2p_total) if p2p_total > 0 else None

        # Aggregate total test counts across fail-to-pass and pass-to-pass suites.
        tests_passed = f2p_passed + p2p_passed
        tests_total = f2p_total + p2p_total

        # Guard against division by zero when both suites are empty.
        if tests_total > 0:
            test_pass_fraction = tests_passed / tests_total
        else:
            test_pass_fraction = 1.0 if passed else 0.0

        return {
            "test_pass_fraction": test_pass_fraction,
            "f2p_fraction": f2p_fraction,
            "p2p_fraction": p2p_fraction,
            "tests_passed": tests_passed,
            "tests_total": tests_total,
        }

    # Check for generic test counters if f2p/p2p are not provided.
    if stats.get("tests_total") is not None:
        tests_total = int(stats.get("tests_total") or 0)
        tests_passed = int(stats.get("tests_passed") or 0)
        test_pass_fraction = (tests_passed / tests_total) if tests_total > 0 else (1.0 if passed else 0.0)
        return {
            "test_pass_fraction": test_pass_fraction,
            "f2p_fraction": None,
            "p2p_fraction": None,
            "tests_passed": tests_passed,
            "tests_total": tests_total,
        }

    # Fallback when stats dictionary contains neither f2p/p2p nor tests_total counters.
    return {
        "test_pass_fraction": 1.0 if passed else 0.0,
        "f2p_fraction": None,
        "p2p_fraction": None,
        "tests_passed": None,
        "tests_total": None,
    }


def _extract_blind_patch(
    container: Any,
    task: Any,
    logs_dir: Path,
    workspace_path: Path | None = None,
) -> Path | None:
    """Extract patch by committing workspace changes and running task collection commands."""
    artifacts_dir = logs_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    patch_file = artifacts_dir / "model.patch"

    # 1. Keep harness scaffolding out of the graded artifact, then commit the
    #    agent's work in /app and extract the diff against the task base commit.
    exclusions = " ".join(HARNESS_ARTIFACTS)
    container.exec_run(
        'bash -c "'
        "mkdir -p /app/.git/info && "
        f"printf '%s\n' {exclusions} >> /app/.git/info/exclude"
        '"'
    )
    base_commit = getattr(task, "base_commit", None)
    container.exec_run(
        'bash -c "'
        "git config --global --add safe.directory /app && "
        "git -C /app add -A && "
        "git -C /app -c user.name='Eval' -c user.email='eval@local' commit -m 'Auto-commit agent solution' || true"
        '"'
    )

    # Prefer the task's own collect command: it is the benchmark's definition of
    # how a patch is produced, and diverging from it makes our artifact non-comparable.
    collect_commands = list(getattr(task, "collect_commands", None) or [])
    if collect_commands:
        for collect_cmd in collect_commands:
            container.exec_run(f'bash -c "{collect_cmd}"')
    elif base_commit:
        diff_cmd = f"git -C /app diff --binary {base_commit} HEAD > /logs/artifacts/model.patch || true"
        container.exec_run(f'bash -c "mkdir -p /logs/artifacts && {diff_cmd}"')

    return patch_file if patch_file.is_file() else None


def _inject_tests_to_container(container: Any, tests_dir: Path) -> None:
    """Inject tests directory into container at /tests using AnswerKeyGuard."""
    from lab.sandbox.answer_key import AnswerKeyGuard

    guard = AnswerKeyGuard()
    with guard.temporarily_readable(tests_dir) as readable_tests:
        bio = io.BytesIO()
        with tarfile.open(fileobj=bio, mode="w") as tar:
            tar.add(str(readable_tests), arcname="tests")
        bio.seek(0)
        container.put_archive("/", bio.read())


def extract_and_grade(
    container: Any,
    task: Any,
    arm: str,
    logs_dir: Path,
    workspace_path: Path | None = None,
    recorder: Any | None = None,
    verifier: Any | None = None,
) -> EvaluationResult:
    """Extract patch, run verification, and record structured evaluation artifacts."""
    task_id = getattr(task, "id", None) or getattr(task, "task_id", "unknown_task")

    # 1. Blind patch extraction: identical mechanics across all arms.
    patch_path: Path | None = None
    base_commit = getattr(task, "base_commit", None)
    if base_commit:
        patch_path = _extract_blind_patch(
            container=container,
            task=task,
            logs_dir=logs_dir,
            workspace_path=workspace_path,
        )
    else:
        logger.warning(
            "Task %s has no base_commit; skipping patch extraction for arm %s "
            "(set metadata.base_commit_hash in task.toml to capture patches).",
            task_id,
            arm,
        )

    # 2. Grade. The task's own verifier image is authoritative when it exists:
    #    it applies model.patch to a pristine /app in a separate container, so the
    #    agent cannot influence its own grade by editing tests or the workspace.
    verifier_reward: float | None = None
    verifier_stats: dict[str, Any] | None = None
    verifier_ran_held_out = False

    tests_dir = getattr(task, "tests_dir", None)
    is_in_container = getattr(task, "has_verifier_dockerfile", None) is False

    # DeepSWE tasks ship tests/Dockerfile and are graded in a held-out verifier container.
    # Terminal-bench tasks have has_verifier_dockerfile=False and are graded in-container
    # by injecting the held-out tests/ directory into /tests at evaluation time.
    if verifier is not None and tests_dir is not None and not is_in_container:
        try:
            outcome = verifier.run(task=task, logs_dir=logs_dir)
            exit_code = outcome.exit_code
            output_str = outcome.output
            verifier_reward = outcome.reward
            verifier_stats = outcome.stats
            verifier_ran_held_out = True
            if outcome.crashed:
                logger.error("Held-out verifier crashed for %s; grading as failure", task_id)
        except Exception as err:
            logger.error("Held-out verifier failed for %s: %s", task_id, err)
            exit_code = 1
            output_str = f"Held-out verifier could not run: {err}"
    else:
        if tests_dir is not None and getattr(tests_dir, "is_dir", lambda: False)() and hasattr(container, "put_archive"):
            try:
                _inject_tests_to_container(container, tests_dir)
            except Exception as err:
                logger.warning("Failed to inject tests into container for %s: %s", task_id, err)
        elif tests_dir is None:
            logger.warning(
                "Task %s ships no tests directory; falling back to running the "
                "verification command inside the agent's own container without injected tests.",
                task_id,
            )

        verification_cmd = getattr(task, "verification_cmd", None) or "pytest"
        env_env = getattr(task, "env", None) or {}
        verifier_env = getattr(task, "verifier_env", None) or {}
        combined_env = {**env_env, **verifier_env}
        exec_kwargs: dict[str, Any] = {}
        if combined_env:
            exec_kwargs["environment"] = combined_env

        exec_res = container.exec_run(verification_cmd, workdir="/app", **exec_kwargs)
        if isinstance(exec_res, tuple):
            exit_code, output = exec_res
        else:
            exit_code = getattr(exec_res, "exit_code", 1)
            output = getattr(exec_res, "output", b"")
        output_str = (
            output.decode("utf-8", errors="replace") if isinstance(output, bytes) else str(output)
        )

    # Persist the verifier's full output: the tail alone rarely explains a failure.
    if recorder is not None:
        recorder.record_verifier_output(output_str)

    # 3. Reward and stats: from the held-out verifier when it ran, else from reward.json or reward.txt.
    # Preserve full verifier metadata to enable granular test fraction computations.
    reward: float | None = verifier_reward
    stats: dict[str, Any] | None = verifier_stats
    if not verifier_ran_held_out:
        verifier_dir = logs_dir / "verifier"
        reward_json_path = verifier_dir / "reward.json"
        reward_txt_path = verifier_dir / "reward.txt"
        ctrf_json_path = verifier_dir / "ctrf.json"

        if reward_json_path.is_file():
            try:
                data = json.loads(reward_json_path.read_text(encoding="utf-8"))
                stats = data
                if "reward" in data and data["reward"] is not None:
                    reward = float(data["reward"])
            except Exception as err:
                logger.warning("Failed to parse %s: %s", reward_json_path, err)
        elif reward_txt_path.is_file():
            try:
                val = float(reward_txt_path.read_text(encoding="utf-8").strip())
                reward = None if val < 0 else val
            except Exception as err:
                logger.warning("Failed to parse %s: %s", reward_txt_path, err)

        # Ingest CTRF summary metrics if stats dictionary is still missing or lacking test counts
        if ctrf_json_path.is_file() and (stats is None or "tests_total" not in stats):
            try:
                ctrf_data = json.loads(ctrf_json_path.read_text(encoding="utf-8"))
                summary = ctrf_data.get("results", {}).get("summary", {})
                t_total = summary.get("tests")
                t_passed = summary.get("passed")
                if t_total is not None and isinstance(t_total, int):
                    stats = {
                        **(stats or {}),
                        "tests_total": t_total,
                        "tests_passed": int(t_passed or 0),
                    }
            except Exception as err:
                logger.warning("Failed to parse %s: %s", ctrf_json_path, err)

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
            reasons.append("Missing or invalid verifier/reward.json or reward.txt")
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

    actual_patch_path = patch_path if (patch_path and patch_path.is_file()) else None

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
        stats=stats,
    )

