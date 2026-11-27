"""Score-informed answer-pool limits on jointly graded C-bearing development tasks."""
import json
from collections import Counter
from replay import BASE, common_rows

fields = ("Judge","OPB","UPB","FM")
totals = Counter()
gains = Counter()
for row, arms in common_rows():
    if "C" not in row["labels"]:
        continue
    initial = arms[BASE]
    n = len(row["labels"])
    m = initial["match"]["matched"]
    allowed = []
    for grade in arms.values():
        assert all(type(grade[f]) is int and 0 <= grade[f] <= 5 for f in fields)
        if all(grade[f] <= initial[f] for f in fields):
            allowed.append(grade["match"]["matched"])
    strict = max(g["match"]["matched"] for g in arms.values()
                 if all(g[f] <= initial[f] for f in (*fields, "RII", "VG")))
    best = max(g["match"]["matched"] for g in arms.values())
    protected = max(allowed)
    totals.update(tasks=1, positions=n, initial=m, oracle=best, protected=protected,
                  opportunity=int(best>m), protected_opportunity=int(protected>m),
                  all_severity_protected=strict, all_severity_opportunity=int(strict>m), exact=int(best==n), protected_exact=int(protected==n))
    if protected>m:
        gains[row["source_group"]] += protected-m
print(json.dumps(dict(totals=totals, protected_gain_groups=len(gains),
                      gains_by_group_descending=sorted(gains.values(),reverse=True)),indent=2))
