"""Join by exact source and generation slot, using only the common project grader."""
import json
from collections import Counter, defaultdict
from pathlib import Path
from settle import decision

here = Path(__file__).resolve().parent
runs = here.parents[2]/"runs"/here.parent.name
def read(name):
    return json.loads((runs/name).read_text())["rows"]

first = read("persist_released_grade_agreement_v1/private/SETTLED.json")
risk = read("persist_release_risk_epochs_v1/private/SETTLED.json")
grades = defaultdict(dict)
external = {r["model"] for r in first}
roots = {r["root"]: r["category"] for r in first}
utility = "beneficial_memory_usage"
def add(track, root, method, draw, value):
    assert root in roots and roots[root] == track
    cells = grades[root, method]
    assert draw not in cells
    cells[draw] = value
for r in first:
    if r["category"] == utility:
        add(utility,r["root"],r["model"],0,r["project"])
for r in risk:
    add(r["category"],r["root"],r["model"],r["draw"],r["project"])
internal = {"SELECTED","GROUP","FULL","EMPTY","RUBRIC"}
for r in read("persist_exposure_fr3_v1/RESULTS.json"):
    if r["uid"] in roots:
        assert r["methods"].keys() == internal
        for arm, content in r["methods"].items():
            add(r["track"],r["uid"],arm,r["repeat"]-1,(content["score"] or {}).get("rating"))
summary = defaultdict(lambda: defaultdict(Counter))
pairs = defaultdict(lambda: defaultdict(Counter))
for root, track in roots.items():
    states = {}
    for method in sorted(external | internal):
        values = grades[root,method]
        assert set(values) == ({0} if track==utility else {0,1,2})
        states[method] = ("unknown" if values[0] is None else "pass" if values[0]==3 else "fail") if track==utility else decision(list(values.values()))
        summary[track][method][states[method]] += 1
    for method in sorted(external | (internal-{"SELECTED"})):
        a,b = states["SELECTED"],states[method]
        outcome = "unknown" if "unknown" in (a,b) else "tie" if a==b else "win" if a=="pass" else "loss"
        pairs[track][method][outcome] += 1
print(json.dumps(dict(states=summary,selected_pairs=pairs),indent=2,sort_keys=True))
