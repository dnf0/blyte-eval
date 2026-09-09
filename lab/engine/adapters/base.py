"""Base interfaces and data structures for execution adapters and agent drivers."""

from __future__ import annotations

import abc
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from lab.benchmarks.task_loader import TaskSpec


@dataclass
class DriverTelemetry:
    """Outcome and telemetry metrics from a single driver invocation turn."""

    success: bool
    raw_response: str
    duration_seconds: float
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    conversation_id: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class TaskRunResult:
    """Outcome and telemetry metrics for a complete task execution run."""

    task_id: str
    harness_name: str
    success: bool
    duration_seconds: float
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    error_message: Optional[str] = None
    turns: int = 0
    reward: Optional[float] = None


class AgentDriver(abc.ABC):
    """Abstract driver interface communicating with an underlying agent runtime."""

    @abc.abstractmethod
    def run(
        self,
        task: TaskSpec,
        workspace_path: Path,
        prompt_override: Optional[str] = None,
        conversation_id: Optional[str] = None,
        timeout_sec: float = 3600.0,
    ) -> DriverTelemetry:
        """Run an agent session or turn within the target workspace."""


class AgentAdapter(abc.ABC):
    """Abstract evaluation adapter configuring workspace guidance and managing turns."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Name of the evaluation arm."""

    @abc.abstractmethod
    def execute(
        self,
        workspace_path: Path,
        task: TaskSpec,
        driver: AgentDriver,
        timeout_sec: Optional[float] = None,
    ) -> TaskRunResult:
        """Execute a task in the given workspace using the provided driver."""
