"""Reconstruct uncached generation cost for archived baselines and V41 continuations."""
from collections import Counter, defaultdict
import json
from statistics import median

from run_v41 import ARMS, DRAFT, FINAL, GATE, RP, formal, read, receipt
from trace_cost import samples

DELTA, REVIEW = ARMS
METHODS = (GATE, RP, REVIEW, DELTA)
FIELDS = ("prompt_tokens", "completion_tokens", "total_tokens")


def numeric_cost(usage):
    if (not isinstance(usage, dict) or any(type(usage.get(key)) is not int or usage[key] < 0
                                           for key in FIELDS)):
        return None
    return Counter({key: usage[key] for key in FIELDS})


def old_cost(plan, root, method):
    usage = Counter()
    for stage in formal.STAGES[method]:
        record = receipt(plan, root["uid"], method, stage)
        if record is None:
            return None
        if stage == "Actor" and (record["request_sha256"], record["response"]["answer"]) != (
            root["archived"][method]["actor_sha256"], root["archived"][method]["answer"]
        ):
            raise ValueError("Generation footprint comes from a different archived answer")
        amount = numeric_cost(record["response"].get("usage"))
        if amount is None:
            return None
        usage.update(amount)
    return usage


def profile(bodies, methods):
    paired = [value for value in bodies if all(method in value["usage"] for method in methods)]
    table = {}
    for method in methods:
        cells = [value["usage"][method] for value in paired]
        if cells:
            table[method] = {
                "totals": {key: sum(cell[key] for cell in cells) for key in FIELDS},
                "median_total": median(cell["total_tokens"] for cell in cells),
            }
    return {"common_roots": len(paired), "source_groups": len({value["group"] for value in paired}),
            "cost": table}


def run():
    plan, rows, ledger = samples()
    old_plan = read(formal.OUT / "PLAN.json")
    physical = {(record["stage"], record["request_sha256"]): record for record in ledger}
    roots = {root["uid"]: root for root in plan["roots"]}
    counts = Counter()
    data = []

    def measured(stage, digest):
        record = physical.get((stage, digest))
        return numeric_cost(record["usage"]) if record and record["status"] == "OK" else None

    for row in rows:
        if any(row["answers"][arm]["status"] != "OK" for arm in ARMS):
            continue
        root = roots[row["uid"]]
        usage = {}
        for method in (RP, GATE):
            value = old_cost(old_plan, root, method)
            if value is not None:
                usage[method] = value
            else:
                counts[method + "_missing_archive_usage"] += 1
        task_only = measured(DRAFT, root["task_wire_sha256"])
        for arm in ARMS:
            final = measured(FINAL, row["trace"]["review_sha256"][arm])
            if RP in usage and task_only is not None and final is not None:
                usage[arm] = usage[RP] + task_only + final
            else:
                counts[arm + "_missing_at_least_one_stage_usage"] += 1
        matches = {method: cell["fields"]["match"]["matched"] for method, cell in row["native"].items()
                   if "match" in cell["fields"]}
        data.append({"group": row["group"], "usage": usage,
                     "matches": matches, "positions": len(row["labels"])})
    with_outcome = [row for row in data
                    if all(method in row["usage"] and method in row["matches"] for method in METHODS)]
    return {
        "completed_roots": len(rows), "planned_roots": len(plan["roots"]), "both_final_answers": len(data),
        "nominal_online_requests_per_answer_before_cache": {
            GATE: len(formal.STAGES[GATE]), RP: len(formal.STAGES[RP]),
            **{arm: len(formal.STAGES[RP]) + 2 for arm in ARMS},
        },
        "common_four_method_generation_cost": profile(data, METHODS),
        "common_RP_and_two_reviews_generation_cost": profile(data, (RP, REVIEW, DELTA)),
        "common_generation_cost_and_native_match": {
            **profile(with_outcome, METHODS),
            "positions": sum(row["positions"] for row in with_outcome),
            "matched": {method: sum(row["matches"][method] for row in with_outcome)
                        for method in METHODS},
        },
        "missing_usage": counts, "old_prompt_paid_again_in_model_footprint_only": True,
        "new_model_requests": 0,
        "interpretation": ("Successful logical generation path before cache, using actual usage receipts when present. "
                           "An identical task-only draft is charged once per hypothetical independent answer. "
                           "Evaluator requests and previously billed amounts are excluded from this online cost. "
                           "Incomplete histories stay missing; no imputation or additional dispatch."),
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
