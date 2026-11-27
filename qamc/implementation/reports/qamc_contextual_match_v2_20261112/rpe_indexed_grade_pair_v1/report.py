"""Compare fixed answers across the two contemporary measurement conditions."""
import json
from collections import Counter, defaultdict
from pathlib import Path

here=Path(__file__).resolve().parent
root=here.parents[2]/"runs"/here.parent.name/here.name
data=json.loads((root/"private/SETTLED.json").read_text())
tables=defaultdict(lambda:defaultdict(Counter))
direction=defaultdict(Counter)
missing=Counter()
for row in data["rows"]:
    labels=row["labels"]
    strata=["all","contains_C" if "C" in labels else "contains_B" if "B" in labels else "all_A"]
    if row["uid"].endswith("explicit/056"):
        strata.append("known_056")
    scores={a:row[a]["grade"].get("match") for a in ("archive","original","indexed")}
    for a,m in scores.items():
        if not m:
            missing[a]+=1
    if not all(scores.values()):
        continue
    for s in strata:
        for a,m in scores.items():
            assert m["positions"]==len(labels)
            tables[s][a].update(tasks=1,positions=len(labels),match=m["matched"],exact=int(m["matched"]==len(labels)),
                                flagged=int(bool(row[a]["flags"])))
        for left,right in (("archive","original"),("original","indexed")):
            diff=scores[right]["matched"]-scores[left]["matched"]
            direction[s][left+"_"+right+"_"+("up" if diff>0 else "down" if diff<0 else "tie")]+=1
l=data["ledger"]
print(json.dumps(dict(assigned=len(data["rows"]),tables=tables,directions=direction,missing=missing,
                      requests=len(l),status=Counter(r["status"] for r in l),
                      tokens=sum((r.get("usage") or {}).get("total_tokens",0) for r in l),
                      unknown_usage=sum(not r.get("usage") for r in l)),indent=2))
