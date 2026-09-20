# Task 2 Report: In-Container Static Linux Binary Mounting

## Summary
Successfully implemented automatic in-container static Linux `superstate` binary mounting in `lab/sandbox/docker_manager.py`. When `DockerManager.run_sandbox()` (or its alias `spawn_sandbox()`) launches a container, it checks for a pre-compiled static Linux `superstate` binary on the host via `SUPERSTATE_LINUX_BIN` or candidate paths in `bin/` or `~/.cache/superstate/`. If present, it automatically bind-mounts the binary to `/usr/local/bin/superstate` in read-only mode (`ro`).

## Commits
- **`3ee502d`**: `feat(sandbox): mount static superstate binary into sandbox containers when available`
- **`f93ef3b`**: `fix(tests): update agy_cli_driver test for quoted container_id` (reconciled test assertion with quoted container ID in `run-in-container`)

## TDD Verification Lifecycle

### 1. RED Phase
Created unit tests in `tests/test_docker_manager_shunting.py`:
- `test_spawn_sandbox_mounts_static_superstate_when_file_exists(tmp_path)`: Verifies that when a static Linux binary exists, `spawn_sandbox` bind-mounts it to `/usr/local/bin/superstate` with mode `"ro"`.
- `test_spawn_sandbox_omits_mount_when_binary_absent()`: Verifies that `/usr/local/bin/superstate` is not mounted when no static binary exists.
- `test_find_static_superstate_binary_env_var(tmp_path, monkeypatch)`: Verifies that `SUPERSTATE_LINUX_BIN` overrides default candidate resolution when the pointed file exists.
- `test_find_static_superstate_binary_env_var_nonexistent(tmp_path, monkeypatch)`: Verifies fallback behavior when `SUPERSTATE_LINUX_BIN` points to a non-existent path.
- `test_find_static_superstate_binary_none_when_no_candidates_exist(monkeypatch)`: Verifies `None` is returned when neither the environment variable nor any candidate binary paths exist.

**Initial Test Run (RED)**:
```
ImportError: cannot import name 'find_static_superstate_binary' from 'lab.sandbox.docker_manager'
=========================== short test summary info ============================
ERROR tests/test_docker_manager_shunting.py
1 error in 0.28s
```

### 2. GREEN Phase
Implemented `find_static_superstate_binary()` and updated `DockerManager` in `lab/sandbox/docker_manager.py`:
1. `find_static_superstate_binary()` checks `SUPERSTATE_LINUX_BIN` if set and file exists.
2. Checks candidate paths: `<repo_root>/bin/superstate-linux-x86_64`, `<repo_root>/bin/superstate-linux`, `~/.cache/superstate/superstate-linux-x86_64`.
3. Inside `run_sandbox()`, inspects `find_static_superstate_binary()`. If found, registers `{"bind": "/usr/local/bin/superstate", "mode": "ro"}` in `combined_volumes`.
4. Aliased `spawn_sandbox = run_sandbox` on `DockerManager`.

**Unit Test Run (GREEN)**:
```
tests/test_docker_manager_shunting.py::test_spawn_sandbox_mounts_static_superstate_when_file_exists PASSED [ 20%]
tests/test_docker_manager_shunting.py::test_spawn_sandbox_omits_mount_when_binary_absent PASSED [ 40%]
tests/test_docker_manager_shunting.py::test_find_static_superstate_binary_env_var PASSED [ 60%]
tests/test_docker_manager_shunting.py::test_find_static_superstate_binary_env_var_nonexistent PASSED [ 80%]
tests/test_docker_manager_shunting.py::test_find_static_superstate_binary_none_when_no_candidates_exist PASSED [100%]
============================== 5 passed in 0.63s ===============================
```

### 3. Static Analysis & Linting
- **Ruff**: `.venv/bin/ruff check lab tests` -> Clean (All checks passed).
- **Pyright**: `uv run pyright lab tests` -> 0 errors, 0 warnings, 0 informations.

### 4. Full Regression Test Suite
Executed the entire test suite on the `.venv` interpreter:
- **Command**: `.venv/bin/python -m pytest tests/ -q`
- **Result**: `342 passed in 55.62s`
