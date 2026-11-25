"""Decompose end-to-end Match into draft selection and the executed edit on identical cases."""
import json

from qamc.common import sha

import run_decision_edit as r


def decompose():
    if r.read(r.OUT / "RUN_STATE.json")["state"] != "COMPLETE":
        raise ValueError("Decision-edit results must be settled")
    settled_path = r.OUT / "SETTLED.json"
    rows = r.read(settled_path)["rows"]
    archived = r.read(r.prior.OUT / "FROZEN.json")["roots"]
    predicts_c = {item["uid"]: any(rec["policy"] == "C" for rec in item["archived_policy"]) for item in archived}
    methods = (r.comparisons.ZERO, r.DECISION, r.comparisons.RULE)
    common = [item for item in rows if all(item["native"][m]["fields"].get("match") for m in methods)]
    subsets = {
        "all": common,
        "all_A": [item for item in common if set(item["labels"]) == {"A"}],
        "contains_B_without_C": [item for item in common if "B" in item["labels"] and "C" not in item["labels"]],
        "contains_C": [item for item in common if "C" in item["labels"]],
        "archived_RP_predicts_C": [item for item in common if predicts_c[item["uid"]]],
        "archived_RP_does_not_predict_C": [item for item in common if not predicts_c[item["uid"]]],
    }
    summary = {}
    for label, sample in subsets.items():
        totals = {m: sum(row["native"][m]["fields"]["match"]["matched"] for row in sample) for m in methods}
        summary[label] = {
            "roots": len(sample), "source_groups": len({item["group"] for item in sample}),
            "positions": sum(item["positions"] for item in sample), "correct": totals,
            "local_edit_minus_task_only": totals[r.DECISION] - totals[r.comparisons.ZERO],
            "task_only_minus_C_prior": totals[r.comparisons.ZERO] - totals[r.comparisons.RULE],
            "local_edit_minus_C_prior": totals[r.DECISION] - totals[r.comparisons.RULE],
        }
    return {"source_sha256": sha(settled_path.read_bytes()), "comparisons": summary,
            "new_model_calls": 0, "new_grading_calls": 0, "independent_behavior_validation": False}


if __name__ == "__main__":
    print(json.dumps(decompose(), ensure_ascii=False, indent=2))
