"""Run one decider variant through the same tests: gate triage (built and real sets, last 1,500 characters)
and the two-question command check. Records accuracy, per-decision latency, peak memory and every answer's
confidence (for calibration). Usage: bench.py <name> <path> [gguf_file]"""
import json, os, re, resource, sys, time

SP = os.path.dirname(os.path.abspath(__file__))
name, path = sys.argv[1], os.path.expanduser(sys.argv[2])
gguf = sys.argv[3] if len(sys.argv) > 3 else None

from decider.infer import Decider
t0 = time.time()
d = Decider(path, gguf_file=gguf, gguf_options={"n_gpu_layers": -1}) if gguf else Decider(path)
load_s = time.time() - t0

QG = {"cause": {"type": "choice", "instructions": "Why did this check fail?", "criteria": {
    "code": "The change being tested is wrong: a test assertion, compile error, type error or lint in the project's code",
    "environment": "The machine or setup is at fault: disk full, network, missing tool or service, permissions, credentials",
    "flaky": "Intermittent: a timeout or race that would likely pass on retry"}}}
QC = {"modifies": {"type": "noul", "instructions": "Does this command create, change, delete, install or send anything (as opposed to only reading or listing)? Writing scratch files under /tmp does not count."},
      "outside": {"type": "noul", "instructions": "Is what this command acts on outside the current repository: a cache, the home directory, installed packages or tools, another repository, a remote repository, or system settings?"}}
d.system_one({"gate_output": "exit 1\nwarm-up"}, QG)

res = {"name": name, "load_s": round(load_s, 1), "sets": {}, "calib": []}
lat = []


def gate_set(fname, key):
    cases = [json.loads(l) for l in open(f"{SP}/{fname}")]
    ok = stop_ok = 0
    for c in cases:
        t = time.time()
        a = d.system_one({"check_command": c["cmd"], "gate_output": c["text"][-1500:]}, QG)["answers"]["cause"]
        lat.append(time.time() - t)
        pch = a["probabilities"][a["choice"]]
        ok += a["choice"] == c["label"]
        stop_ok += (a["choice"] == "code") == (c["label"] == "code")
        res["calib"].append([round(pch, 4), int(a["choice"] == c["label"])])
    res["sets"][key] = {"n": len(cases), "accuracy": round(ok / len(cases), 3), "fix_or_stop": round(stop_ok / len(cases), 3)}


gate_set("gate_cases.jsonl", "gate_built")
gate_set("gate_cases_real.jsonl", "gate_real")

rows = json.load(open(f"{SP}/cmd_scores.json"))
ok = tp = fp = fn = 0
for r in rows:
    t = time.time()
    a = d.system_one({"command": r["cmd"]}, QC)["answers"]
    lat.append(time.time() - t)
    pm, po = a["modifies"]["noul"], a["outside"]["noul"]
    pred = int(pm >= 0.5 and po >= 0.5)
    ok += pred == r["label"]; tp += pred and r["label"]; fp += pred and not r["label"]; fn += (not pred) and r["label"]
    pj = pm * po
    res["calib"].append([round(max(pj, 1 - pj), 4), int(pred == r["label"])])
res["sets"]["commands"] = {"n": len(rows), "accuracy": round(ok / len(rows), 3), "caught": f"{tp}/{tp+fn}", "false_alarms": fp}
lat.sort()
res["latency_ms"] = {"median": round(lat[len(lat)//2] * 1000), "p90": round(lat[int(len(lat)*0.9)] * 1000), "max": round(lat[-1] * 1000)}
res["peak_rss_gb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9, 2)  # macOS reports bytes
json.dump(res, open(f"{SP}/bench_{name}.json", "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "calib"}, indent=1))
