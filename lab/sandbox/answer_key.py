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
from typing import Generator, Iterable

logger = logging.getLogger("superstate_eval.answer_key")

DEFAULT_STATE_FILE = Path.home() / ".cache" / "superstate-eval" / "sealed-paths.json"


class AnswerKeyGuard:
    """Seals and restores held-out test directories."""

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
        return restored

    @contextmanager
    def sealed(self, paths: Iterable[Path]) -> Generator[list[Path], None, None]:
        """Make `paths` unreadable for the duration of the block."""
        # Heal anything a hard kill left behind before sealing again.
        self.restore_all()

        targets = [p for p in paths if p is not None and Path(p).is_dir()]
        state = self._load()
        actually_sealed: list[Path] = []

        for path in targets:
            path = Path(path)
            try:
                original = stat.S_IMODE(path.stat().st_mode)
                state[str(path)] = original
                self._save(state)  # persist BEFORE chmod, so a crash is recoverable
                path.chmod(0o000)
                actually_sealed.append(path)
                logger.info("Sealed held-out tests at %s for the agent phase", path)
            except OSError as err:
                logger.error(
                    "Could not seal %s: %s. The agent may be able to read the "
                    "held-out tests during this run.",
                    path,
                    err,
                )
                state.pop(str(path), None)
                self._save(state)

        try:
            yield actually_sealed
        finally:
            for path in actually_sealed:
                mode = state.get(str(path))
                try:
                    path.chmod(mode if mode is not None else 0o755)
                except OSError as err:
                    logger.error("Failed to restore %s: %s", path, err)
                state.pop(str(path), None)
            self._save(state)


def is_readable(path: Path) -> bool:
    """Whether the current process can list `path`. Used by tests and diagnostics."""
    return os.access(path, os.R_OK | os.X_OK)
