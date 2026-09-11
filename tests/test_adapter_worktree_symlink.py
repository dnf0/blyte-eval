from pathlib import Path
from unittest.mock import MagicMock

from lab.engine.adapters.superstate import SuperstateAdapter


def test_switch_container_workspace_with_active_worktree(tmp_path: Path) -> None:
    adapter = SuperstateAdapter(engine="rust", no_worktree=False)
    mock_container = MagicMock()
    
    workspace = tmp_path / "workspace"
    wt_dir = workspace / ".wt" / "task-1"
    wt_dir.mkdir(parents=True)

    adapter._switch_container_workspace(mock_container, workspace, wt_dir)

    expected_cmd = ["sh", "-c", "ln -sfn /workspace_root/.wt/task-1 /app"]
    mock_container.exec_run.assert_called_once_with(expected_cmd, workdir="/")


def test_switch_container_workspace_resets_to_root(tmp_path: Path) -> None:
    adapter = SuperstateAdapter(engine="rust", no_worktree=False)
    mock_container = MagicMock()
    
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)

    adapter._switch_container_workspace(mock_container, workspace, None)

    expected_cmd = ["sh", "-c", "ln -sfn /workspace_root /app"]
    mock_container.exec_run.assert_called_once_with(expected_cmd, workdir="/")


def test_switch_container_workspace_no_worktree_mode(tmp_path: Path) -> None:
    adapter = SuperstateAdapter(engine="rust", no_worktree=True)
    mock_container = MagicMock()
    
    workspace = tmp_path / "workspace"
    wt_dir = workspace / ".wt" / "task-1"
    wt_dir.mkdir(parents=True)

    # In no_worktree mode, should always point to /workspace_root
    adapter._switch_container_workspace(mock_container, workspace, wt_dir)

    expected_cmd = ["sh", "-c", "ln -sfn /workspace_root /app"]
    mock_container.exec_run.assert_called_once_with(expected_cmd, workdir="/")


def test_switch_container_workspace_handles_none_container(tmp_path: Path) -> None:
    adapter = SuperstateAdapter(engine="rust", no_worktree=False)
    # Should safely return without exception
    adapter._switch_container_workspace(None, tmp_path, None)


def test_switch_container_workspace_unresolvable_worktree_fallback(tmp_path: Path) -> None:
    adapter = SuperstateAdapter(engine="rust", no_worktree=False)
    mock_container = MagicMock()

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    external_dir = tmp_path / "external" / "dir"
    external_dir.mkdir(parents=True)

    adapter._switch_container_workspace(mock_container, workspace, external_dir)

    expected_cmd = ["sh", "-c", "ln -sfn /workspace_root /app"]
    mock_container.exec_run.assert_called_once_with(expected_cmd, workdir="/")


def test_switch_container_workspace_handles_exec_nonzero_exit(tmp_path: Path) -> None:
    adapter = SuperstateAdapter(engine="rust", no_worktree=False)
    mock_container = MagicMock()
    mock_container.exec_run.return_value = (1, b"ln: permission denied")

    # Should not raise exception
    adapter._switch_container_workspace(mock_container, tmp_path, None)
    assert mock_container.exec_run.call_count == 1
