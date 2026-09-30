# Codex as the Orchestrator in the Eval — Plan

> **For agentic workers:** Execution is delegated to headless `blyte` (with a sampled A/B against `agy`), one task per dispatch; Claude reviews each task before the next is sent. Do NOT `git push` or open PRs; commit locally only. Do NOT start any benchmark or paid run, or call any model API. Do not edit `FINDINGS.md`, `EXPERIMENTS.md`, `CLAUDE.md`/`AGENTS.md`, `results/`, `traces/` or `data/`.

**Why (2026-09-30):** Codex CLI now runs blyte end to end (blyte #164). To compare Codex + blyte with
Claude Code + blyte on the same task, the eval needs a Codex driver with the Claude arms' conditions:
the task's toolchain reached only through the container MCP server (`run_in_container`, and
`dispatch_blyte` when an implementer model is set); Codex's host tools off (`--disable shell_tool`,
`unified_exec`, `js_repl`, `browser_use`, `computer_use`, `web_search=disabled`); and the operator's
Codex setup kept out: HOME and CODEX_HOME are a fresh directory holding only a symlink to the
operator's `auth.json` (no config, AGENTS.md, skills or rules load; the credentials are never copied).
MCP tools need `default_tools_approval_mode="approve"` to run under `codex exec`. All of this was
checked against the real CLI (0.157) before planning. Under a ChatGPT login Codex reports tokens
but no cost: the frontier cost is 0 and the tokens are in `metrics["frontier_tokens"]`.
Harness specs: `codex` and `codex+blyte[<implementer model>]`, with `--model gpt-…`.

## Global Constraints

- Base branch `feat/codex-driver`. Work only in your own worktree. Existing tests pass unmodified.
- Checks: `make lint && make test`.
- Commit with `--no-gpg-sign` and the exact message below.

### Task 1: `CodexCliDriver` and the `codex` harnesses

**Files:** create `lab/engine/drivers/codex_cli.py`, `tests/test_codex_driver.py`; modify `lab/engine/harnesses.py`.

- [ ] **Step 1: apply this patch exactly.** Write it to a file outside the repository (for example
  `/tmp/codex-driver.patch`) in one go, then run `git apply /tmp/codex-driver.patch` from the
  repository root. Expected: no output; `git status` shows the three files.

