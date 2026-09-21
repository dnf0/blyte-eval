#!/usr/bin/env python3
"""Measure what a perimeter guard costs and saves, offline, in minutes rather than an hour.

WHY OFFLINE
-----------
A guard's job is to change how much context a read-heavy turn admits. That is measurable
directly: run the same prompt against the same repository with the guard on and off, and
compare the tokens. It needs no task corpus, no docker image, no sealed grader and no scoring
pass -- which is why it costs cents and minutes instead of $6 and an hour.

Spotify's Portal measured its own hooks this way: "tokens Claude would consume reading files
directly vs. consuming the bulk-reader's summary", across four scenarios on one monorepo. No
task success involved.

Four benchmark runs on 2026-09-21 tried to answer this question end-to-end and none of them
could, because a benchmark run varies a thousand things at once. This varies one.

USAGE
-----
    scripts/guard_bench.py --repo ~/repos/superstate \\
        --prompt "Explain how the daemon decides when to roll back a failed attempt." \\
        --configs none,file,command,full

Add a new guard by adding an entry to CONFIGS; nothing else needs to change.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

DEFAULT_BIN = Path("/Users/danielfisher/repos/superstate/target/release/superstate")

# Each config is the set of PreToolUse hooks provisioned for that arm. A new perimeter
# mechanism becomes measurable by adding a row here.
CONFIGS: dict[str, list[tuple[str, str, str]]] = {
    # name: [(hook group, tool matcher, guard subcommand + flags)]
    "none": [],
    "file": [
        ("superstate-file-guard", "view_file|View|read_file", "guard pre-tool-use --threshold-lines 200"),
    ],
    "command": [
        ("superstate-command-guard", "run_command|manage_task", "guard pre-command --debounce-sec 30"),
    ],
    "full": [
        ("superstate-file-guard", "view_file|View|read_file", "guard pre-tool-use --threshold-lines 200"),
        ("superstate-command-guard", "run_command|manage_task", "guard pre-command --debounce-sec 30"),
    ],
}


def write_hooks(workspace: Path, config: str, binary: Path) -> None:
    """Provision `.agents/hooks.json` exactly as DaemonRunner does, with an absolute path.

    The absolute path matters: a bare `superstate` resolves through PATH at hook time, which in
    EXP-077 meant a run enforced its guards with the previous day's build.
    """
    agents = workspace / ".agents"
    agents.mkdir(parents=True, exist_ok=True)
    hooks: dict[str, dict] = {}
    for group, matcher, subcommand in CONFIGS[config]:
        hooks[group] = {
            "PreToolUse": [
                {"matcher": matcher, "hooks": [{"command": f"{binary} {subcommand}"}]}
            ]
        }
    (agents / "hooks.json").write_text(json.dumps(hooks, indent=2), encoding="utf-8")


def denials(workspace: Path) -> tuple[int, int]:
    """(count, lines withheld) recorded by the guards during a run."""
    log = workspace / ".agent-state" / "guard-denials.jsonl"
    if not log.is_file():
        return 0, 0
    count = withheld = 0
    for line in log.read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
        except Exception:
            continue
        count += 1
        withheld += int(entry.get("lines") or 0)
    return count, withheld


def run_once(repo: Path, prompt: str, config: str, binary: Path, model: str,
             timeout_sec: int) -> dict:
    """One agy turn against a pristine copy of the repository."""
    with tempfile.TemporaryDirectory(prefix="guard_bench.") as tmp:
        workspace = Path(tmp) / "repo"
        # A copy per run, so one arm's edits cannot bias the next. `.git` is skipped: it is the
        # bulk of the bytes and nothing in a read-heavy prompt needs history.
        shutil.copytree(repo, workspace, ignore=shutil.ignore_patterns(".git", "target", "node_modules"))
        write_hooks(workspace, config, binary)

        env = dict(os.environ, SUPERSTATE_WORKTREE_PATH=str(workspace))
        started = time.monotonic()
        proc = subprocess.run(
            [
                "agy", "--model", model, "--output-format", "json",
                "--dangerously-skip-permissions", "--add-dir", str(workspace),
                "--print-timeout", f"{timeout_sec}s", "--print", prompt,
            ],
            cwd=workspace, env=env, capture_output=True, text=True,
            timeout=timeout_sec + 60,
        )
        elapsed = time.monotonic() - started

        usage: dict = {}
        try:
            usage = (json.loads(proc.stdout) or {}).get("usage") or {}
        except Exception:
            pass
        count, withheld = denials(workspace)
        return {
            "config": config,
            "input_tokens": int(usage.get("input_tokens") or 0),
            "output_tokens": int(usage.get("output_tokens") or 0),
            "cache_read_tokens": int(usage.get("cache_read_tokens") or 0),
            "denials": count,
            "lines_withheld": withheld,
            "seconds": round(elapsed, 1),
            "ok": proc.returncode == 0,
        }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", required=True, type=Path)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--configs", default="none,full")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--model", default="gemini-3.8-flash-high")
    ap.add_argument("--binary", type=Path, default=DEFAULT_BIN)
    ap.add_argument("--timeout-sec", type=int, default=300)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    prompt = args.prompt
    if prompt.startswith("@"):
        prompt = Path(prompt[1:]).read_text(encoding="utf-8")

    if not args.binary.is_file():
        print(f"no superstate binary at {args.binary}", file=sys.stderr)
        return 1
    if shutil.which("agy") is None:
        print("agy is not on PATH", file=sys.stderr)
        return 1

    names = [c.strip() for c in args.configs.split(",") if c.strip()]
    for name in names:
        if name not in CONFIGS:
            print(f"unknown config {name!r}; known: {sorted(CONFIGS)}", file=sys.stderr)
            return 1

    results: list[dict] = []
    for name in names:
        for i in range(args.repeats):
            print(f"  running {name} ({i + 1}/{args.repeats}) ...", flush=True)
            results.append(run_once(args.repo, prompt, name, args.binary,
                                    args.model, args.timeout_sec))

    print(f"\n{'config':10s} {'in_tok':>10s} {'cache_read':>11s} {'out':>8s} "
          f"{'denials':>8s} {'withheld':>9s} {'secs':>6s}")
    medians: dict[str, float] = {}
    for name in names:
        rows = [r for r in results if r["config"] == name]
        med = statistics.median(r["input_tokens"] for r in rows)
        medians[name] = med
        print(f"{name:10s} {med:>10,.0f} "
              f"{statistics.median(r['cache_read_tokens'] for r in rows):>11,.0f} "
              f"{statistics.median(r['output_tokens'] for r in rows):>8,.0f} "
              f"{statistics.median(r['denials'] for r in rows):>8,.0f} "
              f"{statistics.median(r['lines_withheld'] for r in rows):>9,.0f} "
              f"{statistics.median(r['seconds'] for r in rows):>6,.0f}")

    if "none" in medians and medians["none"]:
        print()
        for name in names:
            if name == "none":
                continue
            delta = 100 * (medians[name] - medians["none"]) / medians["none"]
            print(f"  {name:10s} {delta:+.1f}% input tokens vs no guards")

    if args.out:
        args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
