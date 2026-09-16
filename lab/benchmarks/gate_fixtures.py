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
    # Every clause is stated in the instruction: numpy 2.x compatibility, the /app/pyknotid
    # clone location, the three named extensions being *compiled* ("the compiled extensions
    # ... should work in their original context"), the README snippet, and the repository's
    # own suite minus the two files the instruction names as dead.
    #
    # The earlier version checked only that the extensions imported. A pure-Python fallback
    # satisfies that, so the daemon reached `status: completed` with its retry loop working
    # correctly and still failed the grader -- the contract was narrower than the job.
    "build-cython-ext": """cat <<'GATEEOF' | ./run-in-container sh -s
set -e
python - <<'PYEOF'
import numpy, os
assert numpy.__version__.startswith("2."), f"needs numpy 2.x, got {numpy.__version__}"
assert os.path.isdir("/app/pyknotid"), "source must be cloned to /app/pyknotid"
import pyknotid
from pyknotid.spacecurves import chelpers, ccomplexity
from pyknotid import cinvariants
for m in (chelpers, ccomplexity, cinvariants):
    f = getattr(m, "__file__", "") or ""
    assert f.endswith((".so", ".pyd")), f"{m.__name__} is not a compiled extension: {f}"
import pyknotid.make as mk, pyknotid.spacecurves as sp
k = sp.Knot(mk.three_twist(num_points=100))
assert k.alexander_polynomial(-1) is not None
PYEOF
python -m pytest /app/pyknotid/tests \\
  --ignore=/app/pyknotid/tests/test_random_curves.py \\
  --ignore=/app/pyknotid/tests/test_catalogue.py -q
GATEEOF""",
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
    # Typed declarations parse and execute under TypedBindings, mismatched assignment is a
    # "type error" naming the variable, nil into a primitive errors, and both the disabled
    # option and untyped `var` stay dynamic. Tested through a throwaway module that
    # `replace`s the package to /app, so the repo the grader diffs is never written to.
    # Validated in-container: fails to compile pre-implementation --
    #   unknown field TypedBindings in struct literal of type vm.Options
    "anko-typed-variable-bindings": """cat <<'GATEEOF' | ./run-in-container sh -s
set -e
rm -rf /tmp/ankogate && mkdir -p /tmp/ankogate && cd /tmp/ankogate
cat > go.mod <<'EOM'
module ankogate
go 1.21
require github.com/mattn/anko v0.0.0
replace github.com/mattn/anko => /app
EOM
cat > main.go <<'EOM'
package main

import (
	"log"
	"strings"

	"github.com/mattn/anko/env"
	"github.com/mattn/anko/vm"
)

func run(src string, typed bool) (interface{}, error) {
	return vm.Execute(env.NewEnv(), &vm.Options{TypedBindings: typed}, src)
}

func main() {
	if v, err := run("var x: int64 = 10\nx", true); err != nil || v == nil {
		log.Fatalf("typed declaration failed: %v", err)
	}
	if _, err := run("var a, b: int64 = 1, 2\na", true); err != nil {
		log.Fatalf("multi typed declaration failed: %v", err)
	}
	_, err := run("var y: int64 = 1\ny = \"s\"", true)
	if err == nil {
		log.Fatal("type mismatch must error when TypedBindings is enabled")
	}
	if !strings.Contains(err.Error(), "type error") || !strings.Contains(err.Error(), "y") {
		log.Fatalf("error must contain 'type error' and the variable name, got: %v", err)
	}
	if _, err := run("var n: int64 = 1\nn = nil", true); err == nil {
		log.Fatal("nil assignment to a primitive must error")
	}
	if _, err := run("var z: int64 = 1\nz = \"s\"", false); err != nil {
		log.Fatalf("TypedBindings disabled must behave dynamically, got: %v", err)
	}
	if _, err := run("var q = 1\nq = \"s\"", true); err != nil {
		log.Fatalf("untyped declaration must stay dynamic, got: %v", err)
	}
}
EOM
go run .
GATEEOF""",
    # try()/throw()/errtype()/retry and the block form with catch and finally, plus arity
    # enforcement. Same throwaway-module approach as anko.
    # Validated in-container: exits 1 pre-implementation (try/throw/retry unparseable).
    "expr-try-catch-errors": """cat <<'GATEEOF' | ./run-in-container sh -s
set -e
rm -rf /tmp/exprgate && mkdir -p /tmp/exprgate && cd /tmp/exprgate
cat > go.mod <<'EOM'
module exprgate
go 1.21
require github.com/expr-lang/expr v0.0.0
replace github.com/expr-lang/expr => /app
EOM
cat > main.go <<'EOM'
package main

import (
	"log"

	"github.com/expr-lang/expr"
)

func evalOK(src string, want any) {
	got, err := expr.Eval(src, nil)
	if err != nil {
		log.Fatalf("%s: unexpected error: %v", src, err)
	}
	if got != want {
		log.Fatalf("%s: got %v, want %v", src, got, want)
	}
}

func main() {
	evalOK(`try(1/0, "fallback")`, "fallback")
	evalOK(`try(6*7, "fallback")`, 42)
	evalOK(`try(throw("boom"), "caught")`, "caught")
	evalOK(`try { throw("boom") } catch e { errtype(e) }`, "custom")
	evalOK(`errtype(nil)`, "none")
	evalOK(`try { 1/0 } catch { "handled" }`, "handled")
	evalOK(`try { 1 } catch { 2 } finally { 3 }`, 1)
	if _, err := expr.Eval(`try(1)`, nil); err == nil {
		log.Fatal("try requires exactly two arguments")
	}
	if _, err := expr.Eval(`throw()`, nil); err == nil {
		log.Fatal("throw requires exactly one argument")
	}
	if _, err := expr.Eval(`retry`, nil); err == nil {
		log.Fatal("retry outside a catch block must error")
	}
}
EOM
go run .
GATEEOF""",
    # `using` / `await using` declarations under next:true, the no-line-terminator rule, and
    # the five required error substrings. The image's own `npm run build` is broken (rollup
    # cannot parse the TS source), so the gate bundles with esbuild instead -- otherwise it
    # would fail on tooling rather than on the feature.
    # Validated in-container: fails pre-implementation with
    #   Error: [1:6-1:7]: Unexpected token: 'identifier'
    # which is exactly the pre-feature behaviour the instruction describes.
    "meriyah-explicit-resource-declarations": """cat <<'GATEEOF' | ./run-in-container sh -s
set -e
cd /app
npx --no-install esbuild src/meriyah.ts --bundle --platform=node --format=cjs --outfile=/tmp/meriyah_gate.cjs >/dev/null
node -e '
const { parseScript, parseModule } = require("/tmp/meriyah_gate.cjs");
const d = parseModule("using x = null;", { next: true }).body[0];
if (d.type !== "VariableDeclaration" || d.kind !== "using")
  throw new Error("expected VariableDeclaration kind=using, got " + d.type + "/" + d.kind);
if (parseModule("await using y = null;", { next: true }).body[0].kind !== "await using")
  throw new Error("expected kind=await using");
if (parseModule("using\nx = null;", { next: true }).body[0].kind === "using")
  throw new Error("a line break must stop using being a declaration");
const mustThrow = (src, needle, parse) => {
  let msg = null;
  try { (parse || parseModule)(src, { next: true }); } catch (e) { msg = e.message; }
  if (msg === null) throw new Error("expected a parse error for: " + src);
  if (!msg.includes(needle))
    throw new Error(src + ": expected " + JSON.stringify(needle) + " got " + JSON.stringify(msg));
};
mustThrow("using x = null;", "not allowed in the global scope", parseScript);
mustThrow("await using z = null;", "only allowed inside async", parseScript);
mustThrow("using x;", "must have an initializer");
mustThrow("for (using x in {}) {}", "not allowed in for-in");
mustThrow("using {a} = {};", "cannot have destructuring");
'
GATEEOF""",
    # \multicolumn in array-like environments, MathML columnspan/columnalign, and ParseError
    # for every invalid form the instruction lists. The image ships no esbuild and the source
    # entry is katex.ts, so the gate runs the project's own jest with --roots pointing OUTSIDE
    # /app: the test never lands in the repository the grader diffs.
    # Validated in-container: exits 1 pre-implementation, with the two rendering assertions
    # failing because \multicolumn is unknown.
    "katex-multicolumn-array-spans": r"""cat <<'GATEEOF' | ./run-in-container sh -s
set -e
mkdir -p /tmp/gate
cat > /tmp/gate/katex.test.js <<'JSEOF'
const mod = require("/app/katex.ts");
const katex = mod.default || mod;

const render = (tex) => katex.renderToString(tex, { throwOnError: true });
const mustThrow = (tex, why) => {
  let threw = false;
  try { render(tex); } catch (e) { threw = true; }
  if (!threw) throw new Error("expected ParseError: " + why + "  [" + tex + "]");
};

test("multicolumn renders in array-like environments", () => {
  const html = render("\\begin{array}{cc}\\multicolumn{2}{c}{x}\\end{array}");
  expect(html).toEqual(expect.stringContaining("columnspan"));
  for (const env of ["matrix", "pmatrix", "bmatrix", "cases", "aligned", "smallmatrix"]) {
    render(`\\begin{${env}}\\multicolumn{1}{c}{x}\\end{${env}}`);
  }
});

test("multicolumn emits MathML columnspan and columnalign", () => {
  const html = render("\\begin{array}{ccc}\\multicolumn{2}{r}{x}&y\\end{array}");
  expect(html).toEqual(expect.stringContaining("columnspan"));
  expect(html).toEqual(expect.stringContaining("columnalign"));
});

test("invalid multicolumn is a ParseError", () => {
  mustThrow("\\begin{array}{cc}\\multicolumn{0}{c}{x}\\end{array}", "n < 1");
  mustThrow("\\begin{array}{cc}\\multicolumn{1.5}{c}{x}\\end{array}", "non-integer n");
  mustThrow("\\begin{array}{cc}\\multicolumn{3}{c}{x}\\end{array}", "n exceeds remaining columns");
  mustThrow("\\begin{array}{cc}\\multicolumn{1}{q}{x}\\end{array}", "invalid alignment");
  mustThrow("\\begin{array}{cc}\\multicolumn{1}{cc}{x}\\end{array}", "more than one alignment char");
  mustThrow("\\multicolumn{1}{c}{x}", "used outside an array-like environment");
});
JSEOF
cd /app
npx --no-install jest --rootDir /app --roots /tmp/gate --testMatch "**/*.test.js"
GATEEOF""",
    # dependentRequired / dependentSchemas, local $ref with recursion, the two exact error
    # messages the instruction specifies, if/then/else, and deep enum equality.
    #
    # @ark/json-schema resolves to out/index.js, which does not exist until the monorepo is
    # built, so the gate runs `pnpm build` first (verified working in the image, unlike
    # meriyah's). Mocha needs --no-config or the project's own spec glob pulls in the whole
    # suite, and NODE_PATH so a test outside /app can still resolve the workspace packages.
    # Validated in-container: exits 5 pre-implementation (0 passing, 5 failing).
    "arktype-json-schema-refs-dependencies": r"""cat <<'GATEEOF' | ./run-in-container sh -s
set -e
cd /app
pnpm build >/dev/null 2>&1
mkdir -p /tmp/gate
cat > /tmp/gate/ark.test.ts <<'TSEOF'
import { jsonSchemaToType } from "@ark/json-schema"

const t = (schema: unknown) => jsonSchemaToType(schema as never)
const mustReject = (schema: unknown, needle: string) => {
	let msg = ""
	try { t(schema) } catch (e) { msg = String((e as Error).message) }
	if (!msg) throw new Error("expected a rejection for " + JSON.stringify(schema))
	if (!msg.includes(needle))
		throw new Error("expected " + JSON.stringify(needle) + " got " + JSON.stringify(msg))
}

describe("json-schema refs and dependencies", () => {
	it("dependentRequired requires dependent keys when the trigger is present", () => {
		const T = t({ type: "object", dependentRequired: { a: ["b"] } })
		if (T.allows({ a: 1 } as never)) throw new Error("a without b must fail")
		if (!T.allows({ a: 1, b: 2 } as never)) throw new Error("a with b must pass")
		if (!T.allows({ b: 2 } as never)) throw new Error("no trigger means no requirement")
	})

	it("dependentSchemas validates against the schema when the trigger is present", () => {
		const T = t({
			type: "object",
			dependentSchemas: { a: { type: "object", properties: { b: { type: "number" } }, required: ["b"] } }
		})
		if (T.allows({ a: 1, b: "x" } as never)) throw new Error("dependent schema must be enforced")
		if (!T.allows({ a: 1, b: 2 } as never)) throw new Error("satisfying the dependent schema must pass")
	})

	it("resolves local $ref and supports recursion", () => {
		const T = t({
			$defs: { node: { type: "object", properties: { next: { $ref: "#/$defs/node" } } } },
			$ref: "#/$defs/node"
		})
		if (!T.allows({ next: {} } as never)) throw new Error("recursive $ref must resolve")
	})

	it("rejects unsupported and unresolvable refs with the stated messages", () => {
		mustReject(
			{ $ref: "https://example.com/schema" },
			"Only local $ref values of the form #/$defs/<name> are supported"
		)
		mustReject(
			{ $ref: "#/$defs/NonExistentDef" },
			'Unable to resolve $ref "#/$defs/NonExistentDef" from root $defs'
		)
	})

	it("supports if/then/else and deep enum equality", () => {
		const T = t({
			if: { type: "object", properties: { a: { const: 1 } }, required: ["a"] },
			then: { type: "object", required: ["b"] }
		})
		if (T.allows({ a: 1 } as never)) throw new Error("then must apply when if matches")
		if (!T.allows({ a: 1, b: 2 } as never)) throw new Error("satisfying then must pass")
		const E = t({ enum: [{ x: [1, 2] }] })
		if (!E.allows({ x: [1, 2] } as never)) throw new Error("enum must use deep equality")
	})
})
TSEOF
NODE_PATH=/app/node_modules ./node_modules/.bin/mocha --no-config --no-package \
  --node-option import=tsx /tmp/gate/ark.test.ts
GATEEOF""",
    # move.txt holds one or more [src][dst] moves.
    # Validated in-container: exits non-zero pre-implementation.
    "chess-best-move": r"""cat <<'GATEEOF' | ./run-in-container sh -s
set -e
test -s /app/move.txt
python3 - <<'PY'
import re
lines = [l.strip() for l in open("/app/move.txt") if l.strip()]
assert lines, "move.txt must contain at least one move"
for l in lines:
    assert re.fullmatch(r"[a-h][1-8][a-h][1-8]", l), f"move {l!r} must be [src][dst], e.g. e2e4"
PY
GATEEOF""",
    # output.txt starts with the prefix the instruction itself discloses.
    # Validated in-container: exits non-zero pre-implementation.
    "code-from-image": r"""cat <<'GATEEOF' | ./run-in-container sh -s
set -e
test -s /app/output.txt
grep -q '^bee26a' /app/output.txt
GATEEOF""",
    # a 1-hour VEVENT with all three attendees, inside the stated hard constraints.
    # Validated in-container: exits non-zero pre-implementation.
    "constraints-scheduling": r"""cat <<'GATEEOF' | ./run-in-container sh -s
set -e
test -s /app/meeting_scheduled.ics
python3 - <<'PY'
import re
t = open("/app/meeting_scheduled.ics").read()
assert "BEGIN:VEVENT" in t and "END:VEVENT" in t, "must be a VEVENT calendar entry"
for who in ("alice@example.com", "bob@example.com", "carol@example.com"):
    assert who in t, f"{who} must be an attendee"
assert re.search(r"SUMMARY:.*Team Planning Meeting", t, re.I), "summary must name the meeting"
s = re.search(r"DTSTART[^:]*:(\d{8})T(\d{2})(\d{2})", t)
e = re.search(r"DTEND[^:]*:(\d{8})T(\d{2})(\d{2})", t)
assert s and e, "needs DTSTART and DTEND"
sh, sm = int(s.group(2)), int(s.group(3)); eh, em = int(e.group(2)), int(e.group(3))
assert (eh*60+em) - (sh*60+sm) == 60, "meeting must be exactly 1 hour"
# Hard constraints from the brief: Bob no meetings before 10:00; Alice none after 14:00.
assert sh >= 10, "Bob cannot meet before 10 AM"
assert eh*60+em <= 14*60, "Alice cannot meet after 2 PM"
PY
GATEEOF""",
    # extract.js runs and emits a JSON object of integer values keyed by numeric address.
    # Validated in-container: exits non-zero pre-implementation.
    "extract-elf": r"""cat <<'GATEEOF' | ./run-in-container sh -s
set -e
test -s /app/extract.js
node /app/extract.js /app/a.out > /tmp/out.json
python3 - <<'PY'
import json
d = json.load(open("/tmp/out.json"))
assert isinstance(d, dict) and d, "must be a non-empty JSON object"
for k, v in d.items():
    assert str(k).isdigit(), f"address {k!r} must be a numeric key"
    assert isinstance(v, int), f"value for {k} must be an int, got {type(v).__name__}"
PY
GATEEOF""",
    # out.txt carries the decoded text.
    # Validated in-container: exits non-zero pre-implementation.
    "gcode-to-text": r"""cat <<'GATEEOF' | ./run-in-container sh -s
set -e
test -s /app/out.txt
python3 -c "
t=open('/app/out.txt').read().strip()
assert t, 'out.txt must not be empty'
assert any(c.isalnum() for c in t), 'out.txt must contain the printed text'
"
GATEEOF""",
    # secret recovered AND unreachable anywhere in the repo, history included.
    # Validated in-container: exits non-zero pre-implementation.
    "git-leak-recovery": r"""cat <<'GATEEOF' | ./run-in-container sh -s
set -e
test -s /app/secret.txt
grep -qE '^secret' /app/secret.txt
# The secret must no longer be recoverable anywhere in the repo, including history.
S=$(tr -d '\r\n' < /app/secret.txt)
cd /app/repo
! git grep -q -- "$S" $(git rev-list --all) 2>/dev/null
! grep -rq -- "$S" . 2>/dev/null
GATEEOF""",
    # the regex compiles, matches only the LAST date on an IPv4 line, and rejects look-alikes.
    # Validated in-container: exits non-zero pre-implementation.
    "regex-log": r"""cat <<'GATEEOF' | ./run-in-container sh -s
set -e
test -s /app/regex.txt
python3 - <<'PY'
import re
pat = open("/app/regex.txt").read().strip()
assert pat, "regex.txt must not be empty"
rx = re.compile(pat)              # must compile
# A line with an IPv4 and two dates: only the LAST date may match.
line = "2020-01-01 host 10.0.0.1 evt 2021-12-31"
got = rx.findall(line + "\n")
flat = [g if isinstance(g, str) else next((x for x in g if x), "") for g in got]
assert flat == ["2021-12-31"], f"expected only the last date, got {flat}"
# A line with no IPv4 must not match at all.
assert not rx.findall("2020-01-01 no address here\n"), "must require an IPv4 on the line"
# Near-misses must not match.
assert not rx.findall("user 1134-12-1234 and 10.0.0.1\n"), "must reject alphanumeric-adjacent look-alikes"
PY
GATEEOF""",
    # proto, generated stubs, server class and port all present.
    # Validated in-container: exits non-zero pre-implementation.
    "kv-store-grpc": r"""cat <<'GATEEOF' | ./run-in-container sh -s
set -e
test -s /app/kv-store.proto
ls /app/*_pb2.py /app/*_pb2_grpc.py >/dev/null
test -s /app/server.py
python3 -c "import grpc, grpc_tools" 2>/dev/null
grep -q 'service KVStore' /app/kv-store.proto
grep -qE 'rpc +GetVal' /app/kv-store.proto
grep -qE 'rpc +SetVal' /app/kv-store.proto
grep -q 'class Server' /app/server.py
grep -q '5328' /app/server.py
GATEEOF""",
    # one file that python3 and gcc both run, agreeing on Fibonacci.
    # Validated in-container: exits non-zero pre-implementation.
    "polyglot-c-py": r"""cat <<'GATEEOF' | ./run-in-container sh -s
set -e
F=/app/polyglot/main.py.c
test -s "$F"
# Same source must run under python3 and compile+run under gcc, agreeing on Fibonacci.
for n in 0 1 10; do
  p=$(python3 "$F" $n)
  gcc "$F" -o /tmp/cmain 2>/dev/null
  c=$(/tmp/cmain $n)
  [ "$p" = "$c" ] || { echo "python=$p gcc=$c for n=$n"; exit 1; }
done
[ "$(python3 "$F" 10)" = "55" ]
[ "$(python3 "$F" 0)" = "0" ]
[ "$(python3 "$F" 1)" = "1" ]
GATEEOF""",
    # results.txt holds a FLAG{...} value.
    # Validated in-container: exits non-zero pre-implementation.
    "vulnerable-secret": r"""cat <<'GATEEOF' | ./run-in-container sh -s
set -e
test -s /app/results.txt
grep -qE 'FLAG\{.+\}' /app/results.txt
GATEEOF""",
    # merged parquet and conflict report both produced and readable.
    # Validated in-container: exits non-zero pre-implementation.
    "multi-source-data-merger": r"""cat <<'GATEEOF' | ./run-in-container sh -s
set -e
test -s /app/merged_users.parquet
test -s /app/conflicts.json
python3 - <<'PY'
import json
import pandas as pd
df = pd.read_parquet("/app/merged_users.parquet")
assert len(df) > 0, "merged dataset must not be empty"
c = json.load(open("/app/conflicts.json"))
assert isinstance(c, (list, dict)), "conflict report must be JSON"
PY
GATEEOF""",
    # summary.csv has the exact header and every period/severity row.
    # Validated in-container: exits non-zero pre-implementation.
    "log-summary-date-ranges": r"""cat <<'GATEEOF' | ./run-in-container sh -s
set -e
test -s /app/summary.csv
python3 - <<'PY'
import csv
rows = list(csv.reader(open("/app/summary.csv")))
assert rows and rows[0] == ["period", "severity", "count"], f"header must be period,severity,count; got {rows[:1]}"
body = rows[1:]
seen = {(r[0], r[1]) for r in body if len(r) >= 3}
for period in ("today", "last_7_days", "last_30_days"):
    for sev in ("ERROR", "WARNING", "INFO"):
        assert (period, sev) in seen, f"missing row for {period}/{sev}"
for r in body:
    assert r[2].strip().isdigit(), f"count must be an integer, got {r[2]!r}"
PY
GATEEOF""",
    # stated placeholders present and no live-looking credential remains.
    # Validated in-container: exits non-zero pre-implementation.
    "sanitize-git-repo": r"""cat <<'GATEEOF' | ./run-in-container sh -s
set -e
cd /app
R=$(ls -d */ 2>/dev/null | head -1)
[ -n "$R" ]
# The stated placeholders must be present...
grep -rq -- '<your-aws-access-key-id>\|<your-aws-secret-access-key>\|<your-github-token>\|<your-huggingface-token>' . 
# ...and no live-looking credential may remain anywhere, including history.
! grep -rqE 'AKIA[0-9A-Z]{16}' . 2>/dev/null
! grep -rqE 'ghp_[0-9A-Za-z]{30,}' . 2>/dev/null
! grep -rqE 'hf_[0-9A-Za-z]{30,}' . 2>/dev/null
GATEEOF""",
    # correct dominant pair AND faster than the numpy reference.
    # Validated in-container: exits non-zero pre-implementation.
    "largest-eigenval": r"""cat <<'GATEEOF' | ./run-in-container sh -s
set -e
python3 - <<'PY'
import time, numpy as np, sys
sys.path.insert(0, "/app")
from eigen import find_dominant_eigenvalue_and_eigenvector as f
rng = np.random.default_rng(0)
for n in (3, 7, 10):
    A = rng.standard_normal((n, n))
    val, vec = f(A)
    vec = np.asarray(vec).reshape(-1)
    assert np.allclose(A @ vec, val * vec, atol=1e-6), f"eigen pair wrong for n={n}"
    # dominant = largest magnitude
    assert np.isclose(abs(val), max(abs(np.linalg.eigvals(A))), rtol=1e-6), f"not dominant for n={n}"
# must beat numpy's reference on median time
A = rng.standard_normal((10, 10))
def med(fn, k=25):
    ts = []
    for _ in range(k):
        t0 = time.perf_counter(); fn(); ts.append(time.perf_counter() - t0)
    return sorted(ts)[len(ts)//2]
mine = med(lambda: f(A))
ref = med(lambda: np.linalg.eig(A))
assert mine < ref, f"must be faster than numpy reference: {mine:.6f} vs {ref:.6f}"
PY
GATEEOF""",
    # repo initialised with branch1 and branch2 checked out.
    # Validated in-container: exits non-zero pre-implementation.
    "merge-diff-arc-agi-task": r"""cat <<'GATEEOF' | ./run-in-container sh -s
set -e
test -d /app/repo/.git
cd /app/repo
git rev-parse --verify branch1 >/dev/null 2>&1
git rev-parse --verify branch2 >/dev/null 2>&1
GATEEOF""",
    # modernised script and dependency file present, script runs.
    # Validated in-container: exits non-zero pre-implementation.
    "modernize-scientific-stack": r"""cat <<'GATEEOF' | ./run-in-container sh -s
set -e
test -s /app/analyze_climate_modern.py
test -s /app/requirements.txt -o -s /app/pyproject.toml
python3 -c "import ast,sys; ast.parse(open('/app/analyze_climate_modern.py').read())"
python3 /app/analyze_climate_modern.py >/dev/null 2>&1
GATEEOF""",
    # paired primers within the stated length and melting-temperature bounds.
    # Validated in-container: exits non-zero pre-implementation.
    "dna-insert": r"""cat <<'GATEEOF' | ./run-in-container sh -s
set -e
test -s /app/primers.fasta
python3 - <<'PY'
import re, subprocess, shutil
seqs, name = [], None
for line in open("/app/primers.fasta"):
    line = line.strip()
    if line.startswith(">"):
        name = line
    elif line and name is not None:
        seqs.append(line.upper())
assert seqs, "primers.fasta must contain sequences"
assert len(seqs) % 2 == 0, "primers must be grouped in forward/reverse pairs"
for s in seqs:
    assert re.fullmatch(r"[ACGT]+", s), f"non-nucleotide characters in {s[:20]!r}"
    assert 15 <= len(s) <= 45, f"annealing length must be 15-45, got {len(s)}"
oligotm = shutil.which("oligotm")
if oligotm:
    flags = ["-tp", "1", "-sc", "1", "-mv", "50", "-dv", "2", "-n", "0.8", "-d", "500"]
    tms = [float(subprocess.run([oligotm, *flags, s], capture_output=True, text=True).stdout.strip())
           for s in seqs]
    for t in tms:
        assert 58 <= t <= 72, f"melting temperature {t} outside 58-72"
    for i in range(0, len(tms), 2):
        assert abs(tms[i] - tms[i+1]) <= 5, f"pair Tm differ by more than 5C: {tms[i]} vs {tms[i+1]}"
PY
GATEEOF""",
}


