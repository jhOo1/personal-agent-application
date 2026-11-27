"""Compare whole-task outcomes on the exact published six-method development intersection."""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

here = Path(__file__).resolve().parent
sys.path.insert(0, str(here.parent/"native_residual_v1"))
from compare_rpe_common_panel import BASE, METHODS, read, summarize

def main():
    by_uid = defaultdict(dict)
    for r in read("rpeval_formal_multi_coverage_v1/RESULT_ROWS.json"):
        if r["method"] in METHODS:
            assert r["method"] not in by_uid[r["uid"]]
            by_uid[r["uid"]][r["method"]] = r["native_fields"] or {}
    reference = summarize(include_task_only=True)
    scores = defaultdict(lambda: defaultdict(Counter))
    for row in read("ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]:
        labels = row["labels"]
        arms = {**by_uid[row["uid"]], BASE:row["ipe_c"]["grade"] or {},
                "TASK_ONLY":row["controls"]["TASK_ONLY"]["grade"] or {}}
        if not labels or len(arms) != 6 or not all(g.get("match") for g in arms.values()):
            continue
        for arm, g in arms.items():
            match = g["match"]
            n = match["positions"]
            assert n == len(labels) and 0 <= match["matched"] <= n
            assert type(g["Judge"]) is int and 0 <= g["Judge"] <= 5
            for group in ("all","contains_C" if "C" in labels else "only_B" if "B" in labels else "all_A"):
                scores[group][arm].update(tasks=1, positions=n, matched=match["matched"],
                    exact=int(match["matched"]==n),severity=g["Judge"])
    for group, methods in scores.items():
        for arm, total in methods.items():
            assert total["matched"] == reference["scores"][group][arm]["Match"]
            assert total["tasks"] == reference["common"][group]["tasks"]
    print(json.dumps(scores, indent=2))
if __name__ == "__main__":
    main()
