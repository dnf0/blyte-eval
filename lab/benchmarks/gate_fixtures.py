"""Hand-authored agent-facing verification gates, one per benchmark task.

WHY THESE EXIST
---------------
The gate is what defines "done" for the worker: the turnkey prompt tells it to stop the
moment the gate exits 0. That makes the gate the single highest-leverage variable in a run.

Deriving it from the task instruction with an LLM turn made it a *random variable*. The
spec is a constant -- the same instruction every run -- but the contract synthesised from
it was not. For `fastapi-deprecation-response-headers` two runs produced:

    run A: a full functional check of headers, OpenAPI schema and middleware stats
    run B: test -f fastapi/middleware/deprecation.py && [ "$(git branch --show-current)" != "main" ]

Run B is satisfied by `touch`. With the contract varying that wildly between runs, no two
runs measure the same task, and arm-vs-arm comparison is meaningless -- the gate moves more
than the thing under test.

These fixtures make the contract a constant, so a run is reproducible and the comparison
measures the execution model rather than how well an LLM happened to invent a spec that
day. It also mirrors real use, where a human writes `verify_cmd` once, deliberately.

CONTRACT FOR ENTRIES
--------------------
Each gate must:
  * exit 0 only when every requirement the instruction states is met;
  * FAIL before any work has been done (a gate that already passes cannot discriminate);
  * never read `/tests/`, which holds the sealed grader -- that is the answer key, and
    gating on it would let the agent read what it is scored against;
  * run through `./run-in-container` when it needs the project environment.

These are deliberately derived from the instruction text alone, never from the sealed
grader, so they remain a fair statement of the task rather than a leak of its tests.
"""

from __future__ import annotations

import re
from typing import Optional

# The sealed grader lives at `/tests/` in the container ROOT. A package's own suite at
# `/app/<pkg>/tests/` is a legitimate gate and must not be confused with it -- a plain
# `"/tests/" in cmd` substring test rejects exactly the gate build-cython-ext needs,
# since its instruction explicitly asks for the repository's own tests to keep passing.
SEALED_GRADER_RE = re.compile(r"(?:^|[\s;&|(<'\"])/tests/|(?:^|[\s;&|(])bash\s+/tests\b")


def references_sealed_grader(command: Optional[str]) -> bool:
    """Whether a command reads the sealed held-out grader at the container root."""
    if not command:
        return False
    return bool(SEALED_GRADER_RE.search(command))

