"""Exploratory: does decider's judgement of a task's specification separate the plan tasks blyte got right first time
(verdict 'accepted') from those that needed a fix or a redo? Only a few of the latter were the task's fault."""
import json, os, time

SP = os.path.dirname(os.path.abspath(__file__))
items = json.load(open(f"{SP}/task_items.json"))
PLAN_GAP = {"S13-gate-failures-blyte", "E11-plan-first-blyte", "S32-grep-long-lines-blyte"}  # the notes blame the task
Q = {"spec": {"type": "score", "instructions": "How completely does this task specify what to build, for an engineer who has not seen the repository?",
              "criteria": ["vague: key behaviour is left to guess", "mostly specified, with gaps", "fully specified: files, behaviour, edge cases and tests"]},
     "ask": {"type": "noul", "instructions": "Would a careful engineer who has not seen the repository need to ask a question before implementing this task?"}}

from decider.infer import Decider
d = Decider(os.path.expanduser("~/.cache/decider/decider-4b-GGUF"), gguf_file="decider-4b-v2.1-Q4_K_M.gguf",
            gguf_options={"n_gpu_layers": -1, "n_ctx": 16384})
rows = []
for it in items:
    t0 = time.time()
    a = d.system_one({"task": it["task"][:10000]}, Q)["answers"]
    pr = a["spec"]["probabilities"]
    rows.append({"id": it["id"], "verdict": it["verdict"], "plan_gap": it["id"] in PLAN_GAP,
                 "p_vague": pr.get("0", 0), "p_full": pr.get("2", 0), "p_ask": a["ask"]["noul"], "s": round(time.time() - t0, 2)})


def auc(b, g):
    return sum((x > y) + 0.5 * (x == y) for x in b for y in g) / (len(b) * len(g))


ok = [r for r in rows if r["verdict"] == "accepted"]
notok = [r for r in rows if r["verdict"] != "accepted"]
gap = [r for r in rows if r["plan_gap"]]
for key in ("p_ask", "p_vague"):
    print(f"{key:8} AUC not-accepted vs accepted {auc([r[key] for r in notok], [r[key] for r in ok]):.2f}   "
          f"plan-gap (n={len(gap)}) vs accepted {auc([r[key] for r in gap], [r[key] for r in ok]):.2f}   "
          f"mean accepted {sum(r[key] for r in ok)/len(ok):.2f}  not-accepted {sum(r[key] for r in notok)/len(notok):.2f}")
for r in sorted(rows, key=lambda r: -r["p_ask"])[:6]:
    print(f"   most likely to need a question: {r['id']:32} {r['verdict']:8} p_ask {r['p_ask']:.2f}")
print(f"median seconds per task {sorted(r['s'] for r in rows)[len(rows)//2]}")
json.dump(rows, open(f"{SP}/task_scores.json", "w"), indent=1)
