"""Pair the archived IPE-C route with same-cohort paper reconstructions."""
from collections import Counter
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
METHODS = ("RPR_PAPER_FULL", "MEMADAPTER_FULL", "DES2GEN_FULL", "GEPA_SELECTED_BOUNDS")


def read(path):
    return json.loads((HERE / path).read_text())


def compare():
    routes = {row["uid"]: row for row in read("ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]}
    results = read("rpeval_formal_multi_coverage_v1/RESULT_ROWS.json")
    report = {method: {} for method in METHODS}
    for row in results:
        method, uid = row["method"], row["uid"]
        if method not in report or uid not in routes:
            continue
        route = routes[uid]
        raw_labels = route["labels"]
        if not raw_labels:
            continue
        scope = "all_A" if set(raw_labels) == {"A"} else "contains_C" if "C" in raw_labels else "only_B"
        left = (route["ipe_c"] or {}).get("grade") or {}
        right = row["native_fields"] or {}
        if not left.get("match") or not right.get("match"):
            continue
        n = len(raw_labels)
        if left["match"]["positions"] != n or right["match"]["positions"] != n:
            raise ValueError(f"Mismatched position denominator: {uid}/{method}")
        a, b = left["match"]["matched"], right["match"]["matched"]
        for level in (scope, "all"):
            totals = report[method].setdefault(level, Counter())
            totals.update({"n": 1, "positions": n, "ipe_c": a, "reference": b,
                           "win": a > b, "loss": a < b, "tie": a == b,
                           "ipe_c_opb": left["OPB"], "reference_opb": right["OPB"],
                           "ipe_c_upb": left["UPB"], "reference_upb": right["UPB"]})
    return report


if __name__ == "__main__":
    print(json.dumps(compare(), indent=2))
