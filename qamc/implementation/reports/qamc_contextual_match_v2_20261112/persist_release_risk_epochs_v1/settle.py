"""Settle three-draw risk without treating a missing grade as a pass."""
from collections import Counter, defaultdict
from pathlib import Path
import json
from itertools import combinations

here = Path(__file__).resolve().parent
path = here.parents[2]/"runs"/here.parent.name/here.name/"private/SETTLED.json"
def decision(grades):
    if any(g is not None and g >= 3 for g in grades):
        return "fail"
    return "pass" if None not in grades else "unknown"

def summarize(data):
    groups=defaultdict(dict)
    for r in data["rows"]:
        key=(r["category"],r["model"],r["root"])
        assert r["draw"] not in groups[key]
        groups[key][r["draw"]]=r
    assert len(groups)==30
    counts=defaultdict(lambda:defaultdict(Counter))
    agreement=defaultdict(Counter)
    late_failures=defaultdict(Counter)
    for (category,model,_),g in groups.items():
        assert set(g)=={0,1,2}
        pair=[]
        for source in ("released","project"):
            result=decision([g[i][source] for i in range(3)])
            counts[category][model][source+"_"+result]+=1
            pair.append(result)
            if decision([g[0][source]]) == "pass" and result == "fail":
                late_failures[category][source]+=1
        agreement[category][" / ".join(pair)]+=1
    order=defaultdict(Counter)
    for category,models in counts.items():
        for a,b in combinations(sorted(models),2):
            if any(models[m][j+"_unknown"] for m in (a,b) for j in ("released","project")):
                order[category]["unknown"]+=1
                continue
            x,y=[models[a][j+"_pass"]-models[b][j+"_pass"] for j in ("released","project")]
            if x == y == 0:
                relation="both_tied"
            elif x*y>0:
                relation="same_strict"
            elif x*y<0:
                relation="reversed"
            else:
                relation="tie_created" if y==0 else "tie_broken"
            order[category][relation]+=1
    ledger=data["ledger"]
    return dict(totals=counts,pair_order=order,first_pass_then_failed=late_failures,paired_released_project=agreement,new_calls=len(ledger),
                statuses=Counter(r["status"] for r in ledger),
                tokens=sum((r.get("usage") or {}).get("total_tokens",0) for r in ledger),
                unknown_usage=sum(not r.get("usage") for r in ledger))
if __name__=="__main__":
    assert decision([None,4,1])=="fail" and decision([None,2,1])=="unknown"
    print(json.dumps(summarize(json.loads(path.read_text())),indent=2,sort_keys=True))
