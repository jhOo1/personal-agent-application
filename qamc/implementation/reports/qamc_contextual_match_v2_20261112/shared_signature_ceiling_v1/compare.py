"""Retrospective feasibility of one shared action per observable signature."""
import json
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path
import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint

prior = Path(__file__).resolve().parent.parent/"paired_regret_policy_v1"
sys.path.insert(0,str(prior))
from portfolio import good, reference, ACTIONS
rows = [r for r in json.loads((prior/"MATRIX.json").read_text())["rows"] if good(r)]
domains = sorted({r["domain"] for r in rows})
assert len(rows) == 296

def solve(subset,signature,goal=None,targets=None):
    buckets=defaultdict(list)
    for row in subset:
        f=row["features"]
        key = (f["has_ipe_c"],) if signature=="bit" else tuple(sorted(f.items()))
        buckets[key].append(row)
    values=list(buckets.values())
    k=len(values)*len(ACTIONS)
    axes=sorted({(r["domain"],axis) for r in subset for axis in reference(r)})
    gains=np.zeros((len(axes),k))
    for i,group in enumerate(values):
        for r in group:
            for axis,ref in reference(r).items():
                line=axes.index((r["domain"],axis))
                for a,action in enumerate(ACTIONS):
                    gains[line,i*len(ACTIONS)+a]+=r["metrics"][action].get(axis,0)-ref
    assignments=np.kron(np.eye(len(values)),np.ones((1,len(ACTIONS))))
    floors=np.array([(targets or {}).get(domain,0) if axis=="primary" else 0 for domain,axis in axes])
    c=np.zeros(k) if goal is None else -gains[axes.index((goal,"primary"))]
    res=milp(c,integrality=np.ones(k),bounds=Bounds(0,1),
             constraints=[LinearConstraint(assignments,1,1),LinearConstraint(gains,floors,np.inf)])
    assert res.status in (0,2),res.message
    if res.status==0:
        x=np.rint(res.x)
        assert np.all(assignments@x==1) and np.all(gains@x>=floors)
    return {"signatures":len(values),"shared_across_domains":sum(len({r["domain"] for r in v})>1 for v in values),
            "feasible":res.status==0,"gain":int(round(-res.fun)) if goal and res.status==0 else None}

result={}
for mode in ("bit","complete"):
    solo={d:solve([r for r in rows if r["domain"]==d],mode,d) for d in domains}
    multi={}
    for n in (2,3):
        for ds in combinations(domains,n):
            s=[r for r in rows if r["domain"] in ds]
            v=solve(s,mode)
            if v["feasible"]:
                v["individual_optima_simultaneous"]=solve(s,mode,targets={d:solo[d]["gain"] for d in ds})["feasible"]
                v["conditional_max_gains"]={d:solve(s,mode,d)["gain"] for d in ds}
                v["conditional_maxima_simultaneous"]=solve(s,mode,targets=v["conditional_max_gains"])["feasible"]
            multi["+".join(ds)]=v
    result[mode]=dict(solo=solo,joint=multi)
print(json.dumps(result,indent=2,sort_keys=True))
