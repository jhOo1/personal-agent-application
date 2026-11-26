"""Inspect same-reference style transitions by previously frozen profile group."""
from collections import Counter, defaultdict
import json
from pathlib import Path
from runpy import run_path

runner = run_path(str(Path(__file__).with_name("run.py")))
METHOD, RUN, fields, probe = (runner[name] for name in ("METHOD", "RUN", "fields", "probe"))


def compare():
    result = probe.read(RUN / "RESULTS.json")
    pairs = defaultdict(dict)
    for row in result["rows"]:
        if row["method"] in pairs[row["uid"]]:
            raise ValueError("Duplicate answer")
        pairs[row["uid"]][row["method"]] = row
    groups = sorted({row[METHOD]["group"] for row in pairs.values()})
    report = defaultdict(Counter)
    cases = []
    for uid, arms in pairs.items():
        row = arms[METHOD]
        group = f"profile_{groups.index(row['group']) + 1}"
        scores = {"gate": row["base_score"], **{m: r["score"] for m, r in arms.items()}}
        if not all(scores.values()):
            cases.append({"uid": uid, "group": group, "status": "NOT_COMMON_VALID"})
            continue
        a = fields(row["score"])
        evidence = [(x["preference"], x["appropriate"]) for x in row["score"]["decisions"]]
        effects = {}
        for method, score in scores.items():
            if method == METHOD:
                continue
            if evidence != [(x["preference"], x["appropriate"]) for x in score["decisions"]]:
                raise ValueError("Ordered attribute references changed")
            b = fields(score)
            effects[method] = {key: a[key] - b[key] for key in
                               ("aar_numerator", "mr_numerator", "nonbold_n", "task_completeness")}
            report[f"{group}/{method}"].update({"cases": 1, **effects[method]})
        cases.append({"uid": uid, "profile": group, "status": "SCORED", "paired_changes": effects})
    return {"profiles": report, "cases": cases}


if __name__ == "__main__":
    print(json.dumps(compare(), indent=2, sort_keys=True))
