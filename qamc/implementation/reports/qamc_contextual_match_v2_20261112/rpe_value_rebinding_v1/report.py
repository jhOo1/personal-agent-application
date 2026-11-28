"""Summarize only from settled receipts, with symmetric missingness and flags."""
import json
from collections import Counter
from pathlib import Path

here=Path(__file__).resolve().parent
out=here.parents[2]/"runs"/here.parent.name/here.name
old=out.parent/"rpe_remaining_roots_deployment_v1/deployment1"
read=lambda p:json.loads(p.read_text())
baseline={r["uid"]:r for r in read(old/"RESULTS.json")["rows"]}
data=read(out/"RESULTS.json")
rows={u:{"IPE_C":r["scores"][r["branch"]]} for u,r in baseline.items()}
states=Counter()
for row in data["rows"]:
    rows[row["uid"]][row["arm"]]=row["score"]
    states[(row["arm"],row["action"])]+=1
eligible={u for u,arms in rows.items() if all(s["grade"].get("match") for s in arms.values())}
tables={}
for scope in ("all","all_A","B_only","contains_C","flag_free"):
    chosen=[u for u in eligible if scope=="all" or baseline[u]["stratum"]==scope or
            (scope=="flag_free" and all(s["flags"]==[] for s in rows[u].values()))]
    table={}
    for arm in ("IPE_C","GENERIC","VALUE"):
        t=Counter()
        for uid in chosen:
            g=rows[uid][arm]["grade"]; m=g["match"]
            t.update(tasks=1,positions=m["positions"],match=m["matched"],whole=int(m["matched"]==m["positions"]))
            t.update({k:g[k] for k in ("OPB","UPB","FM")})
        table[arm]=dict(t)
    tables[scope]=table
ledger=data["ledger"]
print(json.dumps(dict(assigned=len(rows),actions={a:dict((s,c) for (k,s),c in states.items() if k==a)
                  for a in ("GENERIC","VALUE")},tables=tables,
                  physical=Counter(r["unit"]["stage"] for r in ledger),statuses=Counter(r["status"] for r in ledger),
                  reported_tokens=sum((r.get("usage") or {}).get("total_tokens") or 0 for r in ledger),
                  unknown_usage=sum((r.get("usage") or {}).get("total_tokens") is None for r in ledger),
                  retries=sum(r["automatic_retries"] for r in ledger)),indent=2))
