"""Summarize jointly usable endpoint outcomes; preserve all missing units."""
import json
from pathlib import Path
from collections import Counter
here=Path(__file__).resolve().parent
path=here.parents[2]/"runs"/here.parent.name/here.name/"private/SETTLED.json"
data=json.loads(path.read_text())
print("# Feasible-option generation versus generic prompting\n")
print("Two new Actor answers per assigned task, identical frozen source and policy packets, distinct additional guidance. Archival IPE-C, empty and full RP endpoints are same-task comparators. All scores use the detailed project RPEval grading adaptation. Development cases only.\n")
print("|Stratum|Assigned|Common|Positions|Method|Match|OPB|UPB|FM|")
print("|---|---:|---:|---:|---|---:|---:|---:|---:|")
for st in ("all","soft","ignore","hard"):
    rows=[r for r in data["rows"] if st=="all" or r["stratum"]==st]
    usable=[r for r in rows if all((g or {}).get("match") and all(isinstance(g.get(k),int) for k in ("OPB","UPB","FM")) for g in r["methods"].values())]
    for method in ("generic","feasible","IPE_C","TASK_ONLY","RPR_PAPER_FULL"):
        grades=[r["methods"][method] for r in usable]
        vals=[sum(g["match"]["matched"] for g in grades)]+[sum(g[k] for g in grades) for k in ("OPB","UPB","FM")]
        print(f"|{st}|{len(rows)}|{len(usable)}|{sum(g['match']['positions'] for g in grades)}|{method}|"+ "|".join(map(str,vals))+"|")
print(f"\nPhysical requests {data['requests']}; statuses {data['statuses']}; reported tokens {data['reported_tokens']}; unknown usage {data['unknown_usage']}. No human reviews.")
