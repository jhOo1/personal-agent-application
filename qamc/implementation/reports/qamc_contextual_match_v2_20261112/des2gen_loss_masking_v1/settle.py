"""Summarize the two registered answers per source, recording unavailable pairs."""
from collections import Counter, defaultdict
import json
from pathlib import Path

here = Path(__file__).resolve().parent
run = here.parents[2] / "runs" / here.parent.name / here.name / "private"
read = lambda p: json.loads(p.read_text())
data = read(run / "RESULTS.json")
pin = read(run / "FROZEN.json")
prior = {r["uid"]:r for r in read(here.parent / "ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]}
grades = defaultdict(dict)
for r in data["rows"]:
    assert r["uid"] + "|" + r["arm"] in pin["wires"]
    grades[r["uid"]][r["arm"]] = r["score"]
assert len(data["rows"]) == len(pin["wires"]) == 2 * len(grades)
assert len({prior[u]["source_group"] for u in grades}) == len(grades)
total = defaultdict(Counter)
results = []
for u, pair in sorted(grades.items()):
    assert set(pair) == {"full","masked"}
    case = {"development_case":u.split("/",2)[-1]}
    for arm, v in pair.items():
        g = v["grade"]
        case[arm] = None if not g.get("match") else dict(match=g["match"], OPB=g["OPB"], UPB=g["UPB"], FM=g["FM"], flagged=bool(v["flags"]))
    if all(case[a] is not None for a in pair):
        for arm in pair:
            g = case[arm]
            total[arm].update(match=g["match"]["matched"], positions=g["match"]["positions"], OPB=g["OPB"], UPB=g["UPB"], FM=g["FM"])
    results.append(case)
ledger = data["ledger"]
cost = dict(requests=len(ledger), statuses=Counter(r["status"] for r in ledger), tokens=sum((r["usage"] or {}).get("total_tokens",0) for r in ledger), unknown_usage=sum(not r["usage"] for r in ledger))
print(json.dumps(dict(cases=results,common=total,cost=cost),indent=2))
