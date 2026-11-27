"""Export paired aggregate scores only."""
from collections import Counter, defaultdict
import json
from pathlib import Path

here=Path(__file__).resolve().parent
data=json.loads((here.parents[2]/"runs"/here.parent.name/here.name/"private/SETTLED.json").read_text())
totals=defaultdict(Counter)
pairs=defaultdict(Counter)
avail=Counter()
details=[]
for r in data["rows"]:
    arms=("reference","review","screen")
    scores={a:r[a]["grade"] for a in arms}
    for a,s in scores.items():
        if s.get("match"):avail[a]+=1
    if not all(s.get("match") for s in scores.values()):continue
    for a,s in scores.items():
        m=s["match"]
        totals[a].update(tasks=1,positions=m["positions"],match=m["matched"],OPB=s["OPB"],UPB=s["UPB"],FM=s["FM"],flags=int(bool(r[a]["flags"])))
    for a in arms[:2]:
        diff=scores["screen"]["match"]["matched"]-scores[a]["match"]["matched"]
        pairs[a]["win" if diff>0 else "loss" if diff<0 else "tie"]+=1
    details.append(dict(case=r["uid"].split("formal_multi_v1/")[-1],**{a:s["match"]["matched"] for a,s in scores.items()}))
l=data["ledger"]
print(json.dumps(dict(assigned=len(data["rows"]),available=avail,common=totals,paired=pairs,details=details,requests=len(l),
    by_stage=Counter(r["unit"]["stage"] for r in l),statuses=Counter(r["status"] for r in l),
    tokens=sum((r.get("usage") or {}).get("total_tokens",0) for r in l),unknown_usage=sum(not r.get("usage") for r in l)),indent=2))
