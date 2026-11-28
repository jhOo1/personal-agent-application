"""Join the existing protected-route roster to matched external answers by Gate lineage."""
from collections import Counter
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import runpy
import sys

base = Path(__file__).resolve().parent.parent
with redirect_stdout(StringIO()):
    external = runpy.run_path(str(base/"bench_external_joint_v1/compare.py"))
sys.path.insert(0,str(base/"paired_regret_policy_v1"))
from portfolio import good
rows = [r for r in external["rows"] if r["domain"]=="BenchPreS" and good(r)]
assert len(rows)==26
counts, potential, missing = Counter(), {}, Counter()
names = ["DES2GEN_FULL","MEMADAPTER_FULL","PAPER_SELECTIVITY"]
details = []
for r in rows:
    uid = r["uid"]
    cells = external["cells"][uid]
    gate = cells.get(external["gate"])
    if not gate:
        raise ValueError("missing Gate provenance")
    v, attrs, digest = gate
    m = r["metrics"]["G"]
    assert (digest,v["primary"],-v["MR"],v["completeness"],v["nonbold"],v["positions"]) == (
        r["answers"]["G"],m["primary"],m["MR"],m["completeness"],m["nonbold"],r["denom"])
    best_old = max(s["primary"] for s in r["metrics"].values())
    counts.update(old=best_old,positions=r["denom"],unrealized=r["denom"]-best_old)
    found=[]
    unrestricted=best_old
    for method in names:
        cell=cells.get(method)
        if not cell:
            missing[method]+=1
            missing[method+"_residual_positions"]+=r["denom"]-best_old
            continue
        other,labels,answer=cell
        assert labels==attrs and other["positions"]==v["positions"] and other["MR_denominator"]==v["MR_denominator"]
        if other["primary"] > best_old:
            details.append(dict(task=uid.split("/")[-1][:8], method=method, differences={k:other[k]-v[k] for k in ("primary","MR","nonbold","completeness")}))
        unrestricted=max(unrestricted,other["primary"])
        if other["primary"]>best_old and other["MR"]<=v["MR"] and other["nonbold"]>=v["nonbold"] and other["completeness"]>=v["completeness"]:
            found.append((method,other["primary"]-best_old))
    counts["unrestricted_added"]+=unrestricted-best_old
    if found:
        potential[uid.split("/")[-1][:8]]=found
    counts["added"]+=max((gain for _,gain in found),default=0)
    # A missing arm might improve wherever the old ceiling leaves space.
    if any(not cells.get(n) for n in names):
        counts["unresolved_extra"]+=r["denom"]-best_old-max((gain for _,gain in found),default=0)
assert counts["old"]==38 and counts["positions"]==44
print(json.dumps(dict(tasks=len(rows),references=names,counts=counts,qualified=potential,improvements=details,missing=missing),indent=2))

if "--inspect-private" in sys.argv:
    targets = {item["task"]:item["method"] for item in details}
    for uid,method,answer,score,_ in external["candidates"](external["panel"]):
        prefix = uid.split("/")[-1][:8]
        if prefix in targets and method in (targets[prefix], external["gate"]):
            print(prefix,method,answer)
