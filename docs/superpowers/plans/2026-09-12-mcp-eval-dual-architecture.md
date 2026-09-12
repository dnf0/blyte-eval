# MCP Evaluation Dual Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Choose an execution mode:
> 1. `superpowers:subagent-driven-development` (recommended for multi-agent reviews, backed by `SKILL.state` / `.agent-state/state.json`)
> 2. `agent-rules:stateful-execution` (SKILL.state) (recommended for deterministic single-agent linear execution)
> 3. `superpowers:executing-plans` (batch execution with manual checkpoints)
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the dual Model Context Protocol (MCP) evaluation architecture in `superstate-eval`, delivering both harness-level MCP orchestration (`superstate_mcp`) and agent-level autonomous MCP tool exposure (`superstate_agent_mcp`).

**Architecture:** A robust Python stdio JSON-RPC MCP client (`SuperstateMcpClient`) communicates with the release binary `superstate mcp` (protocol `2024-11-05`). The harness adapter (`SuperstateMcpAdapter`) uses this client for deterministic state management over stdio. The agent adapter (`SuperstateAgentMcpAdapter`) configures the driver (`ClaudeCliDriver`) with `--mcp-config` to expose all 25 `superstate` tools directly to the LLM agent under an autonomous execution contract.

**Tech Stack:** Python 3.12, stdio JSON-RPC 2.0, Model Context Protocol (MCP 2024-11-05), `pytest`, `pytest-mock`, `ruff`, `pyright`, Rust `superstate-mcp`.

## Global Constraints

- Python 3.12 syntax with strict type annotations (`from __future__ import annotations`).
- Standard MCP protocol: version `2024-11-05`, notifications sent without expecting response (`notifications/initialized`).
- Child process lifecycle: non-blocking stdio management, guaranteed termination and clean pipe closure on exit or timeout.
- Host configuration isolation: evaluation containers and drivers must never read or leak host operator config in `~/.gemini/config/mcp_config.json` or `~/.claude.json`.
- Zero regression on existing arms: `vanilla`, `superpowers`, `superstate_python`, and `superstate_rust` must continue passing 100% of tests.

---

### Task 1: `SuperstateMcpClient` Implementation & Protocol Handshake

- **Depends on:** none

**Files:**
- Create: `lab/engine/mcp/__init__.py`
- Create: `lab/engine/mcp/client.py`
- Test: `tests/test_superstate_mcp_client.py`

**Interfaces:**
- Produces: `class SuperstateMcpClient`
  ```python
  class SuperstateMcpClient:
      def __init__(self, superstate_bin: Optional[Path | str] = None, timeout: float = 30.0) -> None: ...
      def __enter__(self) -> "SuperstateMcpClient": ...
      def __exit__(self, exc_type, exc_val, exc_tb) -> None: ...
      def start(self) -> None: ...
      def stop(self) -> None: ...
      def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]: ...
      def state_init(self, plan: Path | str, repo: Path | str, no_worktree: bool = False, worktree: bool = False, goal: Optional[str] = None) -> bool: ...
      def state_prompt(self, repo: Path | str, with_graph: bool = False, task: Optional[str] = None, no_worktree: bool = False) -> str: ...
      def state_next(self, repo: Path | str, verify_cmd: Optional[str] = None, verify_git_clean: bool = False, ignore_untracked_glob: Optional[str] = None) -> bool: ...
      def state_status(self, repo: Path | str, json_format: bool = True) -> dict[str, Any]: ...
      def state_ready(self, repo: Path | str) -> list[str]: ...
      def state_doctor(self, repo: Path | str, repair: bool = False) -> dict[str, Any]: ...
      def state_exec(self, repo: Path | str, cmd: str, verify_cmd: Optional[str] = None, rollback_on_fail: bool = False, advance: bool = False) -> dict[str, Any]: ...
      def state_note(self, repo: Path | str, message: str) -> bool: ...
      def worktree_clean(self, repo: Path | str, force: bool = False) -> dict[str, Any]: ...
  ```

**Steps:**
- [ ] Write failing test in `tests/test_superstate_mcp_client.py`:
  - Test client handshake (`initialize`, `notifications/initialized`, `tools/list`).
  - Test tool execution (`state_status`, `state_prompt`).
  - Test error handling on missing tools and invalid arguments.
  - Test context manager clean child process termination.
- [ ] Run `pytest tests/test_superstate_mcp_client.py` to confirm failure.
- [ ] Implement `SuperstateMcpClient` in `lab/engine/mcp/client.py`.
- [ ] Run `pytest tests/test_superstate_mcp_client.py` to confirm all tests pass.
- [ ] Run `ruff check lab/engine/mcp tests/test_superstate_mcp_client.py`.
- [ ] Commit: `feat(mcp): implement SuperstateMcpClient for stdio JSON-RPC communication`.

---

### Task 2: Harness-Level Adapter (`SuperstateMcpAdapter`)

- **Depends on:** Task 1

