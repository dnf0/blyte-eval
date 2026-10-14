"""Pair driver for blyte: orchestrator dispatches implementers into the same task container."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Optional
import uuid

from lab.benchmarks.task_loader import TaskSpec
from lab.engine.adapters.base import DriverTelemetry
from lab.engine.drivers.agy_cli import estimate_cost_usd
from lab.engine.drivers.blyte_native import (
    CONTAINER_WORKDIR,
    KILL_GRACE_SEC,
    BlyteNativeDriver,
    _read_report,
    _tail,
    _text,
    run_metrics,
)

logger = logging.getLogger("blyte_eval.drivers.blyte_pair")
REPO_ROOT = Path(__file__).resolve().parents[3]


def _natural_sort_key(path: Path) -> tuple[int, str]:
    m = re.search(r"(\d+)", path.stem)
    return (int(m.group(1)) if m else 0, path.name)


def _aggregate_dispatches(dispatch_dir: Optional[Path]) -> tuple[float, int, list[str], float]:
    """Sum cost, wall-clock seconds, count dispatches and collect outcomes from dispatch reports."""
    if dispatch_dir is None or not dispatch_dir.is_dir():
        return 0.0, 0, [], 0.0
    cost = 0.0
    wall_clock = 0.0
    outcomes: list[str] = []
    report_files = sorted(dispatch_dir.glob("*.json"), key=_natural_sort_key)
    for rf in report_files:
        try:
            data = json.loads(rf.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cost += float(data.get("cost_usd", 0.0) or 0.0)
                sec = data.get("wall_clock_secs")
                if sec is None:
                    sec = data.get("seconds")
                if sec is None:
                    sec = data.get("duration_seconds")
                if sec is not None:
                    wall_clock += float(sec)
                if "outcome" in data and data["outcome"] is not None:
                    outcomes.append(str(data["outcome"]))
        except (json.JSONDecodeError, OSError):
            pass
    return cost, len(report_files), outcomes, wall_clock


class BlytePairDriver(BlyteNativeDriver):
    """Drives blyte as an orchestrator that dispatches implementers into the task container."""

    harness_name: str = "blyte+blyte"

    def __init__(
        self,
        model: str,
        implementer_model: str,
        blyte_bin: Optional[str | Path] = None,
        report_dir: Optional[str | Path] = None,
        dispatch_dir: Optional[Path] = None,
        dispatch_cmd: Optional[str] = None,
    ) -> None:
        super().__init__(
            model=model,
            context="folded",
            fold_budget=None,
            blyte_bin=blyte_bin,
            report_dir=report_dir,
        )
        self.implementer_model = implementer_model
        self.harness_name = f"blyte+blyte[{implementer_model}]"
        self.dispatch_dir = Path(dispatch_dir) if dispatch_dir is not None else None
        self.dispatch_cmd = (
            dispatch_cmd
            or f"{sys.executable} -m lab.engine.drivers.dispatch_hook"
        )
        self.last_dispatch_dir: Optional[Path] = None

    def build_command(
        self, prompt: str, container_id: str, report_path: Path, timeout_sec: float
    ) -> list[str]:
        """The argv for one task. Never a --gate: runs are ungated, and the sealed grader decides."""
        return [
            str(self.blyte_bin),
            "--orchestrate",
            "--model",
            self.model,
            "--container",
            container_id,
            "--container-workdir",
            CONTAINER_WORKDIR,
            "--max-seconds",
            str(max(1, int(timeout_sec))),
            "--report",
            str(report_path),
            "--dispatch-cmd",
            self.dispatch_cmd,
            "--",
            prompt,
        ]

    def run(
        self,
        task: TaskSpec,
        workspace_path: Path,
        prompt_override: Optional[str] = None,
        conversation_id: Optional[str] = None,
        timeout_sec: float = 3600.0,
        container: Any = None,
    ) -> DriverTelemetry:
        start = time.monotonic()
        if container is None:
            return DriverTelemetry(
                success=False,
                raw_response="",
                duration_seconds=0.0,
                error_message=(
                    "blyte native driver requires a sandbox container; "
                    "refusing to run on the host"
                ),
            )
        container_id = str(
            getattr(container, "id", None) or getattr(container, "name", None) or container
        )
        prompt = prompt_override or task.instruction
        report_path = self._work_dir / f"report-{uuid.uuid4().hex}.json"
        cmd = self.build_command(prompt, container_id, report_path, timeout_sec)

        if self.dispatch_dir is not None:
            run_dispatch_dir = self.dispatch_dir
        elif self.report_dir is not None:
            task_name = getattr(task, "name", "task")
            run_dispatch_dir = self.report_dir / f"dispatches-{task_name}-{uuid.uuid4().hex[:8]}"
        else:
            task_name = getattr(task, "name", "task")
            run_dispatch_dir = Path(tempfile.mkdtemp(prefix=f"blyte-dispatches-{task_name}-"))
        run_dispatch_dir.mkdir(parents=True, exist_ok=True)
        self.last_dispatch_dir = run_dispatch_dir

        run_env = dict(os.environ)
        run_env.update(task.env or {})
        run_env["BLYTE_EVAL_CONTAINER"] = container_id
        run_env["BLYTE_IMPLEMENTER_MODEL"] = self.implementer_model
        run_env["BLYTE_DISPATCH_DIR"] = str(run_dispatch_dir)
        run_env["BLYTE_BIN"] = str(self.blyte_bin)
        repo_root_str = str(REPO_ROOT)
        existing_pythonpath = run_env.get("PYTHONPATH", "")
        run_env["PYTHONPATH"] = (
            f"{repo_root_str}:{existing_pythonpath}" if existing_pythonpath else repo_root_str
        )

        killed = False
        returncode: Optional[int] = None
        stdout: Optional[str | bytes] = None
        stderr: Optional[str | bytes] = None
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(workspace_path),
                capture_output=True,
                text=True,
                timeout=timeout_sec + KILL_GRACE_SEC,
                check=False,
                env=run_env,
            )
            returncode, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired as exc:
            killed, stdout, stderr = True, exc.stdout, exc.stderr
        elapsed = time.monotonic() - start

        self.last_events_path = None
        if self.report_dir is not None:
            self.report_dir.mkdir(parents=True, exist_ok=True)
            events_path = self.report_dir / f"{task.name}-{report_path.stem}.events.log"
            events_path.write_text(
                _text(stdout) + "\n--- stderr ---\n" + _text(stderr), encoding="utf-8"
            )
            self.last_events_path = events_path

        report = _read_report(report_path)
        self.last_report = report
        if report is None:
            reason = (
                f"blyte killed after {elapsed:.0f}s with no report"
                if killed
                else f"blyte exited {returncode} with no report"
            )
            implementer_cost, dispatches, outcomes, wall_clock = _aggregate_dispatches(
                run_dispatch_dir
            )
            metrics = {
                "frontier_cost_usd": 0.0,
                "implementer_cost_usd": implementer_cost,
                "dispatches": dispatches,
                "dispatch_outcomes": outcomes,
                "implementer_wall_clock_secs": wall_clock,
            }
            telem = DriverTelemetry(
                success=False,
                raw_response="",
                duration_seconds=elapsed,
                cost_usd=implementer_cost,
                error_message=f"{reason}: {_tail(stderr)}",
                metrics=metrics,
            )
            telem.extra = metrics  # type: ignore[attr-defined]
            return telem

        if self.report_dir is not None:
            self.report_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(report_path, self.report_dir / f"{task.name}-{report_path.name}")

        usage = report.get("usage") or {}
        input_tokens = int(usage.get("input", 0))
        output_tokens = int(usage.get("output", 0))
        cached_input_tokens = int(usage.get("cached", 0))
        thinking_tokens = int(usage.get("thinking", 0))

        frontier_cost = report.get("cost_usd")
        if frontier_cost is not None and isinstance(frontier_cost, (int, float)):
            frontier_cost_usd = float(frontier_cost)
        else:
            frontier_cost_usd = estimate_cost_usd(
                self.model, input_tokens, output_tokens, cached_input_tokens, thinking_tokens
            )

        implementer_cost_usd, dispatches, dispatch_outcomes, implementer_wall_clock_secs = (
            _aggregate_dispatches(run_dispatch_dir)
        )
        total_cost_usd = frontier_cost_usd + implementer_cost_usd

        metrics = run_metrics(report, _text(stdout))
        metrics.update(
            {
                "frontier_cost_usd": frontier_cost_usd,
                "implementer_cost_usd": implementer_cost_usd,
                "dispatches": dispatches,
                "dispatch_outcomes": dispatch_outcomes,
                "implementer_wall_clock_secs": implementer_wall_clock_secs,
            }
        )
        if metrics.get("harness_turns"):
            metrics["cost_per_turn"] = round(total_cost_usd / metrics["harness_turns"], 6)

        outcome = report.get("outcome")
        is_error = killed or returncode != 0 or outcome == "error" or bool(report.get("error"))
        success = not is_error
        error_message = None
        if not success:
            error_message = report.get("error") or f"blyte outcome: {outcome}"

        telem = DriverTelemetry(
            success=success,
            raw_response=str(report.get("final_message") or ""),
            duration_seconds=elapsed,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_input_tokens,
            thinking_tokens=thinking_tokens,
            cost_usd=total_cost_usd,
            conversation_id=None,
            error_message=error_message,
            metrics=metrics,
        )
        telem.extra = metrics  # type: ignore[attr-defined]
        return telem
