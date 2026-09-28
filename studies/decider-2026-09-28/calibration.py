"""Calibration of each benchmarked variant: when decider says it is p sure, is it right about p of the time?
Buckets of confidence, observed accuracy per bucket, and the expected calibration error (ECE)."""
import glob, json, os

SP = os.path.dirname(os.path.abspath(__file__))
BUCKETS = [(0.5, 0.7), (0.7, 0.9), (0.9, 0.97), (0.97, 1.01)]
out = {}
for f in sorted(glob.glob(f"{SP}/bench_*.json")):
    r = json.load(open(f))
    if "calib" not in r:
        continue
    c = r["calib"]; n = len(c)
    rows, ece = [], 0.0
    for lo, hi in BUCKETS:
        s = [x for x in c if lo <= x[0] < hi]
        if not s:
            continue
        conf = sum(x[0] for x in s) / len(s); acc = sum(x[1] for x in s) / len(s)
        ece += len(s) / n * abs(conf - acc)
        rows.append({"bucket": f"{lo:.2f}-{min(hi,1):.2f}", "n": len(s), "confidence": round(conf, 3), "accuracy": round(acc, 3)})
    out[r["name"]] = {"n": n, "ece": round(ece, 3), "buckets": rows}
    print(f"{r['name']:16} n={n}  ECE {ece:.3f}")
    for b in rows:
        print(f"   confidence {b['bucket']}: n={b['n']:3}  said {b['confidence']:.2f}  was right {b['accuracy']:.2f}")
json.dump(out, open(f"{SP}/calibration.json", "w"), indent=1)
