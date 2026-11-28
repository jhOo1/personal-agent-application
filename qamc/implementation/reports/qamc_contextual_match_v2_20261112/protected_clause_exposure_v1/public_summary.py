"""Publish metrics and coverage without source text or evaluator commentary."""
from collections import Counter, defaultdict
import json
import re
import sys

ARMS = ("REMIND", "HIDE")
BOLD = re.compile(r"\bbold\s+text\b", re.I)


def numeric_score(row):
    score = row["score"]
    if score is None:
        return None
    domain = row["benchmark"]
    if domain == "RPEval":
        return {k: score[k] for k in ("matched", "positions")} | {
            k: v for k, v in row["bias"].items() if type(v) is int}
    if domain == "BenchPreS":
        fields = ("aar_numerator", "aar_denominator", "mr_numerator", "mr_denominator", "task_completeness")
        nonbold = [d for d in score["decisions"] if d["appropriate"] and not BOLD.search(d["preference"])]
        return {k: score[k] for k in fields} | {
            "nonbold_numerator": sum(d["label"] == "follow" for d in nonbold),
            "nonbold_denominator": len(nonbold)}
    pass_key = "failure_strict_utility" if row["stratum"] == "beneficial_memory_usage" else "failure_release"
    return {"rating":score["rating"],"pass":int(not score[pass_key])}


def summarize(data):
    grouped = defaultdict(dict)
    for row in data["rows"]:
        row["score"] = numeric_score(row)
        if row["benchmark"] == "BenchPreS":
            row["case"] = row["case"][-12:]
        grouped[row["benchmark"], row["case"]][row["arm"]] = row
        if row["score"] and any(type(v) not in (int,float) for v in row["score"].values()):
            raise ValueError("Expected numeric-only per-case metrics")
    table = defaultdict(lambda: defaultdict(Counter))
    for (domain, _), group in grouped.items():
        if set(group) != set(ARMS):
            raise ValueError("Paired allocation missing")
        left, right = (group[arm] for arm in ARMS)
        key = f"{domain}/{left['stratum']}" if domain == "PersistBench" else domain
        for view in ("all", "triggered"):
            if view == "triggered" and not any(row["disposition"] == "TRIGGERED" for row in group.values()):
                continue
            cell = table[key + "/" + view]
            cell["coverage"]["allocated"] += 1
            for row in group.values():
                cell["coverage"][row["arm"] + "/scored"] += row["score"] is not None
            if left["score"] is None or right["score"] is None:
                continue
            cell["coverage"]["common"] += 1
            for arm, row in group.items():
                cell[arm].update(row["score"])
    return data | {"paired":table}


if __name__ == "__main__":
    print(json.dumps(summarize(json.load(sys.stdin)),ensure_ascii=False,indent=2))
