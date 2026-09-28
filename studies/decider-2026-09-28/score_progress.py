"""Does decider's 'making progress?' judgement on a window of tool calls separate runs that ran out of turns or
errored from runs that were verified? Compared with a repetition baseline. AUC: the chance that a random failed
run looks worse than a random verified one (0.5 = no signal)."""
import json, os, random, time

SP = os.path.dirname(os.path.abspath(__file__))
runs = json.load(open(f"{SP}/runs_calls.json"))
bad = [r for r in runs if r["outcome"] != "verified"]
random.seed(3)
good = random.sample([r for r in runs if r["outcome"] == "verified"], 60)
Q = {"progress": {"type": "score", "instructions": "Is this coding agent making progress towards finishing its task, or going in circles?",
                  "criteria": ["going in circles", "unclear", "making steady progress"]},
     "looping": {"type": "noul", "instructions": "Is the agent repeating the same kind of actions without getting closer to done?"}}

from decider.infer import Decider
d = Decider(os.path.expanduser("~/.cache/decider/decider-4b-v2"))
d.system_one({"recent_tool_calls": "● bash ls -> exit 0"}, Q)


def windows(calls):
    n = len(calls)
    for frac in (0.3, 0.6, 0.9):
        end = max(15, int(n * frac))
        yield frac, calls[max(0, end - 15):end]


def repetition(w):
    keys = [c.split(" -> ")[0][:60] for c in w]
    return 1 - len(set(keys)) / len(keys)


rows = []
t0 = time.time()
for r in bad + good:
    for frac, w in windows(r["calls"]):
        a = d.system_one({"recent_tool_calls": "\n".join("● " + c[:160] for c in w)}, Q)["answers"]
        pr = a["progress"]["probabilities"]
        rows.append({"run": os.path.basename(r["f"]), "failed": int(r["outcome"] != "verified"), "frac": frac,
                     "p_circles": pr.get("0", 0), "p_loop": a["looping"]["noul"], "rep": repetition(w)})
print(f"{len(rows)} windows in {time.time()-t0:.0f}s")


def auc(scores_bad, scores_good):
    wins = sum((b > g) + 0.5 * (b == g) for b in scores_bad for g in scores_good)
    return wins / (len(scores_bad) * len(scores_good))


for frac in (0.3, 0.6, 0.9):
    s = [x for x in rows if x["frac"] == frac]
    for key, name in (("p_circles", "decider: going in circles"), ("p_loop", "decider: looping"), ("rep", "repetition baseline")):
        b = [x[key] for x in s if x["failed"]]; g = [x[key] for x in s if not x["failed"]]
        print(f"  at {int(frac*100)}% of the run  {name:28} AUC {auc(b, g):.2f}   mean failed {sum(b)/len(b):.2f}  verified {sum(g)/len(g):.2f}")
json.dump(rows, open(f"{SP}/progress_scores.json", "w"), indent=1)