````diff
diff --git a/lab/engine/drivers/codex_cli.py b/lab/engine/drivers/codex_cli.py
new file mode 100644
index 0000000..a8a5502
--- /dev/null
+++ b/lab/engine/drivers/codex_cli.py
@@ -0,0 +1,223 @@
+"""Codex CLI as the orchestrating harness (2026-09-30), the counterpart of ClaudeCliDriver.
+
+Same conditions as the Claude arms: the task's toolchain is reached only through the container MCP
+server (`run_in_container`, and `dispatch_blyte` when an implementer model is set), Codex's own host
+tools are switched off (shell, unified exec, JS REPL, browser, computer use, web search), and the
+operator's Codex setup is kept out: HOME and CODEX_HOME point at a fresh directory whose only
+content is a symlink to the operator's auth.json, so no config, AGENTS.md, skills or rules load
+and the credentials are never copied or read. Under a ChatGPT login Codex reports tokens but no
+cost, so the frontier cost is recorded as 0 and the tokens are kept in the metrics.
+"""
+
+from __future__ import annotations
+
+import json
+import os
+from pathlib import Path
+import shutil
+import subprocess
+import sys
+import tempfile
+import time
+from typing import Any, Optional
+import uuid
+
+from lab.benchmarks.task_loader import TaskSpec
+from lab.engine.adapters.base import AgentDriver, DriverTelemetry
+from lab.engine.drivers.claude_cli import (
+    AUTONOMY_SYSTEM_PROMPT,
+    MCP_SERVER_NAME,
+    OFFLOAD_SYSTEM_PROMPT,
+    REPO_ROOT,
+    _aggregate_dispatches,
+)
+
+DEFAULT_MODEL = "gpt-5.6-terra"
+
+# Codex's host-side tools, switched off so the container is the only place commands run.
+DISABLED_FEATURES: tuple[str, ...] = ("shell_tool", "unified_exec", "js_repl", "browser_use", "computer_use")
+
+CONTAINER_EXEC_PROMPT = (
+    "Command execution: this workspace is mounted into a Docker container that holds the "
+    "project's toolchain and dependencies. You have no shell on the host. Run every build, test "
+    "and inspection command with the `run_in_container` tool. Edit files with your file-editing "
+    "tool: the workspace directory and the container's /app are the same files."
+)
+
+
+class CodexCliDriverError(RuntimeError):
+    """Raised when the Codex CLI cannot be used."""
+
+
+def parse_events(stdout: str) -> tuple[str, dict[str, int], Optional[str], Optional[str]]:
+    """From `codex exec --json` output: the last agent message, the summed token usage, the
+    thread id, and the error of a failed turn (None when the turn completed)."""
+    text, thread, error = "", None, None
+    usage = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0, "reasoning_output_tokens": 0}
+    for line in stdout.splitlines():
+        try:
+            e = json.loads(line)
+        except ValueError:
+            continue
+        kind = e.get("type")
+        item = e.get("item") or {}
+        if kind == "thread.started":
+            thread = e.get("thread_id") or thread
+        elif kind == "item.completed" and item.get("type") == "agent_message":
+            text = str(item.get("text") or text)
+        elif kind == "turn.completed":
+            for k in usage:
+                usage[k] += int((e.get("usage") or {}).get(k) or 0)
+        elif kind == "turn.failed":
+            error = str((e.get("error") or {}).get("message") or "turn failed")
+    return text, usage, thread, error
+
+
+class CodexCliDriver(AgentDriver):
+    harness_name: str = "codex"
+    """Drives `codex exec` non-interactively."""
+
+    def __init__(
+        self,
+        model: str = DEFAULT_MODEL,
+        cli_path: Optional[str] = None,
+        reasoning_effort: str = "medium",
+        implementer_model: Optional[str] = None,
+        report_dir: Optional[Path | str] = None,
+        mcp_python: Optional[str] = None,
+        auth_file: Optional[Path | str] = None,
+    ) -> None:
+        resolved = cli_path or shutil.which("codex")
+        if not resolved or not os.access(resolved, os.X_OK):
+            raise CodexCliDriverError("The 'codex' CLI is not on PATH. Install Codex or pass cli_path=.")
+        self.cli_path = str(resolved)
+        self.model = model
+        self.reasoning_effort = reasoning_effort
+        self.implementer_model = implementer_model
+        self.report_dir = Path(report_dir) if report_dir is not None else None
+        self.mcp_python = mcp_python or sys.executable
+        self.auth_file = Path(auth_file) if auth_file else Path.home() / ".codex" / "auth.json"
+        self.last_dispatch_dir: Optional[Path] = None
+        if implementer_model is not None:
+            self.harness_name = "codex+blyte"
+
+    @property
+    def provides_isolated_execution(self) -> bool:
+        return True
+
+    @staticmethod
+    def _container_id(container: Any) -> Optional[str]:
+        if container is None:
+            return None
+        ident = getattr(container, "id", None) or getattr(container, "name", None)
+        return str(ident) if ident else None
+
+    def _home(self) -> Path:
+        """A fresh HOME/CODEX_HOME holding only a symlink to the operator's auth.json."""
+        home = Path(tempfile.mkdtemp(prefix="codex-home-"))
+        (home / ".codex").mkdir()
+        if self.auth_file.exists():
+            (home / ".codex" / "auth.json").symlink_to(self.auth_file)
+        return home
+
+    def _prompt(self, instruction: str, container_id: Optional[str]) -> str:
+        parts = [AUTONOMY_SYSTEM_PROMPT]
+        if container_id:
+            parts.append(CONTAINER_EXEC_PROMPT)
+            if self.implementer_model:
+                parts.append(OFFLOAD_SYSTEM_PROMPT)
+        return "\n\n".join(parts) + "\n\n## Task\n\n" + instruction
+
+    def _build_command(
+        self, workspace_path: Path, container_id: Optional[str], dispatch_dir: Optional[Path]
+    ) -> list[str]:
+        cmd = [
+            self.cli_path, "exec", "--json", "--skip-git-repo-check",
+            "-m", self.model,
+            "-c", f"model_reasoning_effort={self.reasoning_effort}",
+            "--sandbox", "workspace-write",
+            "-C", str(workspace_path),
+            "-c", "web_search=disabled",
+        ]
+        for feature in DISABLED_FEATURES:
+            cmd += ["--disable", feature]
+        if container_id:
+            env = {"BLYTE_EVAL_CONTAINER": container_id, "PYTHONPATH": str(REPO_ROOT)}
+            if self.implementer_model and dispatch_dir is not None:
+                env["BLYTE_IMPLEMENTER_MODEL"] = self.implementer_model
+                env["BLYTE_DISPATCH_DIR"] = str(dispatch_dir)
+            env_toml = "{" + ", ".join(f"{k}={json.dumps(v)}" for k, v in env.items()) + "}"
+            srv = f"mcp_servers.{MCP_SERVER_NAME}"
+            cmd += [
+                "-c", f"{srv}.command={json.dumps(self.mcp_python)}",
+                "-c", f'{srv}.args=["-m", "lab.engine.drivers.container_exec_mcp"]',
+                "-c", f"{srv}.cwd={json.dumps(str(REPO_ROOT))}",
+                "-c", f"{srv}.env={env_toml}",
+                "-c", f'{srv}.default_tools_approval_mode="approve"',
+            ]
+        cmd.append("-")  # the prompt comes on stdin
+        return cmd
+
+    def run(
+        self,
+        task: TaskSpec,
+        workspace_path: Path,
+        prompt_override: Optional[str] = None,
+        conversation_id: Optional[str] = None,
+        timeout_sec: float = 3600.0,
+        container: Any = None,
+    ) -> DriverTelemetry:
+        container_id = self._container_id(container)
+        dispatch_dir: Optional[Path] = None
+        if self.implementer_model:
+            name = getattr(task, "name", "task")
+            base = self.report_dir or Path(tempfile.gettempdir())
+            dispatch_dir = base / f"dispatches-{name}-{uuid.uuid4().hex[:8]}"
+            dispatch_dir.mkdir(parents=True, exist_ok=True)
+            self.last_dispatch_dir = dispatch_dir
+        cmd = self._build_command(workspace_path, container_id, dispatch_dir)
+        prompt = self._prompt(prompt_override or task.instruction, container_id)
+        home = self._home()
+        env = dict(os.environ)
+        env.update(task.env or {})
+        env.update({"HOME": str(home), "CODEX_HOME": str(home / ".codex")})
+
+        def metrics(usage: dict[str, int]) -> tuple[float, dict[str, Any]]:
+            m: dict[str, Any] = {"frontier_tokens": usage}
+            if not self.implementer_model:
+                return 0.0, m
+            implementer_cost, dispatches, outcomes = _aggregate_dispatches(dispatch_dir)
+            m.update(frontier_cost_usd=0.0, implementer_cost_usd=implementer_cost,
+                     dispatches=dispatches, dispatch_outcomes=outcomes)
+            return implementer_cost, m
+
+        started = time.monotonic()
+        try:
+            proc = subprocess.run(cmd, cwd=str(workspace_path), input=prompt, capture_output=True,
+                                  text=True, timeout=max(1.0, timeout_sec), env=env)
+        except subprocess.TimeoutExpired:
+            cost, m = metrics({})
+            t = DriverTelemetry(success=False, raw_response="", duration_seconds=time.monotonic() - started,
+                                cost_usd=cost, error_message=f"Agent turn exceeded {timeout_sec:.0f}s and was terminated",
+                                metrics=m)
+            t.extra = m  # type: ignore[attr-defined]
+            return t
+        finally:
+            shutil.rmtree(home, ignore_errors=True)
+        duration = time.monotonic() - started
+        text, usage, thread, error = parse_events(proc.stdout or "")
+        cost, m = metrics(usage)
+        failed = proc.returncode != 0 or error is not None
+        t = DriverTelemetry(
+            success=not failed,
+            raw_response=text,
+            duration_seconds=duration,
+            input_tokens=usage["input_tokens"],
+            output_tokens=usage["output_tokens"] + usage["reasoning_output_tokens"],
+            cost_usd=cost,
+            conversation_id=thread,
+            error_message=(error or (proc.stderr or "").strip()[-500:] or f"codex exited {proc.returncode}") if failed else None,
+            metrics=m,
+        )
+        t.extra = m  # type: ignore[attr-defined]
+        return t
diff --git a/lab/engine/harnesses.py b/lab/engine/harnesses.py
index b9e1756..6f6f57e 100644
--- a/lab/engine/harnesses.py
+++ b/lab/engine/harnesses.py
@@ -42,14 +42,14 @@ def parse_harness_spec(spec: str) -> tuple[str, list[str]]:
     if name == "superstate":  # renamed to blyte on 2026-09-24
         name = "blyte"
     opts = [o for o in (m.group("opts") or "").split(",") if o]
