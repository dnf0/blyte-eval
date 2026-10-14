"""Dispatch hook for blyte pair driver.

Invoked by blyte as `--dispatch-cmd "<executable> -m lab.engine.drivers.dispatch_hook"`.
Reads one JSON object `{task, gate, max_seconds?}` from stdin, calls
`ContainerExec().dispatch(...)`, prints the returned JSON text to stdout,
and exits 0 (or 1 when `is_error` is True).
"""

from __future__ import annotations

import json
import sys
from typing import Any

from lab.engine.drivers.container_exec_mcp import ContainerExec


def main() -> int:
    raw = sys.stdin.read()
    payload = json.loads(raw) if raw.strip() else {}
    if not isinstance(payload, dict):
        payload = {}
    task = str(payload.get("task", ""))
    gate = str(payload.get("gate", ""))
    kwargs: dict[str, Any] = {}
    if "max_seconds" in payload and payload["max_seconds"] is not None:
        kwargs["max_seconds"] = int(payload["max_seconds"])

    executor = ContainerExec()
    result_text, is_error = executor.dispatch(task=task, gate=gate, **kwargs)
    sys.stdout.write(result_text)
    if not result_text.endswith("\n"):
        sys.stdout.write("\n")
    sys.stdout.flush()
    return 1 if is_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
