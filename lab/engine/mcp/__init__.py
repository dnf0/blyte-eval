"""Model Context Protocol (MCP) engine package.

Provides stdio JSON-RPC MCP clients for superstate integration.
"""

from __future__ import annotations

from lab.engine.mcp.client import (
    McpError,
    McpProcessError,
    McpRpcError,
    McpTimeoutError,
    SuperstateMcpClient,
)

__all__ = [
    "McpError",
    "McpProcessError",
    "McpRpcError",
    "McpTimeoutError",
    "SuperstateMcpClient",
]
