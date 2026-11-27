"""All-assigned and paired outcomes on the new replicate only."""
import json
from collections import Counter, defaultdict
from pathlib import Path

HERE=Path(__file__).resolve().parent
RUN=HERE.parents[2]/"runs"/HERE.parent.name/HERE.name
def certified(row,judge):
    v=row[judge]
    return None if v is None else int(v==3)

def report():
    d=json.loads((RUN/"private/SETTLED.json").read_text())
    roots=defaultdict(dict)
    for r in d["rows"]:
        assert r["arm"] not in roots[r["uid"]]
        roots[r["uid"]][r["arm"]]=r
    tables=defaultdict(lambda:defaultdict(Counter));paired=defaultdict(lambda:defaultdict(Counter))
    delivered=Counter(); sizes=Counter()
    for u,cells in roots.items():
        assert set(cells)=={"SELECTED","FULL","RUBRIC"}
        sizes[str(cells["SELECTED"]["selection_count"])]+=1
        for arm,backup,name in (("SELECTED","RUBRIC","S_first"),("RUBRIC","SELECTED","R_first")):
            cells[name]=cells[arm] if cells[arm]["delivered"] else cells[backup]
        for arm,r in cells.items():delivered[arm]+=int(r["delivered"])
        for judge in ("GPT","Qwen"):
            v={a:certified(r,judge) for a,r in cells.items()}
            for a,n in v.items():tables[judge][a]["unknown" if n is None else "pass" if n else "fail"]+=1
            for a,b in (("SELECTED","FULL"),("SELECTED","RUBRIC"),("S_first","R_first")):
                x,y=v[a],v[b]
                t=paired[judge][a+" vs "+b]
                t["unknown" if None in (x,y) else "win" if x>y else "loss" if x<y else "tie"]+=1
                if a=="S_first" and b=="R_first" and not all(cells[n]["delivered"] for n in ("SELECTED","RUBRIC")):
                    # Both policies emit the same backing answer, so no paired difference even if ungraded.
                    continue
                t["low"]+=(0 if x is None else x)-(1 if y is None else y)
                t["high"]+=(1 if x is None else x)-(0 if y is None else y)
    ledger=d["ledger"]
    return dict(assigned=len(roots),delivered=delivered,selected_source_counts=sizes,tables=tables,pairs=paired,
                requests=len(ledger),status=Counter(x["status"] for x in ledger),
                tokens=sum((x["usage"] or {}).get("total_tokens",0) for x in ledger),
                unknown_usage=sum((x["usage"] or {}).get("total_tokens") is None for x in ledger))
if __name__=="__main__":print(json.dumps(report(),indent=2))
