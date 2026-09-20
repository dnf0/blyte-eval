# Task 1 Brief: Container Bridge Output Shunting

## Objective
Implement transparent tool output shunting in the generated `./run-in-container` script in `lab/engine/drivers/agy_cli.py`, routing Docker commands through `superstate shunt --threshold-lines 50` when `superstate` is available on the host and shunting is active (`SUPERSTATE_SHUNT_ENABLED=1`).

## Working Directory
`/Users/danielfisher/repos/superstate-eval/.worktrees/feat-eval-philosophy-autonomous-tdd`

## Global Constraints
- Follow strict Test-Driven Development (TDD): write failing tests first in `tests/test_container_bridge.py`, verify failure, then implement minimal code, verify pass.
- Python 3.12, strict typing, passing `ruff check` and `pyright`.
- Use `.venv/bin/python` for all pytest commands (`.venv/bin/python -m pytest tests/test_container_bridge.py -v`).
- Conventional Commit with `--no-gpg-sign`.

## Files to Touch
- Create: `tests/test_container_bridge.py`
- Modify: `lab/engine/drivers/agy_cli.py:144-156`

## Detailed Steps
1. Write unit tests in `tests/test_container_bridge.py`:
   - `test_setup_container_bridge_generates_shunting_script(tmp_path)`: Tests that `_setup_container_bridge` creates `./run-in-container` containing `superstate shunt --threshold-lines 50` and the check `if [ "${SUPERSTATE_SHUNT_ENABLED:-1}" = "1" ] && command -v superstate >/dev/null 2>&1;`. Also checks executable permissions.
   - `test_container_bridge_preserves_exit_code_and_fallback(tmp_path)`: Tests that when shunting is disabled (`SUPERSTATE_SHUNT_ENABLED=0`), the fallback directly executes the command and faithfully preserves the integer exit code (e.g. exit 42).
   - `test_container_bridge_preserves_stdin_piping(tmp_path)`: Tests that stdin can be piped through the script (e.g. `cat <<'EOF' | ./run-in-container sh -s`).
2. Run `.venv/bin/python -m pytest tests/test_container_bridge.py -v` (Verify RED failure).
3. Modify `_setup_container_bridge` in `lab/engine/drivers/agy_cli.py`:
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
4. Run `.venv/bin/python -m pytest tests/test_container_bridge.py -v` (Verify GREEN pass).
5. Run full test suite: `.venv/bin/python -m pytest tests/ -q` (Must pass all tests).
6. Commit: `git commit -m "feat(bridge): implement transparent tool output shunting in run-in-container" --no-gpg-sign`.
7. Write task report to `docs/superpowers/plans/task-1-shunting-bridge-report.md`.
