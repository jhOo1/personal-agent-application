"""Compare joint delivery on archived, score-request-matched external outputs."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

here = Path(__file__).resolve().parent
sys.path.insert(0, str(here.parent / "external_pool_frontier_v1"))
from replay import candidates, measure, aligned, read, sha

gate = "GEPA_SELECTED_BOUNDS"
rows = read(here.parent/"paired_regret_policy_v1/MATRIX.json")["rows"]
panel = {r["uid"]:dict(benchmark="BenchPreS", group=r["group"]) for r in rows if r["domain"]=="BenchPreS"}
assert len(panel)==48
cells = defaultdict(dict)
missed = {}
for uid, name, answer, score, flags in candidates(panel):
    value = measure("BenchPreS", "", score)
    if value is None:
        continue
    attrs = sorted((d["preference"],d["appropriate"]) for d in score["decisions"])
    if name == gate:
        missed[uid] = sorted(d["preference"].partition(" prefers ")[2] for d in score["decisions"] if d["appropriate"] and d["label"]!="follow")
    cell = (value, attrs, sha(answer))
    if name in cells[uid]:
        assert cells[uid][name]==cell
    cells[uid][name]=cell

def passed(v, omit_bold):
    appropriate = v["nonbold"]==v["nonbold_denominator"] if omit_bold else v["primary"]==v["positions"]
    return appropriate and v["MR"]==0 and v["completeness"]==5

results = {}
for ref in sorted({m for c in cells.values() for m in c} - {gate}):
    report = Counter()
    external_only = []
    for uid in panel:
        c=cells[uid]
        if gate not in c or ref not in c:
            report["unpaired"]+=1
            continue
        a, labels_a, ha=c[gate]
        b, labels_b, hb=c[ref]
        assert labels_a==labels_b and aligned({"a":a,"b":b},("a","b"))
        if ha==hb and a!=b:
            report["same_text_score_conflict"]+=1
            continue
        report["paired"]+=1
        for prefix,omit in (("joint",False),("nonbold_required",True)):
            if omit and not a["nonbold_denominator"]:
                continue
            x,y=passed(a,omit),passed(b,omit)
            label = "both" if x and y else "gate_only" if x else "external_only" if y else "neither"
            report[prefix+"_"+label]+=1
            if y and not x and not omit:
                external_only.append(uid)
    results[ref]=dict(counts=report, external_only_profiles=len({panel[u]["group"] for u in external_only}),
                      external_only_public_prefixes=sorted(u.split("/")[-1][:8] for u in external_only))
opportunities = {}
for uid, c in cells.items():
    if gate not in c:
        continue
    v = c[gate][0]
    winners = [m for m in c if m != gate and passed(c[m][0],False) and not passed(v,False) and
               (c[m][2] != c[gate][2] or c[m][0] == v)]
    if winners:
        opportunities[uid.split("/")[-1][:8]] = dict(methods=sorted(winners), gate=v, missed_attributes=missed[uid])
print(json.dumps(dict(pairs=results, opportunities=opportunities),indent=2,sort_keys=True))
