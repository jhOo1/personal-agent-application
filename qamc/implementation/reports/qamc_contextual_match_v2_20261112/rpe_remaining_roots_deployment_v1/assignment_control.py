"""Exact same-rate comparison of task assignment on saved physical answers."""
from collections import Counter
from math import comb
from pathlib import Path
import json
import sys


def assignment_control(rows):
    valid = [r for r in rows if r["branch"] in ("TASK_ONLY", "RP_FULL") and
             all(s["grade"].get("match") for s in r["scores"].values())]
    totals = Counter()
    changes = []
    full_count = 0
    for row in valid:
        scores = row["scores"]
        empty = scores["TASK_ONLY"]["grade"]["match"]
        full = scores["RP_FULL"]["grade"]["match"]
        assert empty["positions"] == full["positions"]
        totals["positions"] += empty["positions"]
        totals["empty"] += empty["matched"]
        change = full["matched"] - empty["matched"]
        changes.append(change)
        if row["branch"] == "RP_FULL":
            full_count += 1
            totals["selected_change"] += change
    # A histogram indexed by subset size permits exact evaluation on larger panels.
    hist = [Counter({0: 1})] + [Counter() for _ in range(full_count)]
    for i, delta in enumerate(changes):
        for n in range(min(i + 1, full_count), 0, -1):
            for score, count in hist[n - 1].items():
                hist[n][score + delta] += count
    distribution = hist[full_count]
    assignments = sum(distribution.values())
    assert assignments == comb(len(valid), full_count)
    return dict(paired=len(valid), full=full_count, positions=totals["positions"],
                actual=totals["empty"] + totals["selected_change"],
                assignment_count=assignments,
                at_least_actual=sum(v for k, v in distribution.items() if k >= totals["selected_change"]),
                mean=totals["empty"] + sum(k * v for k, v in distribution.items()) / assignments,
                min=totals["empty"] + min(distribution), max=totals["empty"] + max(distribution))


if __name__ == "__main__":
    folder = Path(sys.argv[1])
    result = []
    for n in (1, 2):
        rows = json.loads((folder / f"deployment{n}/RESULTS.json").read_text())["rows"]
        result.append(dict(deployment=n, **assignment_control(rows)))
    print(json.dumps(result, indent=2))
