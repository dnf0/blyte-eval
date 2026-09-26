"""Arm adapters for Vanilla and Superpowers execution."""

from lab.engine.adapters.base import AgentAdapter, AgentDriver, DriverTelemetry, TaskRunResult
from lab.engine.adapters.superpowers import SuperpowersAdapter
from lab.engine.adapters.vanilla import VanillaAdapter

__all__ = [
    "AgentAdapter",
    "AgentDriver",
    "DriverTelemetry",
    "SuperpowersAdapter",
    "TaskRunResult",
    "VanillaAdapter",
]
