"""Recompute paired metrics from completed waves without opening the gateway."""
from collections import Counter
import json
from pathlib import Path
import sys

from run_v41 import ARMS, GATE, OUT, RP, author_cases, formal, read

sys.path.insert(0, str(OUT.parent / "decision_scoped_policy_v40"))
from analyze_policy import paired

FIELDS = ("OPB", "UPB", "RII", "FM", "VG", "Judge", "full_match")


def metric_pairs(rows, left, right):
    result = {}
    for field in FIELDS:
        common = [(r["native"][left]["fields"][field], r["native"][right]["fields"][field])
                  for r in rows if all(field in r["native"][m]["fields"] for m in (left, right))]
        if common:
            a, b = map(sum, zip(*common, strict=True))
            result[field] = {"n": len(common), "left": a / len(common), "right": b / len(common),
                             "delta": (b - a) / len(common)}
        else:
            result[field] = {"n": 0}
    return result


def run_report():
    plan = read(OUT / "FROZEN.json")
    sealed_out = author_cases(read(formal.OUT / "PLAN.json"))
    rows, ledger = [], []
    for index, expected in enumerate(plan["waves"]):
        path = OUT / f"wave_{index:02d}" / "COMPLETED.json"
        if not path.exists():
            break
        result = read(path)
        if [row["uid"] for row in result["rows"]] != expected:
            raise ValueError("Completed wave membership changed")
        rows.extend(result["rows"])
        ledger.extend(result["ledger"])
    for row in rows:
        ref = read(formal.ROOT / sealed_out[row["uid"]]["evaluation_path"])
        row["labels"] = ref["intent_type"]
        row["positions"] = len(row["labels"])
    sets = {
        "all_completed": rows,
        "narrow": [row for row in rows if row["in_sensitivity"]],
        "additional_groups": [row for row in rows if not row["in_sensitivity"]],
        "all_A": [row for row in rows if set(row["labels"]) == {"A"}],
        "contains_BC": [row for row in rows if set(row["labels"]) - {"A"}],
    }
    methods = ((ARMS[1], ARMS[0]), (RP, ARMS[0]), (GATE, ARMS[0]), (RP, ARMS[1]))
    analyses = {scope: {f"{left}__{right}": {**paired(sample, left, right),
                                                "separate_metric_pairs": metric_pairs(sample, left, right)}
                        for left, right in methods}
                for scope, sample in sets.items()}
    counts = Counter((row["stage"], row["unit"]["method"], row["status"]) for row in ledger)
    return {
        "complete": len(rows) == len(plan["roots"]),
        "completed": len(rows), "planned": len(plan["roots"]),
        "pairs": analyses,
        "physical_receipts_in_completed_waves": len(ledger),
        "unknown_usage_in_completed_waves": sum(row["usage"] is None for row in ledger),
        "reported_tokens_in_completed_waves": sum((row["usage"] or {}).get("total_tokens", 0) for row in ledger),
        "counts": [{"stage": stage, "method": method, "status": status, "count": count}
                   for (stage, method, status), count in sorted(counts.items())],
        "legal_B_C_and_task_quality_usable_as_promotion_evidence": False,
    }


if __name__ == "__main__":
    print(json.dumps(run_report(), ensure_ascii=False, indent=2))
