"""Arm adapters for Vanilla, Superpowers, and Superstate execution."""

from lab.engine.adapters.base import AgentAdapter, AgentDriver, DriverTelemetry, TaskRunResult
from lab.engine.adapters.superpowers import SuperpowersAdapter
from lab.engine.adapters.superstate import SuperstateAdapter
from lab.engine.adapters.superstate_agent_mcp import SuperstateAgentMcpAdapter
from lab.engine.adapters.superstate_mcp import SuperstateMcpAdapter
from lab.engine.adapters.vanilla import VanillaAdapter

__all__ = [
    "AgentAdapter",
    "AgentDriver",
    "DriverTelemetry",
    "SuperpowersAdapter",
    "SuperstateAdapter",
    "SuperstateAgentMcpAdapter",
    "SuperstateMcpAdapter",
    "TaskRunResult",
    "VanillaAdapter",
]
