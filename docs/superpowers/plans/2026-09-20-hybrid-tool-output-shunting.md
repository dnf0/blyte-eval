# Hybrid Tool Output Shunting & Distillation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Choose an execution mode:
> 1. `superpowers:subagent-driven-development` (recommended for multi-agent reviews, backed by `SKILL.state` / `.agent-state/state.json`)
> 2. `agent-rules:stateful-execution` (SKILL.state) (recommended for deterministic single-agent linear execution)
> 3. `superpowers:executing-plans` (batch execution with manual checkpoints)
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement hybrid tool output shunting and distillation across host container bridge and in-container execution, cutting LLM context exhaustion on long compilation, build, and test runs while strictly preserving failure signals and exit codes.

**Architecture:** Route all `./run-in-container` executions through `superstate shunt` on the host when enabled, and optionally bind-mount a statically-linked Linux `superstate` binary into `/usr/local/bin/superstate` inside sandbox containers. The shunting engine distills outputs exceeding 50 lines / 4 KB, persists full logs to `.agent-state/logs/`, and provides compact high-signal summaries to the LLM context.

**Tech Stack:** Python 3.12 (`pytest`, `docker-py`), Rust 2021 (`superstate-cli`, `superstate-core`, `tokio`).

## Global Constraints
- Target repositories: `dnfcx/superstate-eval` and `repos/superstate`.
- Strict Test-Driven Development (TDD): write failing tests first, verify RED, implement minimal code, verify GREEN.
- All Python code must pass `ruff check` and `pyright`.
- All Rust code must pass `cargo check --all`, `cargo test --all`, and `cargo clippy -- -D warnings`.
- Conventional Commits with `--no-gpg-sign`.
- Strict Referee Rule: zero harness-level prompt engineering, zero synthetic milestone scaffolding; baseline arms (`vanilla`) remain untouched.

---

### Task 1: Container Bridge Output Shunting (`lab/engine/drivers/agy_cli.py`)

- **Depends on:** none

**Files:**
- Create: `tests/test_container_bridge.py`
- Modify: `lab/engine/drivers/agy_cli.py:144-156`

**Interfaces:**
- Consumes: `_setup_container_bridge(workspace_path: Path, container: Any) -> None`
- Produces: Enhanced `./run-in-container` shell script with `superstate shunt` support and clean fallback.

- [ ] **Step 1: Write the failing unit tests in `tests/test_container_bridge.py`**

```python
"""Tests for container bridge script generation and shunting execution."""

import os
from pathlib import Path
import stat
import subprocess
from unittest.mock import MagicMock

from lab.engine.drivers.agy_cli import AgyCliDriver


def test_setup_container_bridge_generates_shunting_script(tmp_path: Path) -> None:
    """Verify ./run-in-container includes superstate shunt invocation when enabled."""
    driver = AgyCliDriver(cli_path="/bin/echo")
    container = MagicMock()
    container.id = "test-container-123"

    driver._setup_container_bridge(tmp_path, container)

    bridge_script = tmp_path / "run-in-container"
    assert bridge_script.is_file()
    content = bridge_script.read_text(encoding="utf-8")

    assert "superstate shunt" in content
    assert "docker exec -i -w /app test-container-123" in content
    # Verify executable bit is set
    mode = bridge_script.stat().st_mode
    assert bool(mode & stat.S_IXUSR)


def test_container_bridge_preserves_exit_code_and_fallback(tmp_path: Path) -> None:
    """Verify fallback when superstate is absent executes underlying command and preserves exit code."""
    driver = AgyCliDriver(cli_path="/bin/echo")
    container = MagicMock()
    container.id = "dummy-id"

    driver._setup_container_bridge(tmp_path, container)

    bridge_script = tmp_path / "run-in-container"
    content = bridge_script.read_text(encoding="utf-8")

    # Replace docker exec with a mock shell echo/exit script for testing
    mock_script = content.replace(
        'docker exec -i -w /app dummy-id "$@"',
        'sh -c "$@"',
    )
    test_bridge = tmp_path / "test-bridge"
    test_bridge.write_text(mock_script, encoding="utf-8")
    test_bridge.chmod(0o755)

    # Run with SUPERSTATE_SHUNT_ENABLED=0 to force direct execution
    env = dict(os.environ, SUPERSTATE_SHUNT_ENABLED="0")
    res = subprocess.run([str(test_bridge), "exit 42"], env=env, shell=False)
    assert res.returncode == 42
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_container_bridge.py -v`  
Expected: FAIL with `AssertionError: assert 'superstate shunt' in content`

