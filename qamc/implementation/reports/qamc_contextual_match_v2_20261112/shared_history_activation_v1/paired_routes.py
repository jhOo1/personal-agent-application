"""Inspect paired archived outcomes where the two exposure decisions differ."""
from collections import Counter
import json
from score import BASE, OUT, read

def paired_routes():
    choices = read(OUT / "DECISIONS.json")
    strata = read(OUT / "FROZEN.json")["assignments"]
    frontier = {r["uid"]: r for r in read(BASE / "selective_path_frontier_v1/RESULTS.json")["rows"]}
    arms = ("ordinary", "decision")
    totals = Counter()
    changes = []
    for uid, arm in choices.items():
        if uid not in frontier or not all(arm.get(k) for k in arms):
            continue
        row = frontier[uid]
        paths = {"FULL": "RPR_PAPER_FULL", "EMPTY": "TASK_ONLY"}
        cells = [row["cells"][paths[arm[k]]] for k in arms]
        if any(any(c["fields"].get(m) is None for m in ("OPB","UPB","FM")) for c in cells):
            continue
        if all(c["flags"] == [] for c in cells):
            totals.update(roots=1, positions=row["positions"], ordinary=cells[0]["matched"], decision=cells[1]["matched"])
        if arm["ordinary"] != arm["decision"]:
            changes.append(dict(uid=uid, stratum=strata[uid], paths=arm, match=[c["matched"] for c in cells],
                                flags=[c["flags"] for c in cells], positions=row["positions"]))
    records = [read(p) for p in (OUT.parent/"Exposure"/"visible").glob("*/record.json")]
    return dict(clean=totals, changes=changes, statuses=Counter(r["status"] for r in records),
                known_tokens=sum((r.get("usage") or {}).get("total_tokens") or 0 for r in records),
                unknown_usage=sum((r.get("usage") or {}).get("total_tokens") is None for r in records))

if __name__ == "__main__":
    print(json.dumps(paired_routes(), indent=2))