**Files:**
- Create: `lab/engine/adapters/superstate_mcp.py`
- Test: `tests/test_superstate_mcp_adapter.py`

**Interfaces:**
- Consumes: `SuperstateMcpClient` from `lab/engine/mcp/client.py`
- Produces: `class SuperstateMcpAdapter(AgentAdapter)`
  ```python
  class SuperstateMcpAdapter(AgentAdapter):
      def __init__(
          self,
          superstate_bin: Optional[Path | str] = None,
          no_worktree: bool = True,
          worktree: bool = False,
          zero_turn_planning: bool = True,
      ) -> None: ...
      def execute(
          self,
          workspace_path: Path,
          task: TaskSpec,
          driver: AgentDriver,
          timeout_sec: Optional[float] = None,
          container: Any = None,
          budget_hook: Optional[BudgetHook] = None,
          recorder: Any = None,
      ) -> TaskRunResult: ...
  ```

**Steps:**
- [ ] Write failing test in `tests/test_superstate_mcp_adapter.py`:
  - Test milestone execution loop with `MockDriver` using `SuperstateMcpAdapter`.
  - Test gate execution inside container / host and `state_next` advancement.
  - Test provenance recording (`transport: "mcp_stdio"`).
  - Test cleanup on failure or completion (`worktree_clean`).
- [ ] Run `pytest tests/test_superstate_mcp_adapter.py` to confirm failure.
- [ ] Implement `SuperstateMcpAdapter` in `lab/engine/adapters/superstate_mcp.py`.
- [ ] Run `pytest tests/test_superstate_mcp_adapter.py` to confirm all tests pass.
- [ ] Run `ruff check lab/engine/adapters/superstate_mcp.py`.
- [ ] Commit: `feat(adapters): implement SuperstateMcpAdapter for harness-driven MCP state orchestration`.

---

### Task 3: Driver MCP Support & Agent-Level Autonomous Adapter

- **Depends on:** Task 1, Task 2

**Files:**
- Modify: `lab/engine/drivers/claude_cli.py`
- Create: `lab/engine/adapters/superstate_agent_mcp.py`
- Test: `tests/test_superstate_agent_mcp.py`
- Modify: `tests/test_claude_cli_driver.py`

**Interfaces:**
- Consumes: `SuperstateMcpClient` from `lab/engine/mcp/client.py`
- In `ClaudeCliDriver`: `superstate_mcp: bool = False` configuration flag.
- Produces: `class SuperstateAgentMcpAdapter(AgentAdapter)`
  ```python
  class SuperstateAgentMcpAdapter(AgentAdapter):
      def __init__(self, superstate_bin: Optional[Path | str] = None) -> None: ...
      def execute(
          self,
          workspace_path: Path,
          task: TaskSpec,
          driver: AgentDriver,
          timeout_sec: Optional[float] = None,
          container: Any = None,
          budget_hook: Optional[BudgetHook] = None,
          recorder: Any = None,
      ) -> TaskRunResult: ...
  ```

**Steps:**
- [ ] Write failing test in `tests/test_claude_cli_driver.py` asserting `superstate_mcp=True` injects `superstate` server into `--mcp-config`.
- [ ] Write failing test in `tests/test_superstate_agent_mcp.py` asserting agent-driven MCP execution contract and state completion verification.
- [ ] Update `lab/engine/drivers/claude_cli.py` to support `superstate_mcp`.
- [ ] Implement `SuperstateAgentMcpAdapter` in `lab/engine/adapters/superstate_agent_mcp.py`.
- [ ] Run `pytest tests/test_claude_cli_driver.py tests/test_superstate_agent_mcp.py` to verify passing.
- [ ] Run `ruff check lab/engine/drivers/claude_cli.py lab/engine/adapters/superstate_agent_mcp.py`.
- [ ] Commit: `feat(drivers): expose superstate MCP tools to agent runtime and implement SuperstateAgentMcpAdapter`.

---

### Task 4: Runner Integration & Benchmark Parity Verification

- **Depends on:** Task 2, Task 3

**Files:**
- Modify: `lab/engine/runner.py`
- Modify: `tests/test_adapters.py`
- Modify: `tests/test_runner.py`

**Interfaces:**
- In `AblationRunner._get_adapter(arm)`:
  - Supports `superstate_mcp`, `superstate_rust_mcp`, `superstate_mcp_worktree`, and `superstate_agent_mcp`.

**Steps:**
- [ ] Update `AblationRunner._get_adapter(arm)` in `lab/engine/runner.py` to resolve new arm strings.
- [ ] Add tests in `tests/test_adapters.py` and `tests/test_runner.py` verifying arm resolution and end-to-end execution.
- [ ] Run full test suite: `pytest -q`.
- [ ] Run linting and typing: `ruff check .` and `pyright lab tests`.
- [ ] Commit: `feat(runner): register superstate_mcp and superstate_agent_mcp evaluation arms`.
