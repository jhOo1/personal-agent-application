"""Compare the released selector to BOTH archived endpoints on identical soft-use tasks."""
import json
from collections import Counter, defaultdict
from pathlib import Path

here = Path(__file__).resolve().parent
runs = here.parents[2] / "runs" / here.parent.name
rows = json.loads((runs/"rpe_memgate_matched_actor_v1/RESULTS.json").read_text())["rows"]
arms = ("IPE_C","RPR_PAPER_FULL","MEMGATE_RP_ACTOR")
totals = defaultdict(Counter)
seen = set()
for r in rows:
    if not r["labels"] or "C" in r["labels"] or "B" not in r["labels"]:
        continue
    assert r["uid"] not in seen
    seen.add(r["uid"])
    s = [r["scores"][a] for a in arms]
    if not all(x.get("grade",{}).get("match") for x in s):
        continue
    vals = [x["grade"]["match"]["matched"] for x in s]
    size = len(r["labels"])
    assert all(x["grade"]["match"]["positions"]==size for x in s)
    shape = r["selection"]["shape"]
    if shape=="FULL":
        assert s[1]["answer_sha256"] == s[2]["answer_sha256"] and s[1]["grade"]==s[2]["grade"]
    for flag in ("all","clean"):
        if flag == "clean" and any(x.get("flags")!=[] for x in s):
            continue
        for scope in ("any",shape):
            t=totals[f"{flag}/{scope}"]
            t.update(tasks=1,positions=size,ipe=vals[0],full=vals[1],memgate=vals[2],
                     full_minus_ipe=vals[1]-vals[0],memgate_minus_full=vals[2]-vals[1],
                     beats_both=int(vals[2]>max(vals[:2])),loses_both=int(vals[2]<min(vals[:2])))
print(json.dumps(dict(rows_with_observed_B_no_C=len(seen),tables=totals),indent=2))
