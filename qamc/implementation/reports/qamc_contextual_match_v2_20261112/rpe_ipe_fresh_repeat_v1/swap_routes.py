"""Cross the two saved sets of route decisions with both sets of endpoint grades."""
import json
from pathlib import Path

report = Path(__file__).resolve().parent
runs = report.parents[2] / "runs" / report.parent.name / report.name
deployments = []
for wave in (1, 2):
    rows = json.loads((runs / f"deployment{wave}" / "RESULTS.json").read_text())["rows"]
    indexed = {row["uid"]: row for row in rows}
    assert len(rows) == len(indexed)
    deployments.append(indexed)
first, second = deployments
assert first.keys() == second.keys()
totals = [[0, 0], [0, 0]]
changes = []
omitted = []
positions = 0
for uid, a in first.items():
    b = second[uid]
    assert a["group"] == b["group"] and a["stratum"] == b["stratum"]
    endpoints = [r["scores"] for r in (a, b)]
    matches = [[s[k]["grade"].get("match") for k in ("TASK_ONLY", "RP_FULL")] for s in endpoints]
    if not all(m for pair in matches for m in pair):
        omitted.append(uid)
        continue
    assert len({m["positions"] for pair in matches for m in pair}) == 1
    positions += matches[0][0]["positions"]
    native = []
    for j, scores in enumerate(endpoints):
        full = scores["RP_FULL"]["grade"]["match"]["matched"]
        for i, route in enumerate((a["branch"], b["branch"])):
            delta = scores[route]["grade"]["match"]["matched"] - full
            totals[i][j] += delta
            if i == j:
                native.append(delta)
    if native[0] != native[1]:
        changes.append([uid, a["stratum"], a["branch"], b["branch"], *native])
print(json.dumps(dict(assigned=len(first), omitted=omitted, positions=positions,
                      route_by_endpoint_net_vs_full=totals, changed_net=changes), indent=2))
