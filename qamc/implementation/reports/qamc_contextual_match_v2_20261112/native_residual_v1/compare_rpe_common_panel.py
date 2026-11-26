"""Compare archived methods on one exact strict-Match RPEval intersection."""
import argparse
from collections import Counter, defaultdict
import json

from compare_ipe_c_external import METHODS, read

BASE = "IPE_C"
FIELDS = ("OPB", "UPB", "FM")
TASK_ONLY_ROUTES = {"REUSE_ORIGINAL_TASK_ONLY_STATE", "REUSE_DRAFT", "NEW_DRAFT"}


def summarize(*, include_task_only=False):
    methods = (BASE, *METHODS, "TASK_ONLY") if include_task_only else (BASE, *METHODS)
    routes = read("ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]
    grades = defaultdict(dict)
    for row in read("rpeval_formal_multi_coverage_v1/RESULT_ROWS.json"):
        method = row["method"]
        if method not in METHODS:
            continue
        by_method = grades[row["uid"]]
        if method in by_method:
            raise ValueError("Duplicate archived method and UID")
        by_method[method] = row["native_fields"] or {}

    results, reasons = defaultdict(Counter), Counter()
    totals = defaultdict(lambda: defaultdict(Counter))
    pairs = defaultdict(lambda: defaultdict(Counter))
    group_deltas = defaultdict(Counter)
    if len({row["uid"] for row in routes}) != len(routes):
        raise ValueError("Duplicate frozen routes")
    for row in routes:
        uid = row["uid"]
        labels = row["labels"]
        if not labels:
            reasons["missing_labels"] += 1
            continue
        scores = {BASE: row["ipe_c"]["grade"] or {}, **grades.get(uid, {})}
        if include_task_only:
            task = row["controls"]["TASK_ONLY"]
            if row["old_route"] in TASK_ONLY_ROUTES and task["grade"] and scores[BASE]:
                if not task["answer_sha256"] or task["answer_sha256"] != row["ipe_c"]["answer_sha256"]:
                    raise ValueError(f"Task-only answer drift: {uid}")
                if task["grade"] != scores[BASE]:
                    raise ValueError(f"Task-only score drift: {uid}")
            scores["TASK_ONLY"] = task["grade"] or {}
        missing = [m for m in methods if not scores.get(m, {}).get("match")]
        if missing:
            reasons["missing_common_any_method"] += 1
            reasons.update(missing)
            continue
        if any(s["match"]["positions"] != len(labels) for s in scores.values()):
            raise ValueError(f"Strict denominator drift: {uid}")
        stratum = "contains_C" if "C" in labels else "only_B" if "B" in labels else "all_A"
        fields = [f for f in FIELDS if all(type(s.get(f)) is int for s in scores.values())]
        baseline = scores[BASE]["match"]["matched"]
        for split in ("all", stratum):
            results[split].update({"tasks": 1, "positions": len(labels)})
            results[split].update({f"{f}_common": 1 for f in fields})
            for method, s in scores.items():
                value = s["match"]["matched"]
                totals[split][method].update({"Match": value, **{f: s[f] for f in fields}})
                if method != BASE:
                    difference = baseline - value
                    pairs[split][method].update({
                        "tie" if not difference else "win" if difference > 0 else "loss": 1
                    })
                    if split == "all":
                        group_deltas[method][row["source_group"]] += difference
    signs = {m: Counter("tie" if not d else "win" if d > 0 else "loss" for d in g.values())
             for m, g in group_deltas.items()}
    return {"allocated": len(routes), "missing": reasons, "common": results,
            "scores": totals, "ipe_c_pairs": pairs, "ipe_c_group_deltas": signs}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-task-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(summarize(include_task_only=args.include_task_only), indent=2))
