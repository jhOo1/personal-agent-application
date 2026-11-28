"""Fixed third deployment. Earlier draws are separate reserve sensitivity analyses."""
from collections import Counter, defaultdict
import json
from pathlib import Path
from nested_selection import use_reserve
from check_exposure_fr3 import prepare
from complete import select
from qamc.common import sha

here = Path(__file__).resolve().parent
runs = here.parents[2] / "runs" / here.parent.name
def rows(path):
    return json.loads(path.read_text())["rows"]

cases, inputs, _, _, _ = prepare()
evidence = {}
for r in rows(runs / "persist_exposure_fr3_v1/RESULTS.json"):
    uid = r["uid"]
    if r["track"] == "beneficial_memory_usage":
        continue
    sources = None
    if r["exposure"] is not None:
        sources = select(cases[uid], inputs[uid]["public"], r["route"]["answer"], r["selector"]["answer"])
        assert sha(sources) == r["exposure"]["sha256"]
    evidence[uid,r["repeat"]] = sources
grades = {(r["uid"],r["repeat"]):r for r in rows(runs/"persist_selected_crossjudge_fr3_v1/private/RESULTS.json")
          if r["arm"]=="SELECTED"}
roots = sorted({u for u,_ in evidence})
assert len(roots)==31 and len(evidence)==93
tables = defaultdict(Counter)
different = []
for reserve in (2,1):
    for uid in roots:
        primary, extra = evidence[uid,3], evidence[uid,reserve]
        nested = use_reserve(primary,extra)
        larger = bool(primary and extra and len(extra)>len(primary))
        assert not nested or larger
        if nested != larger:
            different.append([reserve,uid.split("/")[-1][:8]])
        for method, switch in (("primary",False),("nested",nested),("larger",larger)):
            for field in ("old","qwen"):
                idx = reserve if switch else 3
                score, baseline = [grades[uid,i][field] for i in (idx,3)]
                c = tables[f"{reserve}/{cases[uid]['category']}/{method}/{field}"]
                c["roots"] += 1
                c["switched"] += int(switch)
                c["unknown" if score is None else "fail" if score>=3 else "pass"] += 1
                if switch:
                    proposed = [0,1] if score is None else [int(score>=3)]
                    base = [0,1] if baseline is None else [int(baseline>=3)]
                    diffs = [a-b for a in proposed for b in base]
                    c["min_extra_failures"] += min(diffs)
                    c["max_extra_failures"] += max(diffs)
print(json.dumps({"decisions_differ":different,"tables":tables},indent=2))
