"""Observe real editor receipts and compare deployment cost after native settlement."""
from collections import Counter
import json
from statistics import median

from qamc.common import sha

import run_decision_edit as run
from deployment_cost import FIELDS, numeric_cost, old_cost


def reply_status(entry):
    return entry.get("transaction") or entry["status"]


def observe(plan, payloads, jobs, seen):
    by_wire = {record["request_sha256"]: (record, raw) for record, raw in seen if record}
    cells = {m: Counter() for m in run.edit.METHODS}
    rejects = {m: Counter() for m in run.edit.METHODS}
    alternatives = {}
    for uid, method, wire in jobs:
        digest = sha(wire)
        if digest not in by_wire:
            cells[method]["UNDISPATCHED"] += 1
            continue
        record, raw = by_wire[digest]
        if record["status"] == "OK" and raw is None:
            cells[method]["AWAITING_VISIBLE_RESPONSE"] += 1
            continue
        compiled = run.parse_edit(record, raw, payloads[uid], digest)
        cells[method][reply_status(compiled)] += 1
        rejects[method].update(r["reason"] for r in compiled.get("rejected", []))
        if "answer" in compiled:
            alternatives.setdefault(uid, {})[method] = compiled["answer"]
    paired = [methods for methods in alternatives.values() if len(methods) == len(run.edit.METHODS)]
    return {
        "physical_editor_requests": len(by_wire), "physical_editor_cap": plan["request_caps"][run.EDIT],
        "transport_editor": Counter(record["status"] for record, _ in by_wire.values()),
        "editor_reported_tokens": sum((record.get("usage") or {}).get("total_tokens") or 0
                                      for record, _ in by_wire.values()),
        "editor_unknown_usage": sum("total_tokens" not in (record.get("usage") or {})
                                    for record, _ in by_wire.values()),
        "logical_editor_outcomes": cells, "individual_rejected_edits": rejects,
        "tasks_with_two_compiled_answers": len(paired),
        "tasks_with_two_different_answers": sum(len(set(methods.values())) == 2 for methods in paired),
        "native_scores_inferred_from_editor_only": 0,
    }


def costs(plan, roots, rows, ledger):
    formal = run.read(run.prior.formal.OUT / "PLAN.json")
    archived = run.read(run.prior.OUT / "FROZEN.json")
    drafts = run.task_only.saved_drafts(archived)
    originals = {root["uid"]: root for root in roots}
    requests = {rec["request_sha256"]: rec for rec in ledger if rec["unit"]["stage"] == run.EDIT}
    controls = (run.GENERIC, run.comparisons.GATE, run.comparisons.RP, run.comparisons.RULE)
    cases = {m: [] for m in controls}
    omitted = Counter()
    for row in rows:
        native = row["native"]
        if not native[run.DECISION]["fields"].get("match"):
            continue
        root = originals[row["uid"]]
        base = drafts[root["task_wire_sha256"]]["record"]
        neutral = numeric_cost(base["usage"]) if base else None
        amounts = {}
        for m in run.edit.METHODS:
            rec = requests.get(row["edits"][m].get("request_sha256"))
            editing = numeric_cost(rec["usage"]) if rec else None
            amounts[m] = neutral + editing if neutral is not None and editing is not None else None
        for m in (run.comparisons.GATE, run.comparisons.RP):
            amounts[m] = old_cost(formal, root, m)
        rp = amounts[run.comparisons.RP]
        if any(p["policy"] == "C" for p in root["archived_policy"]):
            amounts[run.comparisons.RULE] = rp
        else:
            saved = run.prior.receipt(formal, root["uid"], run.comparisons.RP, "Actor")
            actor = numeric_cost(saved["response"].get("usage")) if saved else None
            amounts[run.comparisons.RULE] = rp - actor + neutral if None not in (rp, actor, neutral) else None
        for method in controls:
            pair = method, run.DECISION
            scores = [native[m]["fields"].get("match") for m in pair]
            if not all(scores):
                continue
            if any(amounts[m] is None for m in pair):
                omitted[method] += 1
                continue
            cases[method].append({"usage": [amounts[m] for m in pair],
                                  "matched": [score["matched"] for score in scores],
                                  "positions": row["positions"], "group": row["group"]})
    paired = {}
    for m, entries in cases.items():
        if not entries:
            continue
        paired[m] = {
            "roots": len(entries), "source_groups": len({row["group"] for row in entries}),
            "positions": sum(row["positions"] for row in entries),
            "methods": {method: {
                "reported_tokens": {field: sum(row["usage"][i][field] for row in entries) for field in FIELDS},
                "median_reported_tokens": median(row["usage"][i]["total_tokens"] for row in entries),
                "matched": sum(row["matched"][i] for row in entries),
            } for i, method in enumerate((m, run.DECISION))},
        }
    return {"matched_inference_cost_without_judge": paired, "missing_usage_among_paired_scores": omitted,
            "logical_inference_calls": {run.GENERIC: 2, run.DECISION: 2, run.comparisons.GATE: 2,
                                        run.comparisons.RP: 3, run.comparisons.RULE: 3},
            "assumptions": "Deployment uses saved task-only generation footprint plus one editor call. "
                           "The C-rule pays two RP pre-Actor steps and only the actor it selects.",
            "synthetic_scoring": False, "independent_confirmation": plan["independent_confirmation"]}


def main():
    frozen = run.read(run.OUT / "FROZEN.json")
    plan, roots, payloads, jobs = run.prepare(frozen["service_reference_sha256"])
    if plan != frozen:
        raise ValueError("Frozen cohort or code changed")
    run.probe.OUT, run.probe.RUN = run.OUT, run.RUN
    status = run.read(run.OUT / "RUN_STATE.json")
    printout = {"state": status["state"], "new_model_calls": 0}
    printout.update(observe(plan, payloads, jobs, run.probe.stage_receipts(run.EDIT).values()))
    judges = [record for record, _ in run.probe.stage_receipts(run.JUDGE).values() if record]
    printout["physical_native_requests"] = len(judges)
    printout["native_transport"] = Counter(record["status"] for record in judges)
    if status["state"] == "COMPLETE":
        settled = run.read(run.OUT / "SETTLED.json")
        printout.update(costs(plan, roots, settled["rows"], settled["ledger"]))
    print(json.dumps(printout, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