- [ ] **Step 3: Implement minimal shunting bridge in `lab/engine/drivers/agy_cli.py`**

Modify `lab/engine/drivers/agy_cli.py` around line 144:
```python
    def _setup_container_bridge(self, workspace_path: Path, container: Any) -> None:
        """Create a `./run-in-container` wrapper script in workspace pointing to container."""
        container_id = getattr(container, "id", None) or getattr(container, "name", str(container))
        script_path = workspace_path / "run-in-container"
        script_content = (
            "#!/usr/bin/env bash\n"
            "set -o pipefail\n\n"
            'if [ "${SUPERSTATE_SHUNT_ENABLED:-1}" = "1" ] && command -v superstate >/dev/null 2>&1; then\n'
            f'    exec superstate shunt --threshold-lines 50 -- docker exec -i -w /app {container_id} "$@"\n'
            "else\n"
            f'    exec docker exec -i -w /app {container_id} "$@"\n'
            "fi\n"
        )
        script_path.write_text(script_content, encoding="utf-8")
        current_mode = script_path.stat().st_mode
        script_path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_container_bridge.py -v`  
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add tests/test_container_bridge.py lab/engine/drivers/agy_cli.py
git commit -m "feat(bridge): implement transparent tool output shunting in run-in-container" --no-gpg-sign
```

---

### Task 2: In-Container Static Linux Binary Mounting (`lab/sandbox/docker_manager.py`)

- **Depends on:** none

**Files:**
- Modify: `lab/sandbox/docker_manager.py:70-80`
- Create: `tests/test_docker_manager_shunting.py`

**Interfaces:**
- Consumes: `DockerManager.spawn_sandbox(..., volumes=...)`
- Produces: Optional bind mount of static Linux `superstate` into `/usr/local/bin/superstate`.

- [ ] **Step 1: Write the failing unit tests in `tests/test_docker_manager_shunting.py`**

```python
"""Tests for in-container static binary mounting in DockerManager."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from lab.sandbox.docker_manager import DockerManager


def test_spawn_sandbox_mounts_static_superstate_when_file_exists(tmp_path: Path) -> None:
    """Verify spawn_sandbox bind-mounts /usr/local/bin/superstate when static binary is present."""
    fake_bin = tmp_path / "superstate-linux-x86_64"
    fake_bin.write_bytes(b"\x7fELFfakebinary")

    manager = DockerManager(client=MagicMock())
    with patch("lab.sandbox.docker_manager.find_static_superstate_binary", return_value=fake_bin):
        with manager.spawn_sandbox(image="dummy-image", command="sleep 10") as container:
            run_kwargs = manager.client.containers.run.call_args[1]
            volumes = run_kwargs["volumes"]
            assert str(fake_bin) in volumes
            assert volumes[str(fake_bin)]["bind"] == "/usr/local/bin/superstate"
            assert volumes[str(fake_bin)]["mode"] == "ro"


def test_spawn_sandbox_omits_mount_when_binary_absent() -> None:
    """Verify spawn_sandbox does not add mount when static binary is absent."""
    manager = DockerManager(client=MagicMock())
    with patch("lab.sandbox.docker_manager.find_static_superstate_binary", return_value=None):
        with manager.spawn_sandbox(image="dummy-image", command="sleep 10") as container:
            run_kwargs = manager.client.containers.run.call_args[1]
            volumes = run_kwargs["volumes"]
            assert not any("/usr/local/bin/superstate" == v.get("bind") for v in volumes.values())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_docker_manager_shunting.py -v`  
Expected: FAIL with `ModuleNotFoundError: cannot import name 'find_static_superstate_binary'`

- [ ] **Step 3: Implement static binary lookup and mounting in `lab/sandbox/docker_manager.py`**

In `lab/sandbox/docker_manager.py`:
```python
def find_static_superstate_binary() -> Optional[Path]:
    """Locate pre-compiled static Linux superstate binary if available on host."""
    env_path = os.environ.get("SUPERSTATE_LINUX_BIN")
    if env_path:
        p = Path(env_path)
        if p.is_file():
            return p

    repo_root = Path(__file__).resolve().parent.parent.parent
    candidates = [
        repo_root / "bin" / "superstate-linux-x86_64",
        repo_root / "bin" / "superstate-linux",
        Path.home() / ".cache" / "superstate" / "superstate-linux-x86_64",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None
```
In `spawn_sandbox()`:
```python
        static_bin = find_static_superstate_binary()
        if static_bin is not None:
            combined_volumes[str(static_bin)] = {
                "bind": "/usr/local/bin/superstate",
                "mode": "ro",
            }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_docker_manager_shunting.py -v`  
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add tests/test_docker_manager_shunting.py lab/sandbox/docker_manager.py
git commit -m "feat(sandbox): mount static superstate binary into sandbox containers when available" --no-gpg-sign
```

---

### Task 3: Shunt CLI Stdin Streaming & Exit Code Verification (`repos/superstate`)

- **Depends on:** none

**Files:**
- Modify: `/Users/danielfisher/repos/superstate/crates/superstate-cli/src/commands/shunt.rs`
- Create: `/Users/danielfisher/repos/superstate/crates/superstate-cli/tests/test_cli_shunt.rs`

**Interfaces:**
- Consumes: `superstate shunt -- <command> [args...]`
- Produces: Verified exit codes and stdin streaming across heavy outputs.

- [ ] **Step 1: Write integration tests in `crates/superstate-cli/tests/test_cli_shunt.rs`**

```rust
use std::process::Command;
use assert_cmd::prelude::*;

#[test]
fn test_shunt_preserves_stdin_and_exit_code() {
    let mut cmd = Command::cargo_bin("superstate").unwrap();
    cmd.args(&["shunt", "--threshold-lines", "5", "--", "sh", "-c", "cat; exit 17"]);
    cmd.write_stdin("hello world\nline 2\nline 3\nline 4\nline 5\nline 6\n");
    let assert = cmd.assert();
    assert.code(17);
}

#[test]
fn test_shunt_distills_output_over_threshold() {
    let mut cmd = Command::cargo_bin("superstate").unwrap();
    cmd.args(&["shunt", "--threshold-lines", "5", "--", "sh", "-c", "for i in $(seq 1 20); do echo line $i; done; exit 0"]);
    let assert = cmd.assert();
    assert.code(0);
    let output = String::from_utf8_lossy(&assert.get_output().stdout);
    assert!(output.contains("[superstate-shunt] Command succeeded (exit 0)"));
}
```

- [ ] **Step 2: Run test to verify behavior**

Run: `cargo test -p superstate-cli --test test_cli_shunt` in `/Users/danielfisher/repos/superstate`  
Expected: PASS or identify fixes needed.

- [ ] **Step 3: Refine `crates/superstate-cli/src/commands/shunt.rs` if needed**

Ensure flags `--threshold-lines` and stdin inheritance work cleanly with `--`.

- [ ] **Step 4: Rebuild and install updated binary**

Run: `cargo install --path crates/superstate-cli --locked --force` in `/Users/danielfisher/repos/superstate`

- [ ] **Step 5: Commit**

```bash
cd /Users/danielfisher/repos/superstate
git add crates/superstate-cli/src/commands/shunt.rs crates/superstate-cli/tests/test_cli_shunt.rs
git commit -m "feat(cli): verify and harden superstate shunt stdin streaming and exit propagation" --no-gpg-sign
```

---

### Task 4: Empirical Benchmark Verification on `build-cython-ext`

- **Depends on:** Task 1, Task 2, Task 3

**Files:**
- Target: `results/canary_shunted_build_cython_ext.json`

- [ ] **Step 1: Run isolated single-task canary evaluation on `build-cython-ext`**

Run:
```bash
./scripts/paired_run.py \
  --arm superstate_daemon_full \
  --tasks build-cython-ext \
  --budget-sec 3600 \
  --concurrency 1 \
  --json results/canary_shunted_build_cython_ext.json
```

- [ ] **Step 2: Verify shunting telemetry and token reduction**

Inspect `results/canary_shunted_build_cython_ext.json` and `.agent-state/logs/`:
1. Check that `.agent-state/logs/cmd_*.log` files were generated during the run.
2. Check `input_tokens` in the result JSON. Compare against EXP-065 baseline (733,391 tokens).
3. Confirm `passed: true` and `reward: 1.0` on the held-out sealed grader.

- [ ] **Step 3: Document findings in `FINDINGS.md` and `EXPERIMENTS.md`**

Update the experiment ledger with the token savings achieved through tool output distillation.
