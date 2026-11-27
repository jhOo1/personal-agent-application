"""Post hoc allocation diagnostic on the already exposed utility panel."""
import json
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
here = Path(__file__).resolve().parent
runs = here.parents[2]/"runs"/here.parent.name
fresh = json.loads((runs/"persist_utility_fresh_deployment_v1/private/SETTLED.json").read_text())
summary = json.loads((here/"SUMMARY.json").read_text())
by_uid = defaultdict(dict)
for row in fresh["rows"]:
    by_uid[row["uid"]][row["arm"]] = row["Qwen"]
ids = sorted(by_uid)
known = {u for u in ids if all(by_uid[u][a] is not None for a in ("SELECTED","FULL"))}
open_count = summary["routes"]["utility"]["style"]
hist = Counter()
for chosen in combinations(ids, open_count):
    opened = set(chosen)
    gain = sum(int(by_uid[u]["FULL"] == 3) - int(by_uid[u]["SELECTED"] == 3) for u in known & opened)
    hist[gain] += 1
observed = summary["tables"]["utility_Qwen"]["paired"]["SELECTED"]["win"] - summary["tables"]["utility_Qwen"]["paired"]["SELECTED"].get("loss",0)
print(json.dumps(dict(assigned=len(ids), fully_graded_pairs=len(known),opened=open_count,
                      gain_histogram=hist, assignments=sum(hist.values()), observed=observed,
                      at_least_observed=sum(n for gain,n in hist.items() if gain>=observed)),indent=2))
