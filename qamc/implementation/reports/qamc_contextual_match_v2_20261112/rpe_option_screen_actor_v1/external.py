"""Match external answers on the frozen generator panel; expose only counts."""
from collections import Counter, defaultdict
import json
from pathlib import Path

here=Path(__file__).resolve().parent
run=here.parents[2]/"runs"/here.parent.name/here.name
panel=json.loads((run/"private/SETTLED.json").read_text())["rows"]
methods=("DES2GEN_FULL","MEMADAPTER_FULL")
arch={(r["uid"],r["method"]):r for r in json.loads((here.parent/"rpeval_formal_multi_coverage_v1/RESULT_ROWS.json").read_text()) if r["method"] in methods}
tables={}
for name, rivals in (("des2gen",methods[:1]),("memadapter",methods[1:]),("all",methods)):
    totals=defaultdict(Counter)
    diff=defaultdict(Counter)
    for row in panel:
        grades={a:row[a]["grade"] for a in ("reference","review","screen")}
        grades.update({r:arch[row["uid"],r].get("native_fields") or {} for r in rivals})
        if not all(s.get("match") for s in grades.values()):
            continue
        for a,s in grades.items():
            match=s["match"]
            assert match["positions"]==grades["reference"]["match"]["positions"]
            totals[a].update(tasks=1,positions=match["positions"],match=match["matched"],OPB=s["OPB"],UPB=s["UPB"],FM=s["FM"])
            delta=grades["screen"]["match"]["matched"]-match["matched"]
            diff[a]["win" if delta>0 else "loss" if delta<0 else "tie"]+=1
    tables[name]=dict(totals=totals,screen_vs=diff)
print(json.dumps(tables,indent=2))