-    if name in ("agy", "claude"):
+    if name in ("agy", "claude", "codex"):
         if opts:
             raise HarnessSpecError(f"{name} takes no options, got {opts}")
         return name, opts
-    if name == "claude+blyte":
+    if name in ("claude+blyte", "codex+blyte"):
         if len(opts) != 1:
             raise HarnessSpecError(
-                f"claude+blyte requires exactly one implementer model option, got {opts}"
+                f"{name} requires exactly one implementer model option, got {opts}"
             )
         return name, opts
     if name == "blyte":
@@ -68,7 +68,7 @@ def parse_harness_spec(spec: str) -> tuple[str, list[str]]:
             raise HarnessSpecError(f"choose one fold budget, got {budgets}")
         return name, opts
     raise HarnessSpecError(
-        f"unknown harness {name!r}; known: agy, claude, claude+blyte, blyte (alias: superstate)"
+        f"unknown harness {name!r}; known: agy, claude, claude+blyte, codex, codex+blyte, blyte (alias: superstate)"
     )
 
 
@@ -105,6 +105,19 @@ def build_harness(
             implementer_model=opts[0],
             report_dir=report_dir,
         )
+    if name in ("codex", "codex+blyte"):
+        if model.startswith(("gemini", "claude", "sonnet", "opus", "haiku")):
+            raise HarnessSpecError(
+                f"{name} needs an OpenAI model, got {model!r}; compare it in a separate run "
+                "with --model gpt-…, since harnesses in one run share a model"
+            )
+        from lab.engine.drivers.codex_cli import CodexCliDriver
+
+        return CodexCliDriver(
+            model=model,
+            implementer_model=opts[0] if name == "codex+blyte" else None,
+            report_dir=report_dir,
+        )
     from lab.engine.drivers.blyte_native import BlyteNativeDriver
 
     return BlyteNativeDriver(
diff --git a/tests/test_codex_driver.py b/tests/test_codex_driver.py
new file mode 100644
index 0000000..b760963
--- /dev/null
+++ b/tests/test_codex_driver.py
@@ -0,0 +1,111 @@
+"""The Codex CLI driver: same conditions as the Claude arms, with the operator's Codex setup kept
+out (2026-09-30)."""
+
+from __future__ import annotations
+
+import json
+from pathlib import Path
+import stat
+from typing import Any
+
+import pytest
+import sys
+
+from lab.benchmarks.task_loader import TaskSpec
+from lab.engine.drivers.codex_cli import DISABLED_FEATURES, CodexCliDriver, parse_events
+from lab.engine.harnesses import HarnessSpecError, build_harness, parse_harness_spec
+
+EVENTS = "\n".join(json.dumps(e) for e in [
+    {"type": "thread.started", "thread_id": "th-1"},
+    {"type": "item.completed", "item": {"type": "agent_message", "text": "first"}},
+    {"type": "item.completed", "item": {"type": "agent_message", "text": "Done: added slugify."}},
+    {"type": "turn.completed", "usage": {"input_tokens": 100, "cached_input_tokens": 60,
+                                         "output_tokens": 20, "reasoning_output_tokens": 5}},
+])
+
+
+class FakeContainer:
+    id = "cnt-123"
+
+
+def _task(tmp_path: Path) -> TaskSpec:
+    return TaskSpec(id="org/t", name="t", instruction="Add slugify.", docker_image="img", task_dir=tmp_path)
+
+
+def _stub(tmp_path: Path) -> Path:
+    """A stand-in codex: records argv, stdin and the environment it saw, then prints EVENTS."""
+    log = tmp_path / "codex-call.json"
+    stub = tmp_path / "codex"
+    body = """#!PYTHON
+import json, os, sys
+auth = os.path.join(os.environ["CODEX_HOME"], "auth.json")
+json.dump({
+    "argv": sys.argv[1:],
+    "stdin": sys.stdin.read(),
+    "home": os.environ["HOME"],
+    "codex_home": os.environ["CODEX_HOME"],
+    "files": sorted(os.listdir(os.environ["CODEX_HOME"])),
+    "auth_link": os.readlink(auth) if os.path.islink(auth) else None,
+}, open(LOG, "w"))
+print(EVENTS)
+"""
+    # sys.executable, not /usr/bin/env python3: a pyenv shim needs the real HOME the driver replaces.
+    body = body.replace("PYTHON", sys.executable).replace("LOG", repr(str(log))).replace("EVENTS", repr(EVENTS))
+    stub.write_text(body)
+    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
+    return stub
+
+
+def test_events_give_the_last_message_the_usage_and_the_thread() -> None:
+    text, usage, thread, error = parse_events(EVENTS)
+    assert (text, thread, error) == ("Done: added slugify.", "th-1", None)
+    assert usage == {"input_tokens": 100, "cached_input_tokens": 60, "output_tokens": 20,
+                     "reasoning_output_tokens": 5}
+    failed = json.dumps({"type": "turn.failed", "error": {"message": "model not supported"}})
+    assert parse_events(failed)[3] == "model not supported"
+
+
+def test_the_host_tools_are_off_and_the_container_server_is_approved(tmp_path: Path) -> None:
+    d = CodexCliDriver(cli_path=str(_stub(tmp_path)), implementer_model="gemini-3.8-flash-high")
+    cmd = d._build_command(tmp_path, "cnt-123", tmp_path / "dispatches")
+    for feature in DISABLED_FEATURES:
+        i = cmd.index(feature)
+        assert cmd[i - 1] == "--disable"
+    assert "web_search=disabled" in cmd
+    joined = " ".join(cmd)
+    assert 'mcp_servers.task.default_tools_approval_mode="approve"' in joined
+    assert '"BLYTE_EVAL_CONTAINER"' not in joined  # TOML keys are bare
+    assert 'BLYTE_EVAL_CONTAINER="cnt-123"' in joined
+    assert 'BLYTE_IMPLEMENTER_MODEL="gemini-3.8-flash-high"' in joined
+    assert cmd[-1] == "-"
+    plain = CodexCliDriver(cli_path=str(_stub(tmp_path)))._build_command(tmp_path, "cnt-123", None)
+    assert "BLYTE_IMPLEMENTER_MODEL" not in " ".join(plain)
+
+
+def test_a_run_uses_a_fresh_home_with_only_the_auth_symlink(tmp_path: Path) -> None:
+    auth = tmp_path / "real-auth.json"
+    auth.write_text("{}")
+    d = CodexCliDriver(cli_path=str(_stub(tmp_path)), implementer_model="gemini-3.8-flash-high",
+                       report_dir=tmp_path / "reports", auth_file=auth)
+    t = d.run(_task(tmp_path), tmp_path, container=FakeContainer())
+    call: dict[str, Any] = json.loads((tmp_path / "codex-call.json").read_text())
+    assert call["home"] != str(Path.home())
+    assert call["files"] == ["auth.json"]
+    assert call["auth_link"] == str(auth)
+    assert not Path(call["home"]).exists(), "the scratch home is removed after the run"
+    assert "run_in_container" in call["stdin"] and "dispatch_blyte" in call["stdin"]
+    assert call["stdin"].endswith("## Task\n\nAdd slugify.")
+    assert t.success and t.raw_response == "Done: added slugify."
+    assert t.conversation_id == "th-1"
+    assert t.metrics["frontier_tokens"]["cached_input_tokens"] == 60
+    assert t.metrics["dispatches"] == 0 and t.metrics["frontier_cost_usd"] == 0.0
+    assert d.harness_name == "codex+blyte"
+
+
+def test_codex_harness_specs() -> None:
+    assert parse_harness_spec("codex") == ("codex", [])
+    assert parse_harness_spec("codex+blyte[gemini-3.8-flash-high]") == ("codex+blyte", ["gemini-3.8-flash-high"])
+    with pytest.raises(HarnessSpecError):
+        parse_harness_spec("codex+blyte")
+    with pytest.raises(HarnessSpecError):
+        build_harness("codex", "sonnet")
````

- [ ] **Step 2:** `.venv/bin/python -m pytest -q tests/test_codex_driver.py`. Expected: 4 passed.

- [ ] **Step 3: run the checks and commit.** `make lint && make test`. Expected: both pass.

```bash
git add lab/engine/drivers/codex_cli.py tests/test_codex_driver.py lab/engine/harnesses.py
git commit --no-gpg-sign -m "feat(eval): a Codex CLI driver, and the codex and codex+blyte harnesses"
```