# Keyed by task directory name (TaskSpec.name), not the fully qualified id.
GATE_FIXTURES: dict[str, str] = {
    # "create a JSON file in /app/recover.json ... [{"word": ..., "value": ...}, ...]"
    "sqlite-db-truncate": (
        "./run-in-container python3 -c \""
        "import json;"
        "d=json.load(open('/app/recover.json'));"
        "assert isinstance(d,list) and len(d)>0, 'recover.json must be a non-empty list';"
        "assert all(isinstance(r,dict) and 'word' in r and 'value' in r for r in d), 'each row needs word and value';"
        "assert all(isinstance(r['word'],str) and isinstance(r['value'],int) for r in d), 'word:str, value:int'"
        '"'
    ),
    # "recover all 11 records ... sorted by id ... [{"id":..,"name":..,"value":..}, ...]"
    "db-wal-recovery": (
        "./run-in-container python3 -c \""
        "import json;"
        "d=json.load(open('/app/recovered.json'));"
        "assert isinstance(d,list), 'recovered.json must be a list';"
        "assert len(d)==11, f'expected 11 records, got {len(d)}';"
        "assert all(isinstance(r,dict) and {'id','name','value'} <= set(r) for r in d), 'each row needs id, name, value';"
        "ids=[r['id'] for r in d];"
        "assert ids==sorted(ids), 'records must be sorted by id'"
        '"'
    ),
    # 2048-bit key at 600, cert with the stated O/CN valid 365 days, combined PEM, and a
    # verification.txt carrying subject and validity dates.
    "openssl-selfsigned-cert": (
        "./run-in-container sh -c '"
        "test -d /app/ssl && "
        "test -f /app/ssl/server.key && "
        '[ "$(stat -c %a /app/ssl/server.key)" = "600" ] && '
        "openssl rsa -in /app/ssl/server.key -noout -check >/dev/null 2>&1 && "
        "openssl rsa -in /app/ssl/server.key -noout -text 2>/dev/null | grep -qE \"2048 bit|Private-Key: \\(2048\" && "
        "openssl x509 -in /app/ssl/server.crt -noout -subject 2>/dev/null | grep -q \"DevOps Team\" && "
        "openssl x509 -in /app/ssl/server.crt -noout -subject 2>/dev/null | grep -q \"dev-internal.company.local\" && "
        "grep -q \"PRIVATE KEY\" /app/ssl/server.pem && "
        "grep -q \"CERTIFICATE\" /app/ssl/server.pem && "
        "test -s /app/ssl/verification.txt && "
        "grep -qi \"dev-internal.company.local\" /app/ssl/verification.txt"
        "'"
    ),
    # The README snippet must run, the compiled extensions must import, and the package's
    # own suite must still pass -- excluding the two files the instruction names as dead.
    "build-cython-ext": (
        "./run-in-container sh -c '"
        "python -c \"import pyknotid; "
        "from pyknotid.spacecurves import chelpers, ccomplexity; "
        "from pyknotid import cinvariants; "
        "import pyknotid.make as mk; import pyknotid.spacecurves as sp; "
        "k = sp.Knot(mk.three_twist(num_points=100)); k.alexander_polynomial(-1)\" && "
        "python -m pytest /app/pyknotid/tests "
        "--ignore=/app/pyknotid/tests/test_random_curves.py "
        "--ignore=/app/pyknotid/tests/test_catalogue.py -q"
        "'"
    ),
    # Features 1-5 of the instruction: Deprecation/Sunset/Link headers, the OpenAPI
    # x-* extensions, the tracking middleware, and header preservation with Link merging.
    "fastapi-deprecation-response-headers": (
        "./run-in-container python -c \""
        "import datetime as dt;"
        "from fastapi import FastAPI, APIRouter;"
        "from fastapi.testclient import TestClient;"
        "from starlette.responses import JSONResponse;"
        "from fastapi.middleware.deprecation import DeprecationTrackingMiddleware;"
        "d=dt.datetime(2035,1,1,tzinfo=dt.timezone.utc);"
        "app=FastAPI();"
        "app.get('/a', deprecated=True)(lambda: {'ok':1});"
        "app.get('/b', sunset=d, successor_url='/v2')(lambda: {'ok':2});"
        "app.get('/c', deprecation_date=d)(lambda: {'ok':3});"
        "app.get('/d', deprecated=True)(lambda: JSONResponse({'ok':4}, headers={'deprecation':'keep-me'}));"
        "r=APIRouter(deprecated=True); r.get('/e')(lambda: {'ok':5}); app.include_router(r);"
        "mw=DeprecationTrackingMiddleware(app); c=TestClient(mw);"
        "assert c.get('/a').headers.get('deprecation')=='true', 'F1: deprecated=True must emit Deprecation: true';"
        "hb=c.get('/b').headers;"
        "assert 'sunset' in hb, 'F1: sunset must emit a Sunset header';"
        "assert 'successor-version' in hb.get('link',''), 'F3: successor_url must emit Link rel=successor-version';"
        "hc=c.get('/c').headers;"
        "assert hc.get('deprecation') not in (None,'true'), 'F2: deprecation_date must emit a date, not true';"
        "assert c.get('/d').headers.get('deprecation')=='keep-me', 'F5: an existing Deprecation header must be preserved';"
        "assert c.get('/e').headers.get('deprecation')=='true', 'F1: router-level deprecated=True must apply';"
        "s=app.openapi()['paths']['/b']['get'];"
        "assert 'x-sunset' in s and 'x-successor-url' in s, 'F1/F3: OpenAPI must carry x-sunset and x-successor-url';"
        "assert 'x-deprecation-date' in app.openapi()['paths']['/c']['get'], 'F2: OpenAPI must carry x-deprecation-date';"
        "st=mw.get_stats();"
        "assert st['/a']['deprecated_hits']==1, 'F4: middleware must count deprecated hits';"
        "assert st['/b']['sunset_hits']==1, 'F4: middleware must count sunset hits';"
        "mw.reset_stats();"
        "assert not mw.get_stats().get('/a',{}).get('deprecated_hits',0), 'F4: reset_stats must clear counters'"
        '"'
    ),
    # Response.iter_multipart() parsing two parts, MultipartPart type, header access,
    # and DecodingError on a non-multipart response.
    # Validated in-container: fails pre-implementation with
    #   AttributeError: 'Response' object has no attribute 'iter_multipart'
    "httpx-multipart-response-parsing": """cat <<'GATEEOF' | ./run-in-container python -
import httpx
body = (b"preamble\\r\\n--BB\\r\\nContent-Type: text/plain\\r\\nX-A: 1\\r\\n\\r\\nhello\\r\\n"
        b"--BB\\r\\nContent-Type: application/json\\r\\n\\r\\n{}\\r\\n--BB--\\r\\nepilogue")
r = httpx.Response(200, headers={"Content-Type": 'multipart/mixed; boundary="BB"'}, content=body)
parts = list(r.iter_multipart())
assert len(parts) == 2, f"expected 2 parts, got {len(parts)}"
assert isinstance(parts[0], httpx.MultipartPart)
assert parts[0].content == b"hello", parts[0].content
assert parts[0].headers["x-a"] == "1"
assert parts[1].content == b"{}"
bad = httpx.Response(200, headers={"Content-Type": "text/plain"}, content=b"x")
try:
    list(bad.iter_multipart())
except httpx.DecodingError:
    pass
else:
    raise AssertionError("non-multipart must raise DecodingError")
GATEEOF""",
    # State(data=...) lifecycle: init on entry, removal on exit, reset on re-entry,
    # per-instance storage, DataVar defaults, get/set accessors.
    # Validated in-container: fails pre-implementation with
    #   ImportError: cannot import name 'DataVar' from 'statemachine'
    "python-statemachine-state-data-scoping": """cat <<'GATEEOF' | ./run-in-container python -
from statemachine import State, StateMachine, DataVar

class M(StateMachine):
    idle = State(initial=True, data={"count": 0, "items": list})
    busy = State(data={"n": DataVar(default=5)})
    go = idle.to(busy)
    back = busy.to(idle)

m = M()
assert m.get_state_data(m.idle) == {"count": 0, "items": []}
m.go()
assert m.get_state_data(m.idle) is None, "data must be removed on exit"
assert m.get_state_data(m.busy) == {"n": 5}
m.back()
assert m.get_state_data(m.idle)["count"] == 0, "re-entry must reset to defaults"
assert M().get_state_data(M().idle)["count"] == 0, "data must be per instance"
assert isinstance(m.state_data_values, dict)
m.set_state_data(m.idle, "count", 3)
assert m.get_state_data(m.idle)["count"] == 3
GATEEOF""",
    # Bounded-memory mode: byte-identical json output vs unbounded, a non-empty spill
    # file left in the configured dir, and the stats line with spills/peak fields.
    # Validated in-container: exits 1 pre-implementation (flags unrecognised).
    "scc-bounded-memory-spilling": """cat <<'GATEEOF' | ./run-in-container sh -s
set -e
cd /app
go build -o /tmp/sccgate .
mkdir -p /tmp/sccsrc && for i in 1 2 3 4 5; do printf 'package p\\nfunc F%s() {}\\n' "$i" > /tmp/sccsrc/f$i.go; done
rm -rf /tmp/sccspill && mkdir -p /tmp/sccspill
/tmp/sccgate --format-multi json:/tmp/unbounded.json /tmp/sccsrc
/tmp/sccgate --bounded-memory --bounded-memory-dir /tmp/sccspill \\
  --bounded-memory-max-in-memory-files 1 --bounded-memory-stats \\
  --format-multi json:/tmp/bounded.json /tmp/sccsrc 2>/tmp/sccstats
cmp -s /tmp/unbounded.json /tmp/bounded.json
grep -q '^bounded-memory:' /tmp/sccstats
grep -qE 'spills=[1-9][0-9]*' /tmp/sccstats
grep -qE 'peak_in_memory_files=[0-9]+' /tmp/sccstats
test -n "$(find /tmp/sccspill -type f -size +0c | head -1)"
GATEEOF""",
}


def agent_gate_for(task_name: str) -> Optional[str]:
    """Return the hand-authored agent-facing gate for a task, if one exists.

    This is deliberately NOT `TaskSpec.verification_cmd`: that field holds the sealed
    held-out grader and is what `extractor.py` runs to decide pass/fail. Overwriting it
    would grade the agent against the very contract it was handed, which would inflate
    every score. The two must stay separate -- this gate steers the agent, that one
    judges it.
    """
    return GATE_FIXTURES.get(task_name)
