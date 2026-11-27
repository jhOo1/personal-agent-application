"""Compare repeated deployment with the better completed full-history arm per task."""
from collections import Counter
from itertools import product
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE.parents[2] / "runs" / HERE.parent.name / HERE.name
METHODS = ("SELECTED_GEPA", "PB_RUBRIC", "PB_GEPA")


def read(name):
    return json.loads((RUN / name).read_text())


def measure():
    roster = read("FROZEN.json")["cases"]
    rows = read("RESULTS.json")["rows"]
    index = {(r["uid"],r["method"],r["draw"]):r for r in rows}
    assert len(index) == len(rows)
    expected = set()
    result = {}
    for uid, track in roster.items():
        bu = track == "beneficial_memory_usage"
        draws = 1 if bu else 3
        states = []
        for method in METHODS:
            failures = []
            for i in range(1,draws+1):
                key = (uid,method,i)
                expected.add(key)
                r = index[key]
                assert r["category"] == track
                score = r["score"]
                failures.append(None if score is None else score["failure_strict_utility" if bu else "failure_release"])
            states.append(1 if True in failures else None if None in failures else 0)
        combos = product(*[(0,1) if s is None else (s,) for s in states])
        diffs = [active-min(a,b) for active,a,b in combos]
        out = result.setdefault(track,Counter())
        out.update({"allocated":1,"min_difference":min(diffs),"max_difference":max(diffs)})
        if min(diffs)==max(diffs):
            out[{1:"loss",-1:"win",0:"tie"}[diffs[0]]] += 1
        else:
            out["unresolved"] += 1
        if diffs == [-1]:
            print("verified simultaneous win", track, uid, [index[uid,METHODS[0],i]["selected_count"] for i in range(1,draws+1)])
    assert set(index)==expected
    return {k:dict(v) for k,v in result.items()}


if __name__ == "__main__":
    print(json.dumps(measure(),indent=2))
