"""Aggregate only strictly paired method outcomes; retain per-run denominators."""
import json
from collections import Counter
from pathlib import Path

here=Path(__file__).resolve().parent
out=here.parents[2]/"runs"/here.parent.name/here.name
statuses=Counter()
tokens=unknown=0
replicates=[]
table=[]
for i in (1,2):
    data=json.loads((out/f"deployment{i}"/"RESULTS.json").read_text())
    rows=data["rows"]
    assert len(rows)==len({r["group"] for r in rows})==18
    statuses.update(r["status"] for r in data["ledger"])
    for receipt in data["ledger"]:
        usage=(receipt.get("usage") or {}).get("total_tokens")
        tokens+=usage or 0
        unknown+=usage is None
    replicates.append({r["uid"]:r for r in rows})
    for scope in ("all","all_A","B_only","contains_C"):
        sample=[r for r in rows if scope=="all" or r["stratum"]==scope]
        paired=[r for r in sample if r["branch"] and all(x["grade"].get("match") for x in r["scores"].values())]
        for method in ("IPE_C","TASK_ONLY","RP_FULL"):
            grades=[r["scores"][r["branch"] if method=="IPE_C" else method]["grade"] for r in paired]
            table.append(dict(deployment=i,scope=scope,method=method,assigned=len(sample),paired=len(paired),
                              positions=sum(g["match"]["positions"] for g in grades),
                              match=sum(g["match"]["matched"] for g in grades),
                              severity={m:[sum(g[m] for g in grades if m in g),sum(m in g for g in grades)] for m in ("OPB","UPB","FM")}))
a,b=replicates
assert a.keys()==b.keys()
routes=Counter((a[u]["branch"] or "UNKNOWN",b[u]["branch"] or "UNKNOWN") for u in a)
report=["# Fresh IPE-C deployments on 18 exposed development roots","",
        "Each deployment made fresh estimator, generator and grader calls. IPE-C uses the physical answer and grade of its preselected endpoint. Each row below uses the same complete tasks across all three methods. The second deployment repeats the same roots.","",
        "| Deployment | Stratum | Paired / assigned | Positions | IPE-C | Task only | Full RP |",
        "|---|---|---:|---:|---:|---:|---:|"]
for j in range(0,len(table),3):
    r,t,f=table[j:j+3]
    report.append(f"| {r['deployment']} | {r['scope']} | {r['paired']}/{r['assigned']} | {r['positions']} | {r['match']} | {t['match']} | {f['match']} |")
report+=["","Route pairs by root (first → second): "+", ".join(f"{x} → {y}: {v}" for (x,y),v in sorted(routes.items()))+".","",
         f"Physical requests: {sum(statuses.values())}, statuses {dict(statuses)}, reported tokens {tokens:,}, unknown usage {unknown}.",
         "","[Protocol](PROTOCOL.md) · [Severity totals and denominators](SUMMARY.json)"]
(here/"RESULTS.md").write_text("\n".join(report)+"\n")
(here/"SUMMARY.json").write_text(json.dumps(table,indent=2)+"\n")
