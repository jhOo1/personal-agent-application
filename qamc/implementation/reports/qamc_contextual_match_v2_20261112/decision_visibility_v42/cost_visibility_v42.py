"""Reconstruct independent per-answer costs beside the physical experiment ledger."""
from collections import Counter, defaultdict
import json
from statistics import median

from deployment_cost import FIELDS, numeric_cost, old_cost, profile
import run_visibility_v42 as runner


def compare_costs(data, left, right):
    common = [row for row in data if left in row["usage"] and right in row["usage"]]
    result = profile(common, (left, right))
    if common:
        for field in FIELDS:
            result["cost"][right][f"paired_median_{field}_difference"] = median(
                row["usage"][right][field] - row["usage"][left][field] for row in common)
    return result


def summarize():
    plan = runner.read(runner.OUT / "FROZEN.json")
    if plan != runner.prepare():
        raise ValueError("V42 costs are linked to a different freeze")
    prior = runner.read(runner.prior.OUT / "FROZEN.json")
    roots = {r["uid"]: r for r in prior["roots"]}
    old_plan = runner.read(runner.prior.formal.OUT / "PLAN.json")
    cached = runner.old_receipts(prior)
    ledger, rows = [], []
    for index, uids in enumerate(plan["waves"]):
        file = runner.OUT / f"wave_{index:02d}" / "COMPLETED.json"
        if not file.exists():
            break
        saved = runner.read(file)
        if [r["uid"] for r in saved["rows"]] != uids:
            raise ValueError("Wave membership changed")
        rows.extend(saved["rows"])
        ledger.extend(saved["ledger"])
    recipes = {name: len(runner.prior.formal.STAGES[name]) for name in (runner.prior.GATE, runner.prior.RP)}
    recipes.update({arm: 2 for arm in runner.ARMS})
    receipt_index = {(record["unit"]["stage"], record["request_sha256"]): record for record in ledger}
    if len(receipt_index) != len(ledger):
        raise ValueError("Physical request was put on the ledger more than once")
    for stage in (runner.SELECTOR, runner.ACTOR):
        for digest, (record, _) in cached[stage].items():
            if (stage, digest) in receipt_index:
                raise ValueError("Historical generation was dispatched again")
            receipt_index[stage, digest] = record
    billed = defaultdict(Counter)
    for record in ledger:
        key = record["unit"]["stage"] + "/" + record["unit"]["method"]
        usage = numeric_cost(record.get("usage"))
        billed[key].update(requests=1, ok=record["status"] == "OK", unknown_usage=usage is None,
                           completion_over_requested=record.get("reported_completion_over_requested") is True)
        if usage is not None:
            billed[key].update(usage)

    def observed(stage, request_sha256):
        record = receipt_index.get((stage, request_sha256))
        if record and record["status"] == "OK":
            return numeric_cost(record.get("usage"))
        return None

    data, missing = [], Counter()
    for row in rows:
        cost, components = {}, {}
        for method in (runner.prior.GATE, runner.prior.RP):
            value = old_cost(old_plan, roots[row["uid"]], method)
            if value is not None:
                cost[method] = value
            else:
                missing[method] += 1
        for arm, (method, _) in runner.ARMS.items():
            answer = row["answers"][arm]
            selector = observed(runner.SELECTOR, row["selected"][method]["request_sha256"])
            actor = observed(runner.ACTOR, answer.get("request_sha256"))
            if selector is not None and actor is not None and answer["status"] == "OK":
                cost[arm] = selector + actor
                components[arm] = {runner.SELECTOR: selector, runner.ACTOR: actor}
            else:
                missing[arm] += 1
        data.append({"group": row["group"], "uid": row["uid"], "usage": cost, "components": components,
                     "match": {method: result["fields"]["match"]["matched"] for method, result in row["native"].items()
                               if "match" in result["fields"]}, "positions": row["positions"]})
    controls = tuple(recipes)
    fair = [row for row in data if set(controls) <= row["usage"].keys() and set(controls) <= row["match"].keys()]
    return {
        "settled": len(rows), "online_calls_before_cache": recipes, "new_physical_receipts": len(ledger),
        "new_physical_cost_by_issuer": billed, "missing_logical_cost_by_method": missing,
        "matched_costs_and_scores": {
            **profile(fair, controls), "positions": sum(row["positions"] for row in fair),
            "match": {method: sum(row["match"][method] for row in fair) for method in controls},
        },
        "same_call_budget": {f"{left}__{right}": compare_costs(data, left, right)
                             for left, right in runner.COMPARISONS[:2]},
        "rows": data, "new_model_calls": 0,
        "semantics": ("Physical bills assign each newly sent request once. Independent per-answer cost charges "
                      "a shared Selector and any exact Actor reuse once per logical answer. Judge calls are "
                      "excluded from independent generation cost. Missing amounts are not imputed."),
    }


if __name__ == "__main__":
    print(json.dumps(summarize(), ensure_ascii=False, indent=2))
