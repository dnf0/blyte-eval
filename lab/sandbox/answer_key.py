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
import shutil
import stat
import threading
from typing import Generator, Iterable

logger = logging.getLogger("superstate_eval.answer_key")

DEFAULT_STATE_FILE = Path.home() / ".cache" / "superstate-eval" / "sealed-paths.json"


class AnswerKeyGuard:
    """Seals and restores held-out test directories with thread-safe reference counting."""

    _lock: threading.RLock = threading.RLock()
    _active_counts: dict[str, int] = {}
    # A readable copy taken before sealing: the verifier is built from these
    # tests, so sealing the only copy would make grading impossible.
    _staged: dict[str, Path] = {}

    @classmethod
    def staged_copy(cls, path: Path) -> Path | None:
        """A readable copy of a sealed directory, for grading.

        The verifier is built from the task's tests, so it reads this rather than
        the sealed original.
        """
        with cls._lock:
            return cls._staged.get(str(Path(path).resolve()))

    @contextmanager
    def temporarily_readable(self, path: Path) -> Generator[Path, None, None]:
        """Yield a readable view of `path`, for grading.

        Deliberately does not unseal the original. Runs overlap, so unsealing for
        one run's grading would expose the answers to another run's agent, which
        is the case the seal exists for. The staged copy taken before sealing is
        handed over instead, and callers must build from the yielded path.
        """
        staged = self.staged_copy(path)
        yield staged if staged is not None else Path(path)

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
        """Make `paths` unreadable for the duration of the block.

        Nests safely: concurrent callers share one seal, and the directories are
        restored when the last of them exits.
        """
        targets = [Path(p).resolve() for p in paths if p is not None and Path(p).is_dir()]
        acquired: list[Path] = []

        for path in targets:
            key = str(path)
            with self._lock:
                if self._active_counts.get(key, 0) > 0:
                    # Already sealed by another run: join it rather than resealing.
                    self._active_counts[key] += 1
                    acquired.append(path)
                    continue
                try:
                    self._stage(path)
                    state = self._load()
                    state[key] = stat.S_IMODE(path.stat().st_mode)
                    self._save(state)  # persist BEFORE chmod, so a crash is recoverable
                    path.chmod(0o000)
                    self._active_counts[key] = 1
                    acquired.append(path)
                    logger.info("Sealed held-out tests at %s for the agent phase", path)
                except OSError as err:
                    logger.error(
                        "Could not seal %s: %s. The agent may be able to read the "
                        "held-out tests during this run.",
                        path,
                        err,
                    )
                    state = self._load()
                    state.pop(key, None)
                    self._save(state)

        try:
            yield acquired
        finally:
            for path in acquired:
                key = str(path)
                with self._lock:
                    remaining = self._active_counts.get(key, 1) - 1
                    self._active_counts[key] = max(0, remaining)
                    if remaining > 0:
                        continue  # another run is still working
                    state = self._load()
                    mode = state.get(key)
                    try:
                        path.chmod(mode if mode is not None else 0o755)
                    except OSError as err:
                        logger.error("Failed to restore %s: %s", path, err)
                    state.pop(key, None)
                    self._save(state)
                    self._active_counts.pop(key, None)

    def _stage(self, path: Path) -> None:
        """Copy a directory somewhere readable before it is sealed.

        The verifier is built from these tests, so sealing the only copy would
        make grading impossible. Staging happens before the chmod, so the copy is
        taken while the directory is still readable.
        """
        key = str(path)
        if key in self._staged:
            return
        staging = self.state_file.parent / "staged" / path.parent.name / path.name
        try:
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
            staging.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(path, staging)
            self._staged[key] = staging
        except OSError as err:
            logger.warning("Could not stage %s for grading: %s", path, err)


def is_readable(path: Path) -> bool:
    """Whether the current process can list `path`. Used by tests and diagnostics."""
    return os.access(path, os.R_OK | os.X_OK)
