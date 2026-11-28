"""Partition gains, losses and unresolved roots across two graders on the same final answers."""
from collections import Counter
from pathlib import Path
import json
from settle import verdict, runs, out, read

ref={(r["uid"],r["repeat"]):r for r in read(runs/"persist_selected_crossjudge_fr3_v1/private/RESULTS.json")["rows"] if r["arm"]=="SELECTED"}
rows={r["uid"]:[] for r in ref.values()}
for i in (1,2,3):
    for r in read(out/f"DRAW_{i}.json")["rows"]:
        rows[r["uid"]].append((r,ref[r["uid"],i]))

def preference(a,b):
    if a==b and a!="unknown":return "tie"
    if "unknown" in (a,b):return "unknown"
    return "direct" if a=="pass" else "routed"

counts={}
for uid,pairs in rows.items():
    track=pairs[0][0]["track"]
    table=counts.setdefault(track,Counter())
    directions=[]
    for g,k in (("gpt","old"),("qwen","qwen")):
        d=verdict(track,[r[g] for r,s in pairs])
        s=verdict(track,[s[k] for r,s in pairs])
        directions.append(preference(d,s))
    table["/".join(directions)]+=1
print(json.dumps(counts,indent=2))
