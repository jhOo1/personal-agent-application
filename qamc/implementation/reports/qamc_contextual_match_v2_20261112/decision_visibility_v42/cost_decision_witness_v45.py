"""Reconcile observed deployment costs on same valid cases across V44 and V45."""
import json
from collections import Counter

import analyze_decision_witness_v45 as analysis
from deployment_cost import numeric_cost, old_cost, profile
from trace_cost import samples

run = analysis.run
METHODS = (analysis.RP, analysis.GENERIC, analysis.C_PRIOR, analysis.ANCHORED)


def evaluate(rows, receipts):
    plan, _, history = samples()
    roots = {r["uid"]: r for r in plan["roots"]}
    formal = run.read(run.stage.prior.formal.OUT / "PLAN.json")
    drafts = {r["request_sha256"]: r for r in history if r["stage"] == run.stage.prior.DRAFT}
    selectors = {r["request_sha256"]: r for r in receipts if r["status"] == "OK"}
    old = run.read(run.parent.OUT / "COMPLETED.json")
    generic = {r["request_sha256"]: r for r in old["ledger"] if r["status"] == "OK"}
    preflight = run.read(run.stage.OUT / "FIXED_ANSWER_CHOICE_PREFLIGHT.json")
    prior_wires = {r["uid"]: r["request_sha256"] for r in preflight["rows"] if r["status"] == "BOTH_DRAFTS"}
    _, manifest, aliases = run.artifacts()
    current_wires = {j["unit"]["root_id"]: run.sha(j["request"]) for j in manifest["units"]}
    current_wires.update({r["uid"]: r["request_sha256"] for r in aliases})
    cost_rows, missing = [], Counter()
    for row in rows:
        uid = row["uid"]
        if not all(row["native"][m]["fields"].get("match") for m in METHODS):
            continue
        root = roots[uid]
        saved = run.stage.prior.receipt(formal, uid, analysis.RP, run.stage.ACTOR)
        costs = {
            "RP": old_cost(formal, root, analysis.RP),
            "rp_actor": numeric_cost(saved["response"].get("usage")) if saved else None,
            "no_history_actor": numeric_cost(drafts[root["task_wire_sha256"]].get("usage")),
            "old_generic": numeric_cost(generic[prior_wires[uid][analysis.GENERIC]].get("usage")),
            "new_witness": numeric_cost(selectors[current_wires[uid]].get("usage")),
        }
        if any(value is None for value in costs.values()):
            missing.update(key for key, value in costs.items() if value is None)
            continue
        rp, neutral = costs["RP"], costs["no_history_actor"]
        no_c_rule = rp if run.contract.prior_choice(root) == "SOURCE_RP" else rp - costs["rp_actor"] + neutral
        cost_rows.append({"uid": uid, "group": row["group"], "positions": row["positions"],
                          "usage": {analysis.RP: rp, analysis.C_PRIOR: no_c_rule,
                                    analysis.GENERIC: rp + neutral + costs["old_generic"],
                                    analysis.ANCHORED: rp + neutral + costs["new_witness"]},
                          "scores": {m: row["native"][m]["fields"]["match"]["matched"] for m in METHODS}})
    return {
        "new_model_calls": 0, "generation_calls_per_case_without_cache": dict(zip(METHODS, (3, 5, 3, 5), strict=True)),
        "paired_cost_and_native_match": {
            **profile(cost_rows, METHODS), "positions": sum(r["positions"] for r in cost_rows),
            "matched": {m: sum(r["scores"][m] for r in cost_rows) for m in METHODS},
        },
        "missing_receipts_or_usage_on_score_valid_cases": missing,
        "cost_model": ("The C-rule needs both archived RP pre-Actor steps and only the selected Actor; "
                       "Generic and V45 each include both actors and one comparison or witness inference. "
                       "Usage is from observed calls and excludes grading. Shape-only and anchored share the V45 cost."),
    }


if __name__ == "__main__":
    _, rows, ledger = analysis.collected()
    print(json.dumps(evaluate(rows, ledger), ensure_ascii=False, indent=2))
