"""Bound hidden-B errors compatible with the archived aggregate grades."""
from collections import Counter
import json
from pathlib import Path

TRANSITIONS = {"A": (1, 4), "B": (1, 2), "C": (2, 4)}
FIELDS = {"OPB": 1, "UPB": 2, "RII": 4}


def bounds(row):
    grade = row["base_scores"]
    required = sum(bit for name, bit in FIELDS.items() if grade["fields"].get(name, 0) > 0)
    forbidden = sum(bit for name, bit in FIELDS.items() if name in grade["fields"] and grade["fields"][name] == 0)
    errors = len(row["positions"]) - grade["matched"]
    reached = {(0, 0, 0)}
    for position in row["positions"]:
        hidden_b = position["author_label"] == "B" and position["state"] == "HIDDEN"
        reached |= {
            (wrong + 1, mask | bit, hidden_wrong + hidden_b)
            for wrong, mask, hidden_wrong in reached if wrong < errors
            for bit in TRANSITIONS[position["author_label"]] if not bit & forbidden
        }
    feasible = [hidden for wrong, mask, hidden in reached
                if wrong == errors and mask & required == required]
    return (min(feasible), max(feasible)) if feasible else None


def main():
    path = Path(__file__).resolve().parent.parent / "strong_actor_boundary_audit_v1" / "CENSUS.json"
    totals, forced = Counter(), set()
    for row in json.loads(path.read_text())["RPEval"]["roots"]:
        if not any(p["author_label"] == "B" and p["state"] == "HIDDEN" for p in row["positions"]):
            continue
        totals["roots"] += 1
        if not isinstance(row["base_scores"]["matched"], int):
            totals["missing_match"] += 1
            continue
        interval = bounds(row)
        if interval is None:
            totals["incompatible"] += 1
            continue
        lower, upper = interval
        totals.update(lower=lower, upper=upper, forced_roots=bool(lower))
        if lower:
            forced.add(row["group"])
    print(json.dumps({**totals, "forced_groups": len(forced)}, sort_keys=True))


if __name__ == "__main__":
    main()
