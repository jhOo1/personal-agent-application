"""Decompose the existing strict-Match differences by paired whole-task outcome."""
import json
from collections import Counter, defaultdict
from pathlib import Path
from replay import BASE, common_rows

def analyze():
    totals = defaultdict(lambda: defaultdict(lambda: defaultdict(Counter)))
    seen = set()
    for row, arms in common_rows():
        uid = row["uid"]
        assert uid not in seen
        seen.add(uid)
        labels = row["labels"]
        group = "contains_C" if "C" in labels else "only_B" if "B" in labels else "all_A"
        n = len(labels)
        current = arms[BASE]["match"]["matched"]
        for method, grade in arms.items():
            if method == BASE:
                continue
            other = grade["match"]["matched"]
            assert grade["match"]["positions"] == n and 0 <= other <= n and 0 <= current <= n
            pair = ("both_exact" if other == n else "only_ipe_exact") if current == n else (
                "only_reference_exact" if other == n else "neither_exact")
            for stratum in ("all", group):
                totals[stratum][method][pair].update(
                    tasks=1, positions=n, ipe_match=current, reference_match=other,
                    gains=max(0, current-other), losses=max(0, other-current))
    previous = json.loads((Path(__file__).parent / "RESULTS.json").read_text())
    for stratum, methods in totals.items():
        for method, bins in methods.items():
            for field, source, expected in (("tasks",method,"tasks"), ("positions",method,"positions"),
                                           ("ipe_match",BASE,"matched"), ("reference_match",method,"matched")):
                assert sum(c[field] for c in bins.values()) == previous[stratum][source][expected]
            for method_name, only in ((BASE,"only_ipe_exact"),(method,"only_reference_exact")):
                assert bins.get("both_exact",{}).get("tasks",0) + bins.get(only,{}).get("tasks",0) == previous[stratum][method_name]["exact"]
    return totals

if __name__ == "__main__":
    print(json.dumps(analyze(), indent=2, sort_keys=True))
