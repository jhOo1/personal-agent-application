"""Price observed V44 inference paths with full draft and selection costs."""
import json
from statistics import median

import analyze_fixed_answer_choice_v44 as audit
from deployment_cost import numeric_cost, old_cost, profile
from trace_cost import samples

run = audit.run
RP, GATE, GENERIC, EVIDENCE, REVIEW = audit.RP, audit.GATE, audit.GENERIC, audit.EVIDENCE, audit.REVIEW
METHODS = (RP, GATE, REVIEW, GENERIC, EVIDENCE)


def evaluate(rows, current_ledger):
    parent, previously_reviewed, old_ledger = samples()
    old_plan = run.read(run.stage.prior.formal.OUT / "PLAN.json")
    roots = {r["uid"]: r for r in parent["roots"]}
    refs = {r["uid"]: r for r in previously_reviewed}
    old = {(rec["stage"], rec["request_sha256"]): rec for rec in old_ledger}
    current = {rec["request_sha256"]: rec for rec in current_ledger}
    offline = run.read(run.stage.OUT / "FIXED_ANSWER_CHOICE_PREFLIGHT.json")
    assigned = {r["uid"]: r["request_sha256"] for r in offline["rows"] if r["status"] == "BOTH_DRAFTS"}
    measured = []
    raw_pairs = []
    for row in rows:
        uid, group = row["uid"], row["group"]
        if uid not in assigned or any(row["choices"][m]["status"] != "SELECTED" for m in run.ARMS):
            continue
        root, ref = roots[uid], refs[uid]
        selected = {m: current[assigned[uid][m]] for m in run.ARMS}
        task_only = old.get((run.stage.prior.DRAFT, root["task_wire_sha256"]), {})
        review = old.get((run.stage.prior.FINAL, ref["trace"]["review_sha256"][REVIEW]), {})
        archived_rp = old_cost(old_plan, root, RP)
        archived_gate = old_cost(old_plan, root, GATE)
        costs = {m: c for m, c in ((RP, archived_rp), (GATE, archived_gate)) if c is not None}
        draft_cost = numeric_cost(task_only.get("usage"))
        if archived_rp is not None and draft_cost is not None:
            both = archived_rp + draft_cost
            for m, record in [(REVIEW, review), *selected.items()]:
                stage_cost = numeric_cost(record.get("usage")) if record.get("status") == "OK" else None
                if stage_cost is not None:
                    costs[m] = both + stage_cost
        current_costs = tuple(numeric_cost(selected[m].get("usage")) for m in run.ARMS)
        if all(value is not None for value in current_costs):
            raw_pairs.append(tuple(value["total_tokens"] for value in current_costs))
        matches = {m: row["native"][m]["fields"]["match"]["matched"] for m in METHODS if
                   row["native"][m]["fields"].get("match") is not None}
        measured.append({"uid": uid, "group": group, "usage": costs, "positions": row["positions"], "matched": matches})
    eligible = [r for r in measured if all(m in r["usage"] and m in r["matched"] for m in METHODS)]
    raw = {"paired_count": len(raw_pairs)}
    if raw_pairs:
        raw["median_tokens"] = dict(zip(run.ARMS, map(median, zip(*raw_pairs, strict=True)), strict=True))
        raw["total_tokens"] = dict(zip(run.ARMS, map(sum, zip(*raw_pairs, strict=True)), strict=True))
    return {
        "new_requests": 0, "online_generation_calls_before_cache": {
            RP: 3, GATE: 2, REVIEW: 5, GENERIC: 5, EVIDENCE: 5,
        },
        "choice_only_cost": raw,
        "common_matched_and_cost": {
            **profile(eligible, METHODS), "positions": sum(r["positions"] for r in eligible),
            "matched": {m: sum(r["matched"][m] for r in eligible) for m in METHODS},
        },
        "method_note": "Deployment paths include RP preparation, two draft actors and one comparison, excluding all native scoring. Observed usage only.",
    }


if __name__ == "__main__":
    _, rows, records = audit.reconstruct()
    print(json.dumps(evaluate(rows, records), ensure_ascii=False, indent=2))
