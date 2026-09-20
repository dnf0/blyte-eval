# Task 2 Brief: In-Container Static Linux Binary Mounting

## Objective
Update `lab/sandbox/docker_manager.py` so that when `DockerManager.spawn_sandbox(...)` launches a sandbox container, it checks if a pre-compiled static Linux `superstate` binary exists on the host (e.g. via `SUPERSTATE_LINUX_BIN` env var or in candidate locations such as `bin/superstate-linux-x86_64`), and if present, automatically bind-mounts it to `/usr/local/bin/superstate` (read-only mode).

## Working Directory
`/Users/danielfisher/repos/superstate-eval/.worktrees/feat-eval-philosophy-autonomous-tdd`

## Global Constraints
- Follow strict Test-Driven Development (TDD): write failing tests first in `tests/test_docker_manager_shunting.py`, verify failure, then implement minimal code, verify pass.
- Python 3.12, strict typing, passing `ruff check` and `pyright`.
- Use `.venv/bin/python` for all pytest commands (`.venv/bin/python -m pytest tests/test_docker_manager_shunting.py -v`).
- Conventional Commit with `--no-gpg-sign`.

## Files to Touch
- Create: `tests/test_docker_manager_shunting.py`
- Modify: `lab/sandbox/docker_manager.py`

## Detailed Steps
1. Write failing unit tests in `tests/test_docker_manager_shunting.py`:
   - `test_spawn_sandbox_mounts_static_superstate_when_file_exists(tmp_path)`:
     Create a fake binary in `tmp_path`, mock `find_static_superstate_binary` to return it, mock `DockerManager.client.containers.run`, call `with manager.spawn_sandbox(image="dummy-image", command="sleep 10") as container:`, and assert that the volumes dict passed to `containers.run` contains the fake binary path bound to `/usr/local/bin/superstate` with mode `"ro"`.
   - `test_spawn_sandbox_omits_mount_when_binary_absent()`:
     Mock `find_static_superstate_binary` to return `None`, invoke `spawn_sandbox`, and assert that `/usr/local/bin/superstate` is NOT in the mounted volumes.
   - `test_find_static_superstate_binary_env_var(tmp_path)`:
     Test that `find_static_superstate_binary` respects `SUPERSTATE_LINUX_BIN`.
2. Run `.venv/bin/python -m pytest tests/test_docker_manager_shunting.py -v` (Verify RED failure).
3. Implement `find_static_superstate_binary()` and update `spawn_sandbox()` in `lab/sandbox/docker_manager.py`:
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
           combined_volumes[str(static_bin.resolve())] = {
               "bind": "/usr/local/bin/superstate",
               "mode": "ro",
           }
   ```
4. Run `.venv/bin/python -m pytest tests/test_docker_manager_shunting.py -v` (Verify GREEN pass).
5. Run full test suite: `.venv/bin/python -m pytest tests/ -q` (Must pass all tests).
6. Run `ruff check lab tests` and `pyright lab tests`.
7. Commit: `git commit -m "feat(sandbox): mount static superstate binary into sandbox containers when available" --no-gpg-sign`.
8. Write task report to `docs/superpowers/plans/task-2-docker-manager-shunting-report.md`.
