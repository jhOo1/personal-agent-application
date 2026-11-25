"""Account for score and exact text changes separately by task and profile."""
from collections import Counter
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
FIELDS = ("aar_numerator", "mr_numerator", "task_completeness")


def summary(result, frozen):
    records, coverage = [], Counter()
    for row in result["rows"]:
        uid, method = row["uid"], row["method"]
        before, after = result["base_scores"][uid], row["score"]
        tag = method + "/"
        coverage[tag + "assigned"] += 1
        coverage[tag + row["actor_status"]] += 1
        coverage[tag + "exact_reuse"] += row["same"]
        coverage[tag + "changed"] += row["answer"] is not None and not row["same"]
        coverage[tag + "valid_grade"] += after is not None
        coverage.update(tag + "issue/" + issue for issue in row["issues"])
        record = {"uid": uid, "method": method, "profile": frozen["uids"][uid]["profile"],
                  "before": {k: before[k] for k in FIELDS}, "after": None, "flips": [],
                  "words": len((row["answer"] or "").split()), "edited": not row["same"]}
        records.append(record)
        if not after:
            continue
        record["after"] = {k: after[k] for k in FIELDS}
        for old, new in zip(before["decisions"], after["decisions"], strict=True):
            if any(old[k] != new[k] for k in ("preference", "appropriate")):
                raise ValueError("Different evaluation properties within a pair")
            if old["label"] != new["label"]:
                record["flips"].append({"preference": old["preference"], "appropriate": old["appropriate"],
                                        "before": old["label"], "after": new["label"]})
    return {"records": records, "coverage": coverage,
            **{k: result[k] for k in ("comparisons", "counts", "statuses", "tokens", "unknown_usage")}}


if __name__ == "__main__":
    args = [json.loads((HERE / f).read_text()) for f in ("RESULTS.json", "FROZEN.json")]
    print(json.dumps(summary(*args), ensure_ascii=False, indent=2))
