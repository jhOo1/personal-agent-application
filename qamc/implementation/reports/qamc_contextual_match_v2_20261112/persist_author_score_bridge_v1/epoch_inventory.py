"""Inventory complete generation epochs, ignoring every historical grade."""
import json
from collections import Counter, defaultdict
from pathlib import Path

here = Path(__file__).resolve().parent
run = here.parents[2]/"runs"/here.parent.name/"persist_repeated_deployment_v1"
methods = {"SELECTED_GEPA", "PB_GEPA", "PB_RUBRIC"}
seen = defaultdict(dict)
for draw in (1, 2, 3):
    for row in json.loads((run/f"DRAW{draw}.json").read_text())["rows"]:
        key = (row["category"], row["uid"], row["method"])
        assert draw == row["draw"] and draw not in seen[key]
        seen[key][draw] = bool((row["answer"] or "").strip())
sources = defaultdict(dict)
counts = defaultdict(Counter)
for (category, uid, method), draws in seen.items():
    expected = {1} if category == "beneficial_memory_usage" else {1,2,3}
    assert set(draws) == expected
    sources[category,uid][method] = all(draws.values())
    counts[category].update(assigned_outputs=len(draws), available_outputs=sum(draws.values()),
                            complete_method_tuples=int(all(draws.values())))
for (category,uid), cells in sources.items():
    assert cells.keys() == methods
    counts[category].update(allocated_roots=1, complete_three_method_roots=int(all(cells.values())))
print(json.dumps(counts,indent=2,sort_keys=True))
