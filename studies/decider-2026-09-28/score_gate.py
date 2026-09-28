"""Score decider-4b v2 against a fixed rule baseline on the gate-failure cases: code, environment or flaky."""
import json, os, re, time, sys

SP = os.path.dirname(os.path.abspath(__file__))
cases = [json.loads(l) for l in open(f"{SP}/gate_cases.jsonl")]

# Fixed before the cases were generated (see the study notes): the plan's examples plus the obvious ones.
ENV = ["No space left", "Could not resolve host", "Connection refused", "command not found",
       "Permission denied", "Cannot connect to the Docker daemon", "could not be found"]
FLAKY = ["timed out", "killed by blyte"]


def rule(text):
    if any(p in text for p in FLAKY):
        return "flaky"
    if any(p in text for p in ENV):
        return "environment"
    return "code"


Q = {"cause": {"type": "choice", "instructions": "Why did this check fail?", "criteria": {
    "code": "The change being tested is wrong: a test assertion, compile error, type error or lint in the project's code",
    "environment": "The machine or setup is at fault: disk full, network, missing tool or service, permissions, credentials",
    "flaky": "Intermittent: a timeout or race that would likely pass on retry"}}}

from decider.infer import Decider
d = Decider(os.path.expanduser("~/.cache/decider/decider-4b-v2"))
d.system_one({"gate_output": "exit 1\nwarm-up"}, Q)  # the first call compiles kernels

rows, lat = [], []
for c in cases:
    # decider reads at most 32k tokens; keep the tail, where failures are reported
    text = c["text"][-24000:]
    t0 = time.time()
    a = d.system_one({"check_command": c["cmd"], "gate_output": text}, Q)["answers"]["cause"]
    lat.append(time.time() - t0)
    rows.append({"id": c["id"], "label": c["label"], "rule": rule(c["text"]), "decider": a["choice"],
                 "p": round(a["probabilities"][a["choice"]], 3), "p_label": round(a["probabilities"][c["label"]], 3)})

n = len(rows)
acc_r = sum(r["rule"] == r["label"] for r in rows) / n
acc_d = sum(r["decider"] == r["label"] for r in rows) / n
print(f"{'case':16} {'label':12} {'rule':12} {'decider':12} p(decider's)  p(label)")
for r in rows:
    mr = "" if r["rule"] == r["label"] else " x"
    md = "" if r["decider"] == r["label"] else " x"
    print(f"{r['id']:16} {r['label']:12} {r['rule'] + mr:12} {r['decider'] + md:12} {r['p']:.2f}         {r['p_label']:.2f}")
print(f"\naccuracy: rule {acc_r:.0%} ({sum(r['rule']==r['label'] for r in rows)}/{n}), decider {acc_d:.0%} ({sum(r['decider']==r['label'] for r in rows)}/{n})")
for lab in ("code", "environment", "flaky"):
    s = [r for r in rows if r["label"] == lab]
    print(f"  {lab:12} n={len(s):2}  rule {sum(r['rule']==lab for r in s)}/{len(s)}  decider {sum(r['decider']==lab for r in s)}/{len(s)}")
lat.sort()
print(f"decider latency: median {lat[len(lat)//2]*1000:.0f} ms, max {lat[-1]*1000:.0f} ms")
json.dump(rows, open(f"{SP}/gate_scores.json", "w"), indent=1)
