"""Reconstruct exact selected source sets before joining separately saved ratings."""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from nested_selection import use_reserve

here = Path(__file__).resolve().parent
sys.path.insert(0,str(here.parent / "persist_utility_fresh_deployment_v1"))
from inspect_answers import records
from trial import actor_request, branch, prepare, select, sha

runs = here.parents[2] / "runs" / here.parent.name
def load(p):
    return json.loads(p.read_text())
cases, inputs, protocol, _, _ = prepare()
original = {(r["uid"],r["repeat"]):r for r in load(runs/"persist_exposure_fr3_v1/RESULTS.json")["rows"]}
fresh_dir = runs/"persist_utility_fresh_deployment_v1/private"
route, selector, actors = [records(s) for s in ("Route","Select","Actor")]
decisions = {}
for uid, rep in original:
    if rep != 1:
        continue
    task = inputs[uid]["public"]
    def prior(i):
        r = original[uid,i]
        if r["exposure"] is None:
            return None
        s = select(cases[uid], task, r["route"]["answer"], r["selector"]["answer"])
        assert sha(s) == r["exposure"]["sha256"]
        return s
    reserve = prior(1)
    if cases[uid]["category"] == "beneficial_memory_usage":
        reqs = inputs[uid]["selection_requests"]
        r = route[sha(reqs["query"])]
        primary = select(cases[uid],task,r,selector[sha(reqs[branch(task,r)])])
        wire = actor_request(cases[uid],task["query"],primary,protocol,protocol["prompts"]["gepa"])
        assert sha(wire) in actors
    else:
        primary = prior(2)
    decisions[uid] = use_reserve(primary,reserve)
assert len(decisions) == 49
grades = {(r["uid"],r["repeat"]):r for r in load(runs/"persist_selected_crossjudge_fr3_v1/private/RESULTS.json")["rows"] if r["arm"]=="SELECTED"}
fresh = {r["uid"]:r for r in load(fresh_dir/"SETTLED.json")["rows"] if r["arm"]=="SELECTED"}
tables = defaultdict(Counter)
switches = []
for uid, changed in decisions.items():
    track = cases[uid]["category"]
    beneficial = track == "beneficial_memory_usage"
    if changed:
        switches.append(uid.split("/")[-1][:8])
    for judge, field in (("GPT","old"),("Qwen","qwen")):
        earlier = grades[uid,1][field]
        later = fresh[uid][judge] if beneficial else grades[uid,2][field]
        counts = tables[track+"/"+judge]
        def outcome(x):
            return None if x is None else (x==3 if beneficial else x<3)
        for method, rating in (("primary",later),("reserve",earlier),("nested", earlier if changed else later)):
            val = outcome(rating)
            counts[method + ("_missing" if val is None else "_pass" if val else "_fail")] += 1
        if changed:
            a,b = outcome(earlier),outcome(later)
            counts["switch_" + ("unknown" if None in (a,b) else "tie" if a==b else "win" if a else "loss")] += 1
print(json.dumps(dict(assigned=49,switches=sorted(switches),tables=tables),indent=2))
