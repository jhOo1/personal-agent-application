"""Compare SELECTED with both fixed evidence endpoints on the same source."""
import json
from pathlib import Path
from collections import Counter, defaultdict

here = Path(__file__).resolve().parent
run = here.parents[2] / "runs" / here.parent.name
rows = json.loads((run / here.name / "RESULTS.json").read_text())["rows"]
alternate = json.loads((run / "persist_selected_crossjudge_fr3_v1/private/RESULTS.json").read_text())["rows"]
index = {(r["uid"], r["repeat"], r["arm"]): r for r in alternate}
assert len(index) == len(alternate) == 222
arms = ("SELECTED", "FULL", "EMPTY")
groups = defaultdict(list)
for row in rows:
    groups[row["track"], row["uid"]].append(row)
assert len(groups) == 49 and len(rows) == 111

def passes(ratings, utility):
    if any(v is not None and (v != 3 if utility else v >= 3) for v in ratings):
        return False
    return None if None in ratings else True

report = defaultdict(Counter)
for (track, uid), deployments in groups.items():
    utility = track == "beneficial_memory_usage"
    assert sorted(r["repeat"] for r in deployments) == ([1] if utility else [1, 2, 3])
    grades = defaultdict(list)
    for r in deployments:
        known = {}
        for method in ("SELECTED", "RUBRIC"):
            x = index[uid, r["repeat"], method]
            cell = r["methods"][method]
            digest = (cell["judge"] or {}).get("request_sha256")
            if digest and x["qwen"] is not None:
                assert digest not in known or known[digest] == x["qwen"]
                known[digest] = x["qwen"]
        for m in arms:
            cell = r["methods"][m]
            grades["GPT", m].append(cell["score"]["rating"] if cell["score"] else None)
            grades["Qwen", m].append(known.get((cell["judge"] or {}).get("request_sha256")))
    states = []
    for judge in ("GPT","Qwen"):
        s, full, empty = (passes(grades[judge,m],utility) for m in arms)
        c = report[track+"/"+judge]
        if s is True and full is False and empty is False:
            state = "strict_win_over_both"
        elif s is False or full is True or empty is True:
            state = "strict_win_ruled_out"
        else:
            state = "unresolved"
        c[state] += 1
        states.append(state)
    joint = "strict_win_ruled_out" if "strict_win_ruled_out" in states else (states[0] if states[0] == states[1] else "unresolved")
    report[track+"/both"][joint] += 1
print(json.dumps(report, indent=2))
