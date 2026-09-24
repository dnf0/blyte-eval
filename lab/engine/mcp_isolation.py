"""Strip unrelated MCP servers for the duration of an evaluation run.

WHY
---
Every `agy` invocation loads the schemas of every globally-enabled MCP server before it reads
a single line of the task. Measured 2026-09-21 (FINDINGS 13.17): a turn that replies "pong"
and does nothing else costs **24,222 fresh input tokens**, of which **13,288 is MCP tool
schemas** -- 55% -- for `github`, `notion` and `slack`, which no benchmark task touches. It
also costs wall clock: 17.2s against 1.7s.

`superstate` is kept only for the legacy bolt-on arms: the `superstate_mcp` arms are Condition B
and talk to it over stdio, so removing it would change what is under test. A harness comparison
(`paired_run.py --harnesses`) keeps nothing: there the `superstate` server is ambient overhead
on agy (~13K tokens a call) that no harness under test uses (`servers_to_keep`).

WHY IT IS DONE HERE RATHER THAN BY HAND
---------------------------------------
`agy` has no per-invocation flag for this -- the full flag list has nothing for tools or MCP --
so it is global state, and CLAUDE.md's standing warning is that a crashed run leaves the
servers disabled. Two consequences shape this module:

* **The original is renamed, never copied.** That file holds live API credentials. Copying it
  would put a second copy of those secrets somewhere; renaming moves the same inode and
  preserves its permissions exactly.
* **It self-heals on entry.** If a previous run died before restoring, the stashed original is
  still on disk next to the config, and the next run puts it back before doing anything else.
  A crash therefore costs one run's isolation, never the user's working setup.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)

MCP_CONFIG = Path.home() / ".gemini" / "config" / "mcp_config.json"
STASH = MCP_CONFIG.with_suffix(".json.superstate-eval-stash")

#: Servers kept during a run. `superstate` is the arm under test, not ambient overhead.
KEEP_BY_DEFAULT = frozenset({"superstate"})


def servers_to_keep(harness_mode: bool) -> frozenset[str]:
    """Servers to keep for a run: none when comparing harnesses, `superstate` for legacy arms."""
    return frozenset() if harness_mode else KEEP_BY_DEFAULT


def _restore(reason: str) -> bool:
    """Put the stashed original back. Idempotent; safe to call when nothing is stashed."""
    if not STASH.exists():
        return False
    try:
        os.replace(STASH, MCP_CONFIG)
        logger.info("MCP config restored (%s)", reason)
        return True
    except OSError as e:
        # Loud, because the user's interactive setup is now degraded until they fix it.
        logger.error(
            "COULD NOT RESTORE MCP CONFIG: %s. The original is at %s -- "
            "move it back to %s to restore your MCP servers.", e, STASH, MCP_CONFIG
        )
        return False


@contextlib.contextmanager
def stripped_mcp_servers(keep: frozenset[str] = KEEP_BY_DEFAULT, enabled: bool = True) -> Iterator[list[str]]:
    """Remove non-essential MCP servers for the duration of the block.

    Yields the list of server names that were stripped (empty if isolation did not apply).
    Never raises on failure: a run with the servers still loaded is more expensive but still
    valid, and every arm in a run is affected identically, so it is not a confound. It warns
    instead, and the caller records the outcome in provenance.
    """
    if not enabled:
        yield []
        return

    # Self-heal first: a previous run may have died before restoring.
    if _restore("recovering from an earlier run that did not clean up"):
        pass

    if not MCP_CONFIG.is_file():
        logger.info("no MCP config at %s; nothing to strip", MCP_CONFIG)
        yield []
        return

    try:
        original = json.loads(MCP_CONFIG.read_text(encoding="utf-8"))
        servers = original.get("mcpServers") or {}
        stripped = sorted(n for n in servers if n not in keep)
        if not stripped:
            yield []
            return
        filtered = dict(original)
        filtered["mcpServers"] = {n: c for n, c in servers.items() if n in keep}

        # Rename, never copy: the original holds live credentials.
        os.replace(MCP_CONFIG, STASH)
        MCP_CONFIG.write_text(json.dumps(filtered, indent=2), encoding="utf-8")
        MCP_CONFIG.chmod(0o644)
        logger.info(
            "MCP servers stripped for this run: %s (kept: %s). ~13,288 tokens/invocation.",
            ", ".join(stripped), ", ".join(sorted(keep)) or "none",
        )
    except Exception as e:
        logger.warning("could not strip MCP servers (%s); the run continues with them loaded", e)
        _restore("strip failed partway")
        yield []
        return

    try:
        yield stripped
    finally:
        _restore("run finished")
