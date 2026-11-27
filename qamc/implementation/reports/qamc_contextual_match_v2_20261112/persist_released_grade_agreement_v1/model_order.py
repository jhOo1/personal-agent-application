"""Compare external-model pass counts before and after fixed-answer rescoring."""
import json
from collections import Counter
from itertools import combinations
from pathlib import Path

here = Path(__file__).resolve().parent
private = here.parents[2] / "runs" / here.parent.name / here.name / "private"
rows = json.loads((private / "SETTLED.json").read_text())["rows"]
models = sorted({r["model"] for r in rows})
assert len(models) == 5
result = {}
for track in sorted({r["category"] for r in rows}):
    data = { (r["model"],r["root"]):r for r in rows if r["category"] == track }
    roots = {root for _,root in data}
    assert len(data) == len(roots)*len(models)
    counts = {}
    for m in models:
        scores = {}
        for judge in ("released","project"):
            grades = [data[m,root][judge] for root in roots]
            assert all(type(v) is int for v in grades)
            scores[judge] = sum(v == 3 if track=="beneficial_memory_usage" else v<3 for v in grades)
        counts[m] = scores
    directions = Counter()
    for a,b in combinations(models,2):
        x,y = [counts[a][j]-counts[b][j] for j in ("released","project")]
        directions["same_strict" if x*y>0 else "reversed" if x*y<0 else
                   "both_tied" if x==y==0 else "tie_created" if y==0 else "tie_broken"] += 1
    result[track] = dict(roots=len(roots),passes=counts,pair_order=directions)
assert len(rows)==65
print(json.dumps(result,indent=2))
