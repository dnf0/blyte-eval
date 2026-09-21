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
	if v, err := run("var x: int64 = 10\\nx", true); err != nil || v == nil {
		log.Fatalf("typed declaration failed: %v", err)
	}
	if _, err := run("var a, b: int64 = 1, 2\\na", true); err != nil {
		log.Fatalf("multi typed declaration failed: %v", err)
	}
	_, err := run("var y: int64 = 1\\ny = \\"s\\"", true)
	if err == nil {
		log.Fatal("type mismatch must error when TypedBindings is enabled")
	}
	if !strings.Contains(err.Error(), "type error") || !strings.Contains(err.Error(), "y") {
		log.Fatalf("error must contain 'type error' and the variable name, got: %v", err)
	}
	if _, err := run("var n: int64 = 1\\nn = nil", true); err == nil {
		log.Fatal("nil assignment to a primitive must error")
	}
	if _, err := run("var z: int64 = 1\\nz = \\"s\\"", false); err != nil {
		log.Fatalf("TypedBindings disabled must behave dynamically, got: %v", err)
	}
	if _, err := run("var q = 1\\nq = \\"s\\"", true); err != nil {
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
	// NOTE: assertions on `1/0` were removed on 2026-09-21. expr evaluates division as
	// float64, so 1/0 yields +Inf without raising, and the task's own reference solution
	// (solution/solution.patch) changes no runtime or division code -- it fails any such
	// assertion. The gate rejected the reference fix and trapped the worker for 5 turns
	// and $4.87 in EXP-071. See FINDINGS.md 13.3.
	evalOK(`try(6*7, "fallback")`, 42)
	evalOK(`try(throw("boom"), "caught")`, "caught")
	evalOK(`try { throw("boom") } catch e { errtype(e) }`, "custom")
	evalOK(`errtype(nil)`, "none")
	evalOK(`try { throw("e") } catch { "handled" }`, "handled")
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
if (parseModule("using\\nx = null;", { next: true }).body[0].kind === "using")
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
    # KNOWN DISAGREEMENT (2026-09-21): this gate asserts the exact non-existent-$ref message
    # instruction.md line 8 demands -- `Unable to resolve $ref "#/$defs/NonExistentDef" from
    # root $defs`. The task's own reference solution emits a different sentence, so
    # `scripts/validate_gates.py` reports this gate as rejecting the reference. The gate is
    # kept as written because the instruction, not the reference, is what the worker is given
    # and what a gate may legitimately be derived from. Do not weaken it to match the
    # reference without first establishing which the sealed grader follows.
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
			then: { type: "object", properties: { b: { type: "number" } }, required: ["b"] }
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
    # one file that python3 and gcc both run, agreeing on Fibonacci across a wide range,
    # compiled to the path the instruction names and with no compiler diagnostics on stderr.
    # The old gate checked three inputs and compiled to /tmp.
    "polyglot-c-py": r"""cat <<'GATEEOF' | ./run-in-container sh -s
set -e
F=/app/polyglot/main.py.c
test -s "$F"
# The instruction names this output path explicitly.
gcc "$F" -o /app/polyglot/cmain
test -x /app/polyglot/cmain
python3 - <<'PY'
import subprocess

def fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a

for n in (0, 1, 2, 3, 5, 10, 20, 30, 40):
    py = subprocess.run(["python3", "/app/polyglot/main.py.c", str(n)],
                        capture_output=True, text=True)
    c = subprocess.run(["/app/polyglot/cmain", str(n)], capture_output=True, text=True)
    assert py.returncode == 0, f"python3 failed for n={n}: {py.stderr[-200:]}"
    assert c.returncode == 0, f"compiled binary failed for n={n}: {c.stderr[-200:]}"
    p_out, c_out = py.stdout.strip(), c.stdout.strip()
    assert p_out == c_out, f"n={n}: python printed {p_out!r}, C printed {c_out!r}"
    assert p_out == str(fib(n)), f"n={n}: expected {fib(n)}, got {p_out!r}"
PY
GATEEOF""",
    # results.txt holds a FLAG{...} value.
    # Validated in-container: exits non-zero pre-implementation.
    "vulnerable-secret": r"""cat <<'GATEEOF' | ./run-in-container sh -s
set -e
test -s /app/results.txt
grep -qE 'FLAG\{.+\}' /app/results.txt
GATEEOF""",
    # merged parquet and conflict report both produced and readable.
    # merged parquet carries the stated schema for every user across all three sources,
    # and the conflict report is internally consistent. The old gate asserted only that
    # the parquet was non-empty and conflicts.json parsed as JSON.
    "multi-source-data-merger": r"""cat <<'GATEEOF' | ./run-in-container sh -s
set -e
test -s /app/merged_users.parquet
test -s /app/conflicts.json
python3 - <<'PY'
import json, re
import pandas as pd

df = pd.read_parquet("/app/merged_users.parquet")
for col in ("user_id", "name", "email", "created_date"):
    assert col in df.columns, f"merged output missing column {col!r}"
assert len(df) > 0, "merged dataset must not be empty"
assert df["user_id"].is_unique, "one row per unique user"
assert pd.api.types.is_integer_dtype(df["user_id"]), "user_id must be an integer column"
for value in df["created_date"].dropna().astype(str):
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", value), f"created_date must be YYYY-MM-DD, got {value!r}"

# Every unique user from all three sources must survive the merge.
def ids_from(records):
    out = set()
    for rec in records:
        for key in ("user_id", "id", "userId"):
            if key in rec and rec[key] is not None:
                out.add(int(rec[key]))
                break
    return out

expected = ids_from(json.load(open("/data/source_a/users.json")))
expected |= ids_from(pd.read_csv("/data/source_b/users.csv").to_dict("records"))
expected |= ids_from(pd.read_parquet("/data/source_c/users.parquet").to_dict("records"))
missing = expected - set(df["user_id"].astype(int))
assert not missing, f"users dropped during merge: {sorted(missing)[:10]}"

report = json.load(open("/app/conflicts.json"))
assert isinstance(report, dict), "conflict report must be a JSON object"
assert "total_conflicts" in report and "conflicts" in report
assert report["total_conflicts"] == len(report["conflicts"]), \
    "total_conflicts must equal the number of entries in conflicts"
for entry in report["conflicts"]:
    for key in ("user_id", "field", "values", "selected"):
        assert key in entry, f"conflict entry missing {key!r}"
PY
GATEEOF""",
    # summary.csv has the exact header and every period/severity row.
    # summary.csv carries the exact header and ALL FIVE periods the instruction lists.
    # The old gate checked three of them, so a file missing month_to_date and total passed.
    "log-summary-date-ranges": r"""cat <<'GATEEOF' | ./run-in-container sh -s
set -e
test -s /app/summary.csv
python3 - <<'PY'
import csv

rows = list(csv.reader(open("/app/summary.csv")))
assert rows and rows[0] == ["period", "severity", "count"], \
    f"header must be period,severity,count; got {rows[:1]}"
body = [r for r in rows[1:] if r and any(c.strip() for c in r)]

periods = ("today", "last_7_days", "last_30_days", "month_to_date", "total")
severities = ("ERROR", "WARNING", "INFO")
seen = {(r[0].strip(), r[1].strip()): r[2].strip() for r in body if len(r) >= 3}
for period in periods:
    for sev in severities:
        assert (period, sev) in seen, f"missing row for {period}/{sev}"
assert len(body) == len(periods) * len(severities), \
    f"expected {len(periods) * len(severities)} data rows, got {len(body)}"
for (period, sev), count in seen.items():
    assert count.isdigit(), f"count for {period}/{sev} must be an integer, got {count!r}"

# `total` counts every file regardless of date, so it cannot be smaller than any window.
for sev in severities:
    total = int(seen[("total", sev)])
    for period in ("today", "last_7_days", "last_30_days", "month_to_date"):
        assert int(seen[(period, sev)]) <= total, \
            f"{period}/{sev} exceeds total/{sev}"
    assert int(seen[("today", sev)]) <= int(seen[("last_7_days", sev)]) <= int(seen[("last_30_days", sev)]), \
        f"{sev} windows are not nested"
PY
GATEEOF""",
    # stated placeholders present and no live-looking credential remains.
    # placeholders present and consistent, no live credential anywhere INCLUDING history,
    # and no uncontaminated file deleted. The instruction asks for all three; the old gate
    # checked only the first two, so wiping a file passed.
    "sanitize-git-repo": r"""cat <<'GATEEOF' | ./run-in-container sh -s
set -e
cd /app
R=$(ls -d */ 2>/dev/null | head -1)
[ -n "$R" ]
cd "$R"
# The stated placeholders must be present...
grep -rq -- '<your-aws-access-key-id>\|<your-aws-secret-access-key>\|<your-github-token>\|<your-huggingface-token>' .
# ...no live-looking credential may remain in the working tree...
! grep -rqE 'AKIA[0-9A-Z]{16}' . 2>/dev/null
! grep -rqE 'ghp_[0-9A-Za-z]{30,}' . 2>/dev/null
! grep -rqE 'hf_[0-9A-Za-z]{30,}' . 2>/dev/null
# ...nor anywhere in history, which is what "not present in the repository" requires.
if [ -d .git ]; then
  ! git log -p --all 2>/dev/null | grep -qE 'AKIA[0-9A-Z]{16}'
  ! git log -p --all 2>/dev/null | grep -qE 'ghp_[0-9A-Za-z]{30,}'
  ! git log -p --all 2>/dev/null | grep -qE 'hf_[0-9A-Za-z]{30,}'
  # Deleting a contaminated file is not sanitising it; the instruction forbids
  # removing or modifying files that were never contaminated.
  ! git status --porcelain 2>/dev/null | grep -qE '^( D|D |AD)'
fi
GATEEOF""",
    # correct dominant pair AND faster than the numpy reference.
    # correct dominant pair on several non-symmetric matrices AND reliably faster than the
    # numpy reference, with a margin and repeated trials. The old gate timed one matrix once,
    # which a marginal implementation passes by luck.
    "largest-eigenval": r"""cat <<'GATEEOF' | ./run-in-container sh -s
set -e
python3 - <<'PY'
import time
import numpy as np
import sys

sys.path.insert(0, "/app")
from eigen import find_dominant_eigenvalue_and_eigenvector as f

rng = np.random.default_rng(0)
for trial in range(12):
    n = int(rng.integers(2, 11))
    A = rng.standard_normal((n, n))
    val, vec = f(A)
    vec = np.asarray(vec).reshape(-1)
    assert np.allclose(A @ vec, val * vec, atol=1e-6), \
        f"trial {trial} (n={n}): A@v != lambda*v"
    assert np.isclose(abs(val), max(abs(np.linalg.eigvals(A))), rtol=1e-6), \
        f"trial {trial} (n={n}): eigenvalue is not the dominant one"

def median_time(fn, k=51):
    samples = []
    for _ in range(k):
        t0 = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - t0)
    return sorted(samples)[len(samples) // 2]

# Must win on every size, not just one, and by a margin that survives jitter.
for n in (3, 7, 10):
    A = rng.standard_normal((n, n))
    f(A)                      # warm up any JIT or import cost
    np.linalg.eig(A)
    mine = median_time(lambda: f(A))
    ref = median_time(lambda: np.linalg.eig(A))
    assert mine < ref * 0.95, \
        f"n={n}: {mine:.6f}s vs numpy {ref:.6f}s -- must be reliably faster"
PY
GATEEOF""",
    # repo initialised with branch1 and branch2 checked out.
    # branch2 genuinely merged into branch1, and algo.py reproduces every example.
    # The instruction states both explicitly; the old gate checked only that two branch
    # refs existed, which `git branch` alone satisfies.
    "merge-diff-arc-agi-task": r"""cat <<'GATEEOF' | ./run-in-container sh -s
set -e
test -d /app/repo/.git
cd /app/repo
git rev-parse --verify branch1 >/dev/null 2>&1
git rev-parse --verify branch2 >/dev/null 2>&1
# branch2 must actually be merged into branch1, not merely exist alongside it.
git merge-base --is-ancestor branch2 branch1
test -s /app/repo/algo.py
python3 - <<'PY'
import importlib.util, json
spec = importlib.util.spec_from_file_location("algo", "/app/repo/algo.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
fn = getattr(mod, "map", None)
assert callable(fn), "algo.py must define a callable named map"
raw = json.load(open("/app/examples.json"))
cases = raw.get("train", raw) if isinstance(raw, dict) else raw
assert cases, "examples.json holds no cases"
for i, case in enumerate(cases):
    got = fn(case["input"])
    want = case["output"]
    assert got == want, f"example {i}: map() returned {got!r}, expected {want!r}"
PY
GATEEOF""",
    # modernised script and dependency file present, script runs.
    # the modern script prints the stated line for BOTH stations, the legacy file is
    # untouched, and the dependency file names the required packages with version pins.
    # The old gate only checked the script parsed and exited 0.
    "modernize-scientific-stack": r"""cat <<'GATEEOF' | ./run-in-container sh -s
set -e
test -s /app/analyze_climate_modern.py
# The legacy script is explicitly DO NOT MODIFY.
test -s /app/climate_analyzer/analyze_climate.py
python3 -c "import ast; ast.parse(open('/app/analyze_climate_modern.py').read())"
OUT=$(python3 /app/analyze_climate_modern.py 2>/dev/null)
echo "$OUT" | grep -qE 'Station 101 mean temperature: -?[0-9]+\.[0-9]' || {
  echo "missing/badly formatted line for station 101"; exit 1; }
echo "$OUT" | grep -qE 'Station 102 mean temperature: -?[0-9]+\.[0-9]' || {
  echo "missing/badly formatted line for station 102"; exit 1; }
python3 - <<'PY'
import os, re
path = "/app/requirements.txt" if os.path.exists("/app/requirements.txt") else "/app/pyproject.toml"
assert os.path.exists(path), "need /app/requirements.txt or /app/pyproject.toml"
text = open(path).read().lower()
for pkg in ("numpy", "pandas"):
    assert pkg in text, f"dependency file must include {pkg}"
assert "matplotlib" in text or "scipy" in text, "need at least one of matplotlib, scipy"
assert re.search(r"(>=|==|~=)\s*\d", text), "versions must be constrained with >=, == or ~="
PY
GATEEOF""",
    # paired primers within the stated length and melting-temperature bounds.
    # primer pairs whose ANNEALING REGION (not the whole primer, which may carry a 5' tail)
    # satisfies the stated length and melting-temperature bounds, with oligotm as ground
    # truth. The old gate wrapped every temperature check in `if oligotm:`, so on an image
    # without the tool it silently degraded to a shape check -- and it measured the whole
    # PARTIALLY VERIFIABLE -- see the note below. Checks every requirement the image can
    # actually support: primers pair up, and each one's ANNEALING REGION (the 3' part that
    # matches the template, not the whole primer, which may carry a 5' tail) is a real
    # template match of the stated 15-45nt length.
    #
    # The melting-temperature bounds CANNOT be checked here. The instruction names primer3's
    # `oligotm` as ground truth, and the image ships no oligotm binary, no primer3-py, no
    # pip3 and no network -- verified 2026-09-16. The previous gate wrapped the temperature
    # checks in `if oligotm:`, so on this image it silently skipped them and degraded to a
    # shape check that `touch`-grade output passes. This version keeps every check it can
    # enforce mandatory and states plainly which requirement is out of reach, rather than
    # hiding the gap behind a conditional.
    "dna-insert": r"""cat <<'GATEEOF' | ./run-in-container sh -s
set -e
test -s /app/primers.fasta
python3 - <<'PY'
import re, shutil, subprocess

def read_fasta(path):
    out, name = [], None
    for line in open(path):
        line = line.strip()
        if line.startswith(">"):
            name = line
        elif line and name is not None:
            out.append(line.upper())
    return out

primers = read_fasta("/app/primers.fasta")
assert primers, "primers.fasta must contain sequences"
assert len(primers) % 2 == 0, "primers must be grouped in forward/reverse pairs"
for s in primers:
    assert re.fullmatch(r"[ACGT]+", s), f"non-nucleotide characters in {s[:20]!r}"

template = max(read_fasta("/app/sequences.fasta"), key=len)
COMP = str.maketrans("ACGT", "TGCA")
def rc(s):
    return s.translate(COMP)[::-1]
# The plasmid is circular, so an annealing site may wrap the origin.
haystack = (template + template) + "|" + (rc(template) + rc(template))

def annealing_region(primer):
    # Longest 3-prime suffix of the primer that is present in the template.
    for start in range(len(primer)):
        suffix = primer[start:]
        if suffix in haystack:
            return suffix
    return ""

regions = []
for s in primers:
    region = annealing_region(s)
    assert region, f"primer {s[:20]!r} does not anneal to the template at its 3' end"
    assert 15 <= len(region) <= 45, \
        f"annealing length must be 15-45, got {len(region)} for {s[:20]!r}"
    regions.append(region)

# Melting temperature: enforced only where the stated ground-truth tool exists. On an image
# without it the bound is unverifiable -- this is reported, never silently skipped.
oligotm = shutil.which("oligotm")
if oligotm:
    FLAGS = ["-tp", "1", "-sc", "1", "-mv", "50", "-dv", "2", "-n", "0.8", "-d", "500"]
    temps = []
    for region in regions:
        proc = subprocess.run([oligotm, *FLAGS, region], capture_output=True, text=True)
        assert proc.returncode == 0, f"oligotm failed on {region[:20]!r}: {proc.stderr[-200:]}"
        tm = float(proc.stdout.strip())
        assert 58 <= tm <= 72, f"melting temperature {tm} outside 58-72 for {region[:20]!r}"
        temps.append(tm)
    for i in range(0, len(temps), 2):
        assert abs(temps[i] - temps[i + 1]) <= 5, \
            f"pair {i // 2} melting temperatures differ by more than 5C"
else:
    print("GATE LIMITATION: oligotm absent, melting-temperature bounds NOT verified")
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
    # The seven below ship no held-out tests/ directory at all. task_loader falls back to
    # `pytest tests/`, which the harness then runs INSIDE THE AGENT'S OWN CONTAINER -- so
    # whatever the agent wrote into tests/ becomes the grader. That is self-grading, and it
    # is not symmetrical between arms: measured 2026-09-16 over 55 paired runs, these tasks
    # went vanilla 0/7 and superstate_mcp 7/7, because superstate's handoff prompt asks the
    # worker to produce and run a verification command while the baseline gets no such
    # instruction. They supplied 7 of the 18 discordant pairs behind the headline lift.
    #
    # Where the agent writes no tests/, the same fallback instead exits 127 (pytest absent)
    # and scores zero for every arm. So these tasks are simultaneously a source of spurious
    # passes and spurious failures. extractor.py now refuses to grade them at all.
    "largest-eigenval": "no held-out tests/; grading would run the agent's own tests",
    "log-summary-date-ranges": "no held-out tests/; grading would run the agent's own tests",
    "merge-diff-arc-agi-task": "no held-out tests/; grading would run the agent's own tests",
    "modernize-scientific-stack": "no held-out tests/; grading would run the agent's own tests",
    "multi-source-data-merger": "no held-out tests/; grading would run the agent's own tests",
    "polyglot-c-py": "no held-out tests/; grading would run the agent's own tests",
    "sanitize-git-repo": "no held-out tests/; grading would run the agent's own tests",
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
