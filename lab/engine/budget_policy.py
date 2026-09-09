"""Progress-earned budget policy and execution telemetry accounting.

Allows milestone-driven architectures to earn runtime runway upon
demonstrated progress, while maintaining transparent records of total
granted budget, actual wall-clock, cost, and tokens.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import logging
from typing import Any, Dict, List

logger = logging.getLogger("superstate_eval.budget_policy")


@dataclass
class BudgetPolicy:
    """Manages progress-earned execution timeouts."""

    base_timeout_sec: float
    lease_extension_sec: float = 1200.0
    max_lease_extensions: int = 5
    milestones_completed: int = 0
    extensions_granted_count: int = 0
    completed_milestone_titles: List[str] = field(default_factory=list)

    @property
    def lease_extensions_earned_sec(self) -> float:
        return self.extensions_granted_count * self.lease_extension_sec

    @property
    def current_granted_budget_sec(self) -> float:
        return self.base_timeout_sec + self.lease_extensions_earned_sec

    def record_milestone_progress(self, milestone_title: str) -> bool:
        """Record completed milestone and grant progress lease extension if within max limit."""
        self.milestones_completed += 1
        self.completed_milestone_titles.append(milestone_title)

        if self.extensions_granted_count < self.max_lease_extensions:
            self.extensions_granted_count += 1
            logger.info(
                f"Progress verified for '{milestone_title}': granted +{self.lease_extension_sec}s lease extension "
                f"(Total budget: {self.current_granted_budget_sec}s, completed milestones: {self.milestones_completed})"
            )
            return True

        logger.info(
            f"Progress verified for '{milestone_title}', but max lease extensions ({self.max_lease_extensions}) reached."
        )
        return False


@dataclass
class RunTelemetry:
    """Auditable execution telemetry across an evaluation unit."""

    task_id: str
    arm: str
    passed: bool
    wall_clock_sec: float
    cost_usd: float
    input_tokens: int
    output_tokens: int
    milestones_completed: int = 0
    lease_extensions_earned_sec: float = 0.0
    total_granted_budget_sec: float = 0.0
    failure_reason: str | None = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
