"""Cross-fit two library policies; scores of the target task enter evaluation only."""
from collections import Counter, defaultdict
from fractions import Fraction
import json
from pathlib import Path
from statistics import mean
import sys

prior = Path(__file__).resolve().parent.parent / "paired_regret_policy_v1"
sys.path.insert(0, str(prior))
from portfolio import ACTIONS, good, fold_map, reference

def vector(features):
    n = features["n"]
    # Ratios in the frozen schema are integer source counts divided by n.
    result = {}
    for name, v in features.items():
        if name == "n":
            result[name] = Fraction(1, n)
        elif name == "has_ipe_c":
            result[name] = int(v)
        else:
            count = round(n*v)
            assert abs(count/n-v) < 1e-9
            result[name] = Fraction(count, n)
    return result

def select(donors, default):
    best = default
    best_gain = 0
    for action in ACTIONS:
        changes = defaultdict(list)
        safe = True
        for r in donors:
            a, b = r["metrics"][action], r["metrics"][r["keep"]]
            if any(a.get(k,0) < b.get(k,0) for k in a.keys() | b.keys()):
                safe = False
                break
            changes[r["group"]].append(Fraction(a["primary"]-b["primary"],r["denom"]))
        if safe and changes:
            gain = mean(mean(v) for v in changes.values())
            if gain > best_gain:
                best, best_gain = action, gain
    return best

def run():
    raw = json.loads((prior/"MATRIX.json").read_text())["rows"]
    rows = [r for r in raw if good(r)]
    folds = fold_map(rows)
    fold = lambda r: folds[r["domain"],r["group"]]
    # Factor the small set of distinct vectors to avoid repeated exact rational arithmetic.
    signatures = {r["uid"]:tuple(sorted(vector(r["features"]).items())) for r in rows}
    totals = defaultdict(Counter)
    for r in rows:
        v = signatures[r["uid"]]
        training = [q for q in rows if fold(q)!=fold(r) and q["group"] != r["group"]]
        by_signature = defaultdict(list)
        for q in training:
            by_signature[signatures[q["uid"]]].append(q)
        distances = {s:sum(abs(a[1]-b[1]) for a,b in zip(v,s)) for s in by_signature}
        nearest = min(distances.values())
        sets = {"exact":by_signature.get(v,[]),
                "nearest":[q for s,d in distances.items() if d==nearest for q in by_signature[s]]}
        base = r["metrics"][r["keep"]]
        for name, donors in [("IPE-C",[]),("reference",[]),*sets.items()]:
            action = select(donors,r["keep"])
            m = reference(r) if name=="reference" else r["metrics"][action]
            diff = m["primary"]-base["primary"]
            t = totals[r["domain"],name]
            t.update(tasks=1,denominator=r["denom"],donor_hit=int(bool(donors)),
                     changed=int(action!=r["keep"]),wins=int(diff>0),losses=int(diff<0))
            t.update(m)
    assert len(rows)==296
    return {domain:{name:t for (d,name),t in totals.items() if d==domain}
            for domain in sorted({r["domain"] for r in rows})}

if __name__=="__main__":
    print(json.dumps(run(),indent=2,sort_keys=True))
