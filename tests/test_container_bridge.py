"""Tests for container bridge script generation and transparent shunting.

Validates that `./run-in-container` correctly routes commands through `superstate shunt`
when available and enabled, falls back gracefully when disabled or absent, and faithfully
preserves exit codes and stdin streaming.
"""

from __future__ import annotations

import os
from pathlib import Path
import stat
import subprocess
import sys

from lab.engine.drivers.agy_cli import AgyCliDriver


class FakeContainer:
    """Minimal fake container object providing an id and name."""

    def __init__(self, container_id: str = "cnt-test-12345") -> None:
        self.id = container_id
        self.name = f"eval-{container_id}"


def _create_fake_docker(bin_dir: Path) -> Path:
    """Create a mock docker executable simulating docker exec forwarding.

    Strips docker exec flags (-i, -w <dir>, and container_id) and directly
    executes the underlying command to simulate container execution locally.
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    docker_bin = bin_dir / "docker"
    docker_bin.write_text(
        "#!/usr/bin/env bash\n"
        "set -eu\n"
        'if [ "${1:-}" = "exec" ]; then\n'
        "    shift\n"
        '    while [ "$#" -gt 0 ]; do\n'
        '        case "$1" in\n'
        "            -i|-t|-it)\n"
        "                shift\n"
        "                ;;\n"
        "            -w)\n"
        "                shift 2\n"
        "                ;;\n"
        "            *)\n"
        "                # Container ID parameter\n"
        "                shift\n"
        "                break\n"
        "                ;;\n"
        "        esac\n"
        "    done\n"
        "fi\n"
        'exec "$@"\n',
        encoding="utf-8",
    )
    current_mode = docker_bin.stat().st_mode
    docker_bin.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return docker_bin


def _create_fake_superstate(bin_dir: Path, log_file: Path) -> Path:
    """Create a mock superstate executable that logs its arguments and forwards the command."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    superstate_bin = bin_dir / "superstate"
    superstate_bin.write_text(
        "#!/usr/bin/env bash\n"
        "set -eu\n"
        f'echo "$@" >> "{log_file}"\n'
        'if [ "${1:-}" = "shunt" ]; then\n'
        "    shift\n"
        '    while [ "$#" -gt 0 ] && [ "$1" != "--" ]; do\n'
        "        shift\n"
        "    done\n"
        '    if [ "${1:-}" = "--" ]; then\n'
        "        shift\n"
        "    fi\n"
        "fi\n"
        'exec "$@"\n',
        encoding="utf-8",
    )
    current_mode = superstate_bin.stat().st_mode
    superstate_bin.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return superstate_bin


def test_setup_container_bridge_generates_shunting_script(tmp_path: Path) -> None:
    """Ensure _setup_container_bridge generates run-in-container with shunt check and permissions."""
    driver = AgyCliDriver(cli_path=sys.executable)
    container = FakeContainer("cnt-shunting-42")

    # Generate the container bridge script in the temporary workspace
    driver._setup_container_bridge(workspace_path=tmp_path, container=container)

    script_path = tmp_path / "run-in-container"
    assert script_path.is_file(), "run-in-container script must be created"

    # Verify executable permissions
    mode = script_path.stat().st_mode
    assert mode & stat.S_IXUSR, "Script must be user-executable"
    assert mode & stat.S_IXGRP, "Script must be group-executable"
    assert mode & stat.S_IXOTH, "Script must be other-executable"

    content = script_path.read_text(encoding="utf-8")

    # Verify transparent shunting logic and flags
    assert "set -o pipefail" in content
    assert 'if [ "${SUPERSTATE_SHUNT_ENABLED:-1}" = "1" ] && command -v superstate >/dev/null 2>&1;' in content
    assert 'exec superstate shunt --threshold-lines 50 -- docker exec -i -w /app cnt-shunting-42 "$@"' in content
    assert 'exec docker exec -i -w /app cnt-shunting-42 "$@"' in content


def test_container_bridge_preserves_exit_code_and_fallback(tmp_path: Path) -> None:
    """Ensure non-zero exit codes are preserved through the bridge when shunting is disabled."""
    driver = AgyCliDriver(cli_path=sys.executable)
    container = FakeContainer("cnt-fallback-99")
    driver._setup_container_bridge(workspace_path=tmp_path, container=container)

    script_path = tmp_path / "run-in-container"

    # Set up fake docker on PATH so the script executes without real docker
    bin_dir = tmp_path / "bin"
    _create_fake_docker(bin_dir)

    test_env = os.environ.copy()
    test_env["PATH"] = f"{bin_dir}:{test_env.get('PATH', '')}"
    test_env["SUPERSTATE_SHUNT_ENABLED"] = "0"

    # Execute a command that exits with code 42
    result = subprocess.run(
        [str(script_path), "bash", "-c", "exit 42"],
        env=test_env,
        capture_output=True,
    )

    assert result.returncode == 42, f"Expected returncode 42, got {result.returncode}"


def test_container_bridge_preserves_stdin_piping(tmp_path: Path) -> None:
    """Ensure stdin streaming is faithfully preserved across the container bridge."""
    driver = AgyCliDriver(cli_path=sys.executable)
    container = FakeContainer("cnt-stdin-123")
    driver._setup_container_bridge(workspace_path=tmp_path, container=container)

    script_path = tmp_path / "run-in-container"

    # Set up fake docker on PATH
    bin_dir = tmp_path / "bin"
    _create_fake_docker(bin_dir)

    test_env = os.environ.copy()
    test_env["PATH"] = f"{bin_dir}:{test_env.get('PATH', '')}"
    test_env["SUPERSTATE_SHUNT_ENABLED"] = "0"

    stdin_payload = "first line\nsecond line\nthird line with special chars: $*!@\n"

    # Run sh -s receiving commands via stdin
    result = subprocess.run(
        [str(script_path), "sh", "-s"],
        input=f"cat <<'EOF'\n{stdin_payload}EOF\n",
        env=test_env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert stdin_payload in result.stdout


def test_container_bridge_routes_through_superstate_shunt_when_available(tmp_path: Path) -> None:
    """Verify that when superstate is present and shunting enabled, superstate shunt is invoked."""
    driver = AgyCliDriver(cli_path=sys.executable)
    container = FakeContainer("cnt-routed-77")
    driver._setup_container_bridge(workspace_path=tmp_path, container=container)

    script_path = tmp_path / "run-in-container"

    # Set up fake docker and fake superstate on PATH
    bin_dir = tmp_path / "bin"
    _create_fake_docker(bin_dir)
    log_file = tmp_path / "superstate.log"
    _create_fake_superstate(bin_dir, log_file)

    test_env = os.environ.copy()
    test_env["PATH"] = f"{bin_dir}:{test_env.get('PATH', '')}"
    test_env["SUPERSTATE_SHUNT_ENABLED"] = "1"

    result = subprocess.run(
        [str(script_path), "echo", "executed inside container"],
        env=test_env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "executed inside container" in result.stdout.strip()

    # Verify superstate shunt was called with correct parameters
    log_content = log_file.read_text(encoding="utf-8")
    assert "shunt --threshold-lines 50 -- docker exec -i -w /app cnt-routed-77 echo executed inside container" in log_content