# Tasks whose SEALED GRADER cannot run, so every arm scores zero regardless of its work.
# These are not hard tasks -- they are unmeasurable, and including them silently depresses
# every arm's pass rate and shrinks the paired-comparison denominator.
UNMEASURABLE_TASKS: dict[str, str] = {
    # Ships no tests/ directory, so task_loader falls back to `pytest tests/` -- and pytest
    # is not installed in the image. Observed exit 127 for vanilla, solo and daemon alike:
    #   OCI runtime exec failed: exec: "pytest": executable file not found in $PATH
    # Re-include once the task carries a verifier that actually executes.
    "sqlite-db-truncate": "grader exits 127: pytest not present in the task image",
}


def is_unmeasurable(task_name: str) -> Optional[str]:
    """Reason a task cannot be scored, or None if it can."""
    return UNMEASURABLE_TASKS.get(task_name)


def agent_gate_for(task_name: str) -> Optional[str]:
    """Return the hand-authored agent-facing gate for a task, if one exists.

    This is deliberately NOT `TaskSpec.verification_cmd`: that field holds the sealed
    held-out grader and is what `extractor.py` runs to decide pass/fail. Overwriting it
    would grade the agent against the very contract it was handed, which would inflate
    every score. The two must stay separate -- this gate steers the agent, that one
    judges it.
    """
    return GATE_FIXTURES.get(task_name)
