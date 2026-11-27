"""Quantify source attribution noise at the input of the fixed Actor test."""
from collections import Counter
import json
from pathlib import Path
here=Path(__file__).resolve().parent
b=here.parent
def read(p):return json.loads(p.read_text())
pin=read(here.parents[2]/"runs"/b.name/here.name/"private/FROZEN.json")
rows={r["uid"]:r for r in read(b/"ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]}
roots=read(b/"counterfactual_rpeval_v41/FROZEN.json")["roots"]
print("\n## Input policies on soft-preference tasks\n")
for subset in ("Assigned four","Broader exposed archive with source and strict paired endpoint scores"):
    conf=Counter();n=0
    for r in roots:
        u=r["uid"]
        cells=rows[u]["scores"]
        if not all(cells[m]["grade"] and cells[m]["grade"].get("match") for m in ("TASK_ONLY","RPR_PAPER_FULL")):continue
        labels=rows[u]["labels"]
        if not labels or "B" not in labels or "C" in labels:continue
        if subset=="Assigned four" and pin["panel"].get(u)!="soft":continue
        assert len(labels)==len(r["original_sources"]) and [m["memory_id"] for m in r["original_sources"]]==[m["memory_id"] for m in r["archived_policy"]]
        conf.update((a,p["policy"]) for a,p in zip(labels,r["archived_policy"]));n+=1
    total=sum(v for (_,p),v in conf.items() if p=="B")
    print(f"{subset}: {n} tasks. Among {total} predicted B, {conf['B','B']} were author B and {conf['A','B']} were author A. Author B mapped to C: {conf['B','C']}; to A: {conf['B','A']}.")
