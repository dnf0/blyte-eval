"""Produce real gate-failure outputs by breaking throwaway copies of blyte (Rust) and blyte-eval (Python)
on purpose, running the real check commands, and recording what they print, formatted as blyte's gate
reports them. Each case carries the label it was built to have: code, environment or flaky."""
import json, os, subprocess, tempfile, shutil

SP = os.path.dirname(os.path.abspath(__file__))
RS, PY = f"{SP}/faults/rs", f"{SP}/faults/py"
OUT = f"{SP}/gate_cases.jsonl"
BASE_ENV = dict(os.environ)
DENY_NET = "(version 1)(allow default)(deny network-outbound (remote ip))"


def reset(repo):
    subprocess.run(["git", "checkout", "-q", "--", "."], cwd=repo, check=True)
    subprocess.run(["git", "clean", "-qfd", "-e", "target", "-e", ".venv"], cwd=repo, check=True)


def append(repo, path, text):
    with open(f"{repo}/{path}", "a") as f:
        f.write(text)


def replace(repo, path, old, new):
    p = f"{repo}/{path}"
    s = open(p).read()
    assert old in s, (path, old)
    open(p, "w").write(s.replace(old, new, 1))


def bound(text, lines=400):
    # blyte keeps the head and tail of long command output
    ls = text.splitlines()
    if len(ls) > lines:
        ls = ls[: lines // 2] + [f"... [{len(ls) - lines} lines cut] ..."] + ls[-lines // 2 :]
    return "\n".join(ls)[:60000]


def run(repo, cmd, env=None, timeout=900):
    e = dict(BASE_ENV)
    e.update(env or {})
    try:
        # A PATH override needs a shell that does not reload the login profile (which restores it).
        shell = ["bash", "--noprofile", "--norc", "-c"] if env and "PATH" in env else ["bash", "-lc"]
        p = subprocess.run(shell + [cmd], cwd=repo, env=e, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr)
    except subprocess.TimeoutExpired as t:
        out = (t.stdout or b"").decode(errors="replace") if isinstance(t.stdout, bytes) else (t.stdout or "")
        err = (t.stderr or b"").decode(errors="replace") if isinstance(t.stderr, bytes) else (t.stderr or "")
        return 124, out + err + f"\n[killed by blyte after 1800s]"


cases = []


def case(cid, label, repo, cmd, setup=None, env=None, timeout=900, teardown=None):
    reset(repo)
    if setup:
        setup()
    code, out = run(repo, cmd, env, timeout)
    if teardown:
        teardown()
    reset(repo)
    text = f"exit {code}\n{bound(out.strip())}"
    cases.append({"id": cid, "label": label, "cmd": cmd, "exit": code, "text": text})
    print(f"{cid:22} {label:12} exit {code:4}  {out.strip().splitlines()[-1][:90] if out.strip() else '(no output)'}")


# ---- code: the change is wrong -------------------------------------------------------------
case("rs-assert", "code", RS, "cargo test -q -p blyte-agent --test test_gate_slots_nesting",
     lambda: replace(RS, "crates/blyte-agent/tests/test_gate_slots_nesting.rs",
                     "assert_eq!(outcome, Outcome::Verified);", "assert_eq!(outcome, Outcome::BudgetExhausted);"))
case("rs-compile", "code", RS, "cargo test -q -p blyte-agent --lib",
     lambda: append(RS, "crates/blyte-agent/src/state.rs", '\npub fn broken() -> u32 {\n    "a"\n}\n'))
case("rs-clippy", "code", RS, "cargo clippy -q -p blyte-agent -- -D warnings",
     lambda: append(RS, "crates/blyte-agent/src/state.rs", "\npub fn lint_me(v: &Vec<u32>) -> bool {\n    v.len() == 0\n}\n"))
case("rs-fmt", "code", RS, "cargo fmt --all --check",
     lambda: append(RS, "crates/blyte-agent/src/state.rs", "\npub fn  ugly( )->u32{1}\n"))
case("rs-borrow", "code", RS, "cargo build -q -p blyte-agent",
     lambda: append(RS, "crates/blyte-agent/src/state.rs",
                    "\npub fn moved() -> usize {\n    let v = vec![1];\n    let w = v;\n    v.len() + w.len()\n}\n"))
case("py-assert", "code", PY, "uv run -q pytest -q tests/test_plan_first.py",
     lambda: replace(PY, "tests/test_plan_first.py", "assert final_response(tmp_path) is None",
                     "assert final_response(tmp_path) is not None"))
case("py-ruff", "code", PY, "uv run -q ruff check lab/engine/plan_first.py",
     lambda: replace(PY, "lab/engine/plan_first.py", "import json\n", "import json\nimport os\n"))
case("py-import", "code", PY, "uv run -q pytest -q tests/test_plan_first.py",
     lambda: replace(PY, "lab/engine/plan_first.py", "import json\n", "import json\nfrom lab.engine.nonexistent import thing\n"))
case("py-syntax", "code", PY, "uv run -q pytest -q tests/test_plan_first.py",
     lambda: append(PY, "lab/engine/plan_first.py", "\ndef broken(:\n    pass\n"))
case("py-type", "code", PY, "uv run -q pyright lab/engine/plan_first.py",
     lambda: append(PY, "lab/engine/plan_first.py", '\nWRONG: int = "a"\n'))
case("py-typeerror", "code", PY, "uv run -q pytest -q tests/test_plan_first.py",
     lambda: replace(PY, "lab/engine/plan_first.py", 'instruction=f"{PLANNING_PROMPT}', 'instruction=len(PLANNING_PROMPT) + f"{PLANNING_PROMPT}'))

# ---- environment: the machine or setup is at fault --------------------------------------------
case("rs-no-cargo", "environment", RS, "cargo test -q -p blyte-agent", env={"PATH": "/usr/bin:/bin"})
case("py-no-uv", "environment", PY, "uv run -q pytest -q", env={"PATH": "/usr/bin:/bin"})
nohome = tempfile.mkdtemp(prefix="cargohome-")
case("rs-no-network", "environment", RS, f"sandbox-exec -p '{DENY_NET}' cargo fetch", env={"CARGO_HOME": nohome}, timeout=300)
case("py-no-network", "environment", PY,
     f"sandbox-exec -p '{DENY_NET}' uv pip install --python .venv/bin/python --no-cache 'httpx==0.28.1' 'rich==14.1.0'",
     env={"UV_CACHE_DIR": tempfile.mkdtemp(prefix="uvcache-")}, timeout=300)
ro = tempfile.mkdtemp(prefix="ro-target-")
os.chmod(ro, 0o555)
case("rs-permission", "environment", RS, "cargo build -q -p blyte-agent", env={"CARGO_TARGET_DIR": f"{ro}/t"})
os.chmod(ro, 0o755)
dmg = f"{SP}/faults/tiny.dmg"
subprocess.run(["hdiutil", "create", "-quiet", "-size", "3m", "-fs", "HFS+", "-volname", "blytetiny", "-ov", dmg], check=True)
subprocess.run(["hdiutil", "attach", "-quiet", "-nobrowse", "-mountpoint", f"{SP}/faults/tiny", dmg], check=True)
case("rs-disk-full", "environment", RS, "cargo build -q -p blyte-agent", env={"CARGO_TARGET_DIR": f"{SP}/faults/tiny/t"})
case("py-disk-full", "environment", PY, "uv run -q pytest -q tests/test_plan_first.py",
     setup=lambda: append(PY, "tests/test_plan_first.py",
                          f"\n\ndef test_writes_report(tmp_path: Path) -> None:\n    open('{SP}/faults/tiny/report.bin', 'wb').write(b'x' * 8_000_000)\n"))
subprocess.run(["hdiutil", "detach", "-quiet", f"{SP}/faults/tiny"], check=False)
case("py-db-down", "environment", PY, "uv run -q pytest -q tests/test_db_service.py",
     setup=lambda: open(f"{PY}/tests/test_db_service.py", "w").write(
         "import socket\n\n\ndef test_can_query_database() -> None:\n    conn = socket.create_connection(('127.0.0.1', 5999), timeout=2)\n    conn.close()\n"))
case("docker-down", "environment", PY, "docker ps", env={"DOCKER_HOST": "unix:///tmp/blyte-no-docker.sock"})
case("aws-profile", "environment", PY, "aws sts get-caller-identity", env={"AWS_PROFILE": "blyte-no-such-profile"})

# ---- flaky: would likely pass on retry --------------------------------------------------------
case("rs-timeout", "flaky", RS, "cargo test -p blyte-agent", env={"CARGO_TARGET_DIR": f"{SP}/faults/rs/target-slow"}, timeout=8)
case("py-net-timeout", "flaky", PY, "uv run -q pytest -q tests/test_http_fixture.py",
     setup=lambda: open(f"{PY}/tests/test_http_fixture.py", "w").write(
         "import urllib.request\n\n\ndef test_fetches_fixture() -> None:\n    urllib.request.urlopen('http://10.255.255.1/fixture.json', timeout=2).read()\n"))

with open(OUT, "w") as f:
    for c in cases:
        f.write(json.dumps(c) + "\n")
shutil.rmtree(f"{SP}/faults/rs/target-slow", ignore_errors=True)
print(f"{len(cases)} cases -> {OUT}")
