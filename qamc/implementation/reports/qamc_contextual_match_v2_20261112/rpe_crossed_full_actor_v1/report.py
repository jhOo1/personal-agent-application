"""Public aggregate; private grades and immutable dispatch receipts stay local."""
import json
from collections import defaultdict,Counter
from pathlib import Path
here=Path(__file__).resolve().parent
run=here.parents[2]/"runs"/here.parent.name/here.name
data=json.loads((run/"private_v2/SETTLED.json").read_text())
groups=defaultdict(dict)
for r in data["rows"]:groups[r["uid"]][r["arm"]]=r
assert len(groups)==8 and all(set(g)=={"QQ","QG","GQ","GG"} for g in groups.values())
metrics=defaultdict(lambda:defaultdict(Counter))
per_root={}
available=Counter()
for uid,g in groups.items():
    for arm,r in g.items():
        if r["score"]["grade"].get("match"):available[arm]+=1
    if not all(r["score"]["grade"].get("match") for r in g.values()):
        continue
    clean=all(r["score"]["flags"]==[] for r in g.values())
    per_root[uid.rsplit("/",2)[1]+"/"+uid.split("/")[-1]]={a:r["score"]["grade"]["match"]["matched"] for a,r in g.items()}
    for scope in ["common"]+(["clean"] if clean else []):
        for arm,r in g.items():
            s=r["score"]["grade"];m=s["match"]
            metrics[scope][arm].update(n=1,positions=m["positions"],match=m["matched"],exact=int(m["positions"]==m["matched"]),OPB=s["OPB"],UPB=s["UPB"],FM=s["FM"])
l=data["ledger"]
print(json.dumps(dict(available=available,metrics=metrics,per_root=per_root,origin=Counter(r["origin"] for r in data["rows"]),
                      requests=Counter(r["unit"]["stage"] for r in l),statuses=Counter(r["status"] for r in l),
                      tokens=sum((r["usage"] or {}).get("total_tokens",0) for r in l),unknown_usage=sum(not r["usage"] for r in l)),indent=2))
