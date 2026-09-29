"""Run trace capture: the diagnostic record an evaluation leaves behind.

Pass/fail and cost tell you *that* an arm underperformed. Improving the state
engine needs the material that explains *why*: what the agent was actually asked,
what it said back, which milestone stalled, which verification gate rejected the
work and what it printed. This module persists that alongside each run.

Layout under a run's logs directory:

    run.json            headline telemetry, provenance and the sandbox contract
    transcript.jsonl    one record per driver turn (prompt, response, telemetry)
    milestones.jsonl    one record per milestone (Arm C): gate command and verdict
    verifier_output.txt full held-out verifier output, untruncated
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("blyte_eval.trace")

# Generous per-field cap: enough to diagnose a stall, small enough that a
# pathological agent cannot fill the disk.
MAX_TEXT_CHARS = 40_000


def _clip(text: str | None) -> str | None:
    """Truncate a captured field, saying so explicitly rather than silently."""
    if text is None:
        return None
    if len(text) <= MAX_TEXT_CHARS:
        return text
    dropped = len(text) - MAX_TEXT_CHARS
    return text[:MAX_TEXT_CHARS] + f"\n...[truncated {dropped} chars]"


@dataclass
class TurnRecord:
    """A single driver invocation, with both sides of the exchange."""

    turn: int
    phase: str
    prompt: Optional[str]
    response: Optional[str]
    success: bool
    duration_seconds: float
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    milestone: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class MilestoneRecord:
    """A milestone attempt and the verdict of its verification gate."""

    index: int
    title: str
    verify_cmd: Optional[str]
    turns_used: int
    gate_ran: bool
    gate_passed: Optional[bool]
    gate_exit_code: Optional[int] = None
    gate_output: Optional[str] = None
    advanced: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)


class RunRecorder:
    """Writes the per-run diagnostic trace. Never raises into the evaluation."""

    def __init__(self, logs_dir: Path | str, task_id: str, arm: str) -> None:
        self.logs_dir = Path(logs_dir)
        self.task_id = task_id
        self.arm = arm
        self.turns: list[TurnRecord] = []
        self.milestones: list[MilestoneRecord] = []
        try:
            self.logs_dir.mkdir(parents=True, exist_ok=True)
        except OSError as err:  # pragma: no cover - defensive
            logger.warning("Could not create trace directory %s: %s", self.logs_dir, err)

    def _append_jsonl(self, filename: str, payload: Dict[str, Any]) -> None:
        try:
            with (self.logs_dir / filename).open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, default=str) + "\n")
        except OSError as err:
            logger.warning("Failed to write %s: %s", filename, err)

    def record_turn(
        self,
        phase: str,
        prompt: Optional[str],
        telemetry: Any,
        milestone: Optional[str] = None,
    ) -> None:
        """Capture one driver turn, including the prompt that produced it."""
        record = TurnRecord(
            turn=len(self.turns) + 1,
            phase=phase,
            prompt=_clip(prompt),
            response=_clip(getattr(telemetry, "raw_response", None)),
            success=bool(getattr(telemetry, "success", False)),
            duration_seconds=float(getattr(telemetry, "duration_seconds", 0.0)),
            input_tokens=int(getattr(telemetry, "input_tokens", 0)),
            output_tokens=int(getattr(telemetry, "output_tokens", 0)),
            cost_usd=float(getattr(telemetry, "cost_usd", 0.0)),
            milestone=milestone,
            error_message=getattr(telemetry, "error_message", None),
        )
        self.turns.append(record)
        self._append_jsonl("transcript.jsonl", asdict(record))

    def record_milestone(self, record: MilestoneRecord) -> None:
        """Capture a milestone attempt and its gate verdict."""
        record.gate_output = _clip(record.gate_output)
        self.milestones.append(record)
        self._append_jsonl("milestones.jsonl", asdict(record))

    def record_verifier_output(self, output: str) -> None:
        """Persist the full held-out verifier output, untruncated."""
        try:
            (self.logs_dir / "verifier_output.txt").write_text(output, encoding="utf-8")
        except OSError as err:
            logger.warning("Failed to write verifier output: %s", err)

    def write_run_record(self, telemetry: Any, **context: Any) -> Optional[Path]:
        """Write the headline run record. Returns the path written, if any."""
        payload: Dict[str, Any] = {
            "task_id": self.task_id,
            "arm": self.arm,
            "telemetry": (
                asdict(telemetry)
                if is_dataclass(telemetry) and not isinstance(telemetry, type)
                else telemetry
            ),
            "turn_count": len(self.turns),
            "milestone_count": len(self.milestones),
            "gates_failed": [
                m.title for m in self.milestones if m.gate_ran and m.gate_passed is False
            ],
            **context,
        }
        path = self.logs_dir / "run.json"
        try:
            path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
            return path
        except OSError as err:
            logger.warning("Failed to write run record: %s", err)
            return None
