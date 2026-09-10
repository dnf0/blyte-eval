"""Keep the held-out tests unreadable while the agent is working.

A host-side agent runs as the same OS user as the harness, so it can in
principle read the task's `tests/` directory -- the answer key -- straight off
the filesystem. Making that directory mode 000 for the duration of the agent
phase blocks it: reads, listing, and recursive grep all fail for the owner too.

This is a lock on a door, not a vault. The same user can chmod it back, so it is
not proof against an agent that deliberately sets out to defeat it. What it does
remove is accidental discovery -- a repo-wide grep or find wandering out of the
workspace -- which is the realistic failure mode for a cooperative model. When a
hard guarantee is needed, run the agent inside the container instead
(lab.sandbox.agent_image), where the path does not exist at all.

Modes are recorded in a state file so a crashed run cannot leave a task
directory permanently unreadable; the next run restores anything left sealed.
"""

from __future__ import annotations

from contextlib import contextmanager
import json
import logging
import os
from pathlib import Path
import stat
import threading
from typing import Generator, Iterable

logger = logging.getLogger("superstate_eval.answer_key")

DEFAULT_STATE_FILE = Path.home() / ".cache" / "superstate-eval" / "sealed-paths.json"


class AnswerKeyGuard:
    """Seals and restores held-out test directories with thread-safe reference counting."""

    _lock: threading.RLock = threading.RLock()
    _active_counts: dict[str, int] = {}

    def __init__(self, state_file: Path | str = DEFAULT_STATE_FILE) -> None:
        self.state_file = Path(state_file)

    def _load(self) -> dict[str, int]:
        if not self.state_file.is_file():
            return {}
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            return {str(k): int(v) for k, v in data.items()}
        except Exception as err:
            logger.warning("Could not read seal state %s: %s", self.state_file, err)
            return {}

    def _save(self, sealed: dict[str, int]) -> None:
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(json.dumps(sealed, indent=2), encoding="utf-8")
        except OSError as err:
            logger.warning("Could not persist seal state %s: %s", self.state_file, err)

    def restore_all(self) -> list[Path]:
        """Restore anything a previous run left sealed. Safe to call at any time."""
        with self._lock:
            sealed = self._load()
            restored: list[Path] = []
            for raw_path, mode in list(sealed.items()):
                path = Path(raw_path)
                if path.exists():
                    try:
                        path.chmod(mode)
                        restored.append(path)
                        logger.info("Restored previously sealed path %s", path)
                    except OSError as err:
                        logger.error("Could not restore %s to mode %o: %s", path, mode, err)
                        continue
                sealed.pop(raw_path, None)
            self._save(sealed)
            self._active_counts.clear()
            return restored

    @contextmanager
    def sealed(self, paths: Iterable[Path]) -> Generator[list[Path], None, None]:
        """Make `paths` unreadable for the duration of the block, with thread-safe refcounting."""
        targets = [Path(p).resolve() for p in paths if p is not None and Path(p).is_dir()]
        actually_sealed: list[Path] = []

        with self._lock:
            if not self._active_counts:
                self.restore_all()

            state = self._load()
            for path in targets:
                p_str = str(path)
                count = self._active_counts.get(p_str, 0)
                if count == 0 and path.is_dir():
                    try:
                        original = stat.S_IMODE(path.stat().st_mode)
                        state[p_str] = original
                        self._save(state)
                        path.chmod(0o000)
                        logger.info("Sealed held-out tests at %s for the agent phase", path)
                    except OSError as err:
                        logger.error("Could not seal %s: %s", path, err)
                        state.pop(p_str, None)
                        self._save(state)
                actually_sealed.append(path)
                self._active_counts[p_str] = count + 1

        try:
            yield actually_sealed
        finally:
            with self._lock:
                state = self._load()
                for path in actually_sealed:
                    p_str = str(path)
                    count = self._active_counts.get(p_str, 1) - 1
                    if count <= 0:
                        self._active_counts.pop(p_str, None)
                        mode = state.get(p_str, 0o755)
                        try:
                            path.chmod(mode)
                            logger.info("Restored held-out tests at %s", path)
                        except OSError as err:
                            logger.error("Failed to restore %s: %s", path, err)
                        state.pop(p_str, None)
                    else:
                        self._active_counts[p_str] = count
                self._save(state)

    @contextmanager
    def temporarily_readable(self, path: Path) -> Generator[None, None, None]:
        """Temporarily restore readability to a sealed path (e.g. for verifier image build)."""
        p = Path(path).resolve()
        p_str = str(p)
        was_sealed = False
        with self._lock:
            state = self._load()
            if self._active_counts.get(p_str, 0) > 0 and p.is_dir():
                mode = state.get(p_str, 0o755)
                try:
                    p.chmod(mode)
                    was_sealed = True
                except OSError as err:
                    logger.error("Failed to temporarily unseal %s: %s", p, err)

        try:
            yield
        finally:
            if was_sealed:
                with self._lock:
                    if self._active_counts.get(p_str, 0) > 0 and p.is_dir():
                        try:
                            p.chmod(0o000)
                        except OSError as err:
                            logger.error("Failed to re-seal %s: %s", p, err)


def is_readable(path: Path) -> bool:
    """Whether the current process can list `path`. Used by tests and diagnostics."""
    return os.access(path, os.R_OK | os.X_OK)
