# Architecture Specification: Antigravity CLI Driver (`AgyCliDriver`) & Container Execution Bridge

**Date:** 2026-09-09  
**Repository:** `superstate-eval`  
**Status:** Approved for Implementation  

---

## 1. Executive Summary & Context

To support evaluating Google Antigravity (`agy`) with `gemini-3.8-flash-high` across the three evaluation arms (Arm A: Vanilla, Arm B: Superpowers, Arm C: Superstate), this specification defines the `AgyCliDriver` and its container execution bridge.

Unlike Claude Code CLI, `agy`:
1. Has no ephemeral CLI flag for MCP registration (such as `--mcp-config`).
2. Does not support revoking core tools (such as `--disallowedTools Bash`).
3. Discovers MCP servers from the host user's `~/.gemini/config/mcp_config.json`, which contains the operator's personal GitHub, Notion, and Slack credentials.

To prevent mutating the host's configuration files, eliminate cross-worker race conditions, and avoid leaking operator credentials, `AgyCliDriver` employs a **workspace-level container execution bridge** (`./run-in-container`) coupled with native `run_command` invocation and prompt steering.

---

## 2. Core Objectives

1. **`AgentDriver` Parity:** Implement `AgyCliDriver` conforming to the `AgentDriver` ABC in `lab/engine/adapters/base.py`.
2. **First-Class Gemini 3.8 Flash Support:** Default to `gemini-3.8-flash-high` (or `--model gemini-3.8-flash --effort high`) with precise token accounting and cost computation.
3. **Hermetic Task Workspace Bridge:** Provide a zero-friction, container-scoped execution script (`./run-in-container`) within the mounted workspace root, routing project build and test commands directly into the task Docker sandbox.
4. **State Machine & Gate Integrity:**
   - Ensure Arm C verification gates remain independently evaluated by the harness via the Docker Python SDK (`container.exec_run(verify_cmd)`).
   - Ensure multi-turn state (`--conversation <conversation_id>`) is preserved across turn iterations in `TurnBasedAdapter` and `SuperstateAdapter`.
5. **Robust Telemetry Extraction:** Parse structured JSON from `agy --output-format json` into `DriverTelemetry` with duration, token counts, and conversation IDs.

---

## 3. Architecture & Driver Implementation

### 3.1 Class Definition (`lab/engine/drivers/agy_cli.py`)

```python
class AgyCliDriver(AgentDriver):
    """Driver executing agent sessions via the Antigravity CLI (agy)."""

    def __init__(
        self,
        model: str = "gemini-3.8-flash-high",
        cli_path: Optional[str] = None,
        extra_args: Optional[list[str]] = None,
        env: Optional[dict[str, str]] = None,
        container_exec: bool = True,
    ) -> None:
        ...
```

### 3.2 CLI Binary Resolution
1. Explicit `cli_path` argument if provided.
2. Direct check for `/Users/danielfisher/.local/bin/agy.real` (preferred over wrapper to prevent non-interactive stdin blocking).
3. Fallback to `shutil.which("agy")` or `shutil.which("agy.real")`.
4. Raise `AgyCliDriverError` if no valid executable is resolved.

### 3.3 Command Construction
For a given prompt turn:
```bash
agy.real \
  --model gemini-3.8-flash-high \
  --output-format json \
  --dangerously-skip-permissions \
  [--conversation <conversation_id>] \
  --print "<prompt>"
```
- Standard input is redirected from `/dev/null` (`stdin=subprocess.DEVNULL`) to ensure non-blocking execution.
- Working directory is set to `workspace_path`.

### 3.4 Telemetry & Pricing
Structured JSON output from `agy`:
```json
{
  "conversation_id": "...",
  "status": "SUCCESS",
  "response": "...",
  "duration_seconds": 12.34,
  "usage": {
    "input_tokens": 12000,
    "output_tokens": 850,
    "thinking_tokens": 512
  }
}
```
Pricing model for `gemini-3.8-flash` (standard benchmark tier):
- Input tokens: $0.15 / 1M tokens ($0.00000015 / token).
- Output tokens: $0.60 / 1M tokens ($0.00000060 / token).
- Thinking tokens are billed as output tokens.

---

## 4. Container Execution Bridge (`./run-in-container`)

When executing against an active sandbox (`container is not None`):
1. **Bridge Script Generation:** The driver writes an executable script at `workspace_path / "run-in-container"`:
   ```bash
   #!/usr/bin/env bash
   exec docker exec -i {container_name_or_id} "$@"
   ```
2. **Permissions:** Set permissions to `0o755`.
3. **Prompt Steering:** Prepend or append container guidance:
   ```markdown
   ## Environment & Execution Contract
   The project dependencies and runtime environment are inside the Docker container.
   To run commands, tests, or builds, use:
     `./run-in-container <command>`
   Example: `./run-in-container pytest tests/`
   ```

### Benefits:
- **Zero Config Mutation:** Host `~/.gemini/config/mcp_config.json` is never modified.
- **Operator Isolation:** Personal Slack/GitHub/Notion credentials are never exposed or invoked.
- **Full Concurrency:** Each task workspace has its own script closed over its specific container ID.
- **Native Tooling:** Uses `agy`'s native, fastest `run_command` tool.

---

## 5. Verification & Testing Strategy

1. **Unit Tests (`tests/test_agy_cli_driver.py`):**
   - Executable path resolution and validation.
   - Argument building (`--model`, `--conversation`, `--dangerously-skip-permissions`).
   - Output parsing (success, error, malformed JSON).
   - Container bridge creation and executable permissions.
   - Timeout and process termination handling.
2. **Lint & Type Checks:**
   - `uv run ruff check lab tests`
   - `uv run pyright lab tests`
   - `uv run pytest -q`
3. **Live Smoke Run:**
   - Execute a single task (`fastapi-deprecation-response-headers`) using `AblationRunner` with `AgyCliDriver`.
