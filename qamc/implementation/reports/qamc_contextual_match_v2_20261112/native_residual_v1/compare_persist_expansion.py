"""Build category-level common-denominator tables from completed expansion runs."""
from collections import Counter
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = ("selected_gepa_expansion_v1", "selected_gepa_pb_rubric_resample_v1",
        "selected_rubric_exposure_v1")


def load_runs():
    scores, missing, transport = {}, Counter(), {}
    for run in RUNS:
        data = json.loads((HERE / run / "RESULTS.json").read_text())
        ledger = data["ledger"]
        transport[run] = {
            "requests": len(ledger),
            "statuses": dict(Counter(x["status"] for x in ledger)),
            "reported_tokens": sum((x.get("usage") or {}).get("total_tokens", 0) for x in ledger),
            "unknown_usage": sum(not (x.get("usage") or {}).get("total_tokens") for x in ledger),
        }
        for row in data["rows"]:
            category, uid, method = row["category"], row["uid"], row["method"]
            flag = "failure_strict_utility" if category == "beneficial_memory_usage" else "failure_release"
            record = scores.setdefault((category, uid), {})
            record["PB_RUBRIC_ARCHIVE"] = not row["base_score"][flag]
            if method in record:
                raise ValueError(f"Duplicate result: {uid} {method}")
            record[method] = None if row["score"] is None else not row["score"][flag]
            if row["score"] is None:
                missing[f"{method}/{category}"] += 1
    return scores, missing, transport


def table(scores, methods):
    result = {}
    for category in sorted({key[0] for key in scores}):
        paired = [row for (kind, _), row in scores.items()
                  if kind == category and all(row.get(method) is not None for method in methods)]
        result[category] = {
            "n": len(paired),
            "passes": {method: sum(row[method] for row in paired) for method in methods},
        }
    return result


if __name__ == "__main__":
    scores, missing, transport = load_runs()
    arms = tuple(next(iter(scores.values())))
    exposure = ("SELECTED_RUBRIC", "FULL_RUBRIC_WITH_SELECTION")
    paired = {left: {right: table(scores, (left, right)) for right in arms if right != left}
              for left in exposure}
    print(json.dumps({"five_arm_common": table(scores, arms), "pairwise": paired,
                      "missing": missing, "transport": transport}, indent=2))
