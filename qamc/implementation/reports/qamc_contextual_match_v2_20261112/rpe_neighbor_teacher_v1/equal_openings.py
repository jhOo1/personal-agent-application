"""Compare nested uniform thinning or padding of the already frozen switches."""
from contextlib import redirect_stdout
from fractions import Fraction
from io import StringIO
from pathlib import Path
import runpy

with redirect_stdout(StringIO()):
    old = runpy.run_path(str(Path(__file__).with_name("replay.py")))
rows = []
for r in old["archive"]:
    if r["uid"] not in old["decisions"]:
        continue
    cells = [r["scores"].get(k) or {} for k in ("TASK_ONLY", "RPR_PAPER_FULL", "IPE_C")]
    if not all((c.get("grade") or {}).get("match") for c in cells):
        continue
    endpoints = [c["grade"] for c in cells[:2]]
    assert all(g["match"]["positions"] == len(r["labels"]) for g in endpoints)
    rows.append((endpoints, old["decisions"][r["uid"]], r["old_route"] == old["on"]))

def expected(policy, target):
    opened = sum(row[policy] for row in rows)
    n = len(rows)
    keep = min(Fraction(target, opened), 1)
    add = max(Fraction(target-opened, n-opened), 0)
    totals = [0]*5
    weights = []
    for row in rows:
        p = keep if row[policy] else add
        weights.append(p)
        for w, g in zip((1-p,p), row[0]):
            m = g["match"]
            values = [m["matched"], int(m["matched"]==m["positions"]), g["OPB"], g["UPB"], g["FM"]]
            totals = [x+w*y for x,y in zip(totals,values)]
    assert sum(weights) == target
    return totals

assert len(rows)==216
print("|History openings|Rule|Expected Match / 1142|Expected exact / 216|Expected OPB|Expected UPB|Expected FM|")
print("|---:|---|---:|---:|---:|---:|---:|")
for target in (72,100):
    for policy, name in ((1,"neighbor"), (2,"IPE-C")):
        values=expected(policy,target)
        ref=old["summary"]["common","transfer" if policy==1 else "IPE-C"]
        if ref["on"] == target:
            assert values==[ref[k] for k in ("match","exact","OPB","UPB","FM")]
        print("|"+ "|".join([str(target),name,*[f"{float(x):.2f}" for x in values]])+"|")
