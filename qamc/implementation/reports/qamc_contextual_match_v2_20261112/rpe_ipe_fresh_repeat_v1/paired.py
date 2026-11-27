"""Compute within-deployment route benefit and repeat variability on matched roots."""
import json
from collections import Counter
from pathlib import Path

here=Path(__file__).resolve().parent
out=here.parents[2]/"runs"/here.parent.name/here.name
def load(i):
    return {r["uid"]:r for r in json.loads((out/f"deployment{i}"/"RESULTS.json").read_text())["rows"]}
a,b=load(1),load(2)
assert set(a)==set(b) and len(a)==18

def match(row, method):
    arm=row["branch"] if method=="IPE_C" else method
    return row["scores"].get(arm,{}).get("grade",{}).get("match",{}).get("matched")

data={}
for comparator in ("RP_FULL","TASK_ONLY"):
    pairs=[]
    for uid in sorted(a):
        changes=[]
        for run in (a,b):
            r=run[uid]
            routed,control=match(r,"IPE_C"),match(r,comparator)
            changes.append(None if routed is None or control is None else routed-control)
        pairs.append(changes)
    complete=[p for p in pairs if None not in p]
    data[comparator]=dict(assigned=len(pairs),fully_known=len(complete),
                          repeat_direction_counts=dict(Counter("/".join("win" if d>0 else "loss" if d<0 else "tie" for d in p) for p in complete)),
                          complete_root_net=sum(sum(p) for p in complete))
data["within_path"]={}
for method in ("RP_FULL","TASK_ONLY","IPE_C"):
    both=[(match(a[u],method),match(b[u],method)) for u in a]
    diffs=[y-x for x,y in both if x is not None and y is not None]
    data["within_path"][method]=dict(roots=len(diffs), changed_match=sum(d!=0 for d in diffs),
                                     absolute_match_difference=sum(abs(d) for d in diffs))
(here/"PAIRED.json").write_text(json.dumps(data,indent=2)+"\n")
