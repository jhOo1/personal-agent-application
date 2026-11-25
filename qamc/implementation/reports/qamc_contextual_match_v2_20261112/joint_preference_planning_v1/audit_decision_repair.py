"""Inspect physical receipts and independently reconstruct a settled V2 comparison."""
from argparse import ArgumentParser
from collections import Counter
import json
from unittest.mock import patch

from deployment_cost import numeric_cost, old_cost, profile
from qamc.common import sha

import decision_repair as method
import run_decision_repair as run


def stage_status(stages):
    counts = {}
    for name, maximum in stages.items():
        records = run.probe.stage_receipts(name)
        if sum(rec is not None for rec, _ in records.values()) > maximum:
            raise ValueError(f"Physical request count exceeds {name} cap")
        counts[name] = {
            "assigned_physical": len(records),
            "states": Counter(rec["status"] if rec else "UNISSUED" for rec, _ in records.values()),
        }
    return counts


def audit_live():
    spec = run.read(run.OUT / "FROZEN.json")
    run.probe.OUT, run.probe.RUN = run.OUT, run.RUN
    return stage_status(spec["caps"])


def normalize_status_records(blocks, edits, value):
    normalized, changes = [], Counter()
    for row in value["reviews"]:
        slot = row.get("block") if isinstance(row, dict) else None
        if not isinstance(slot, str) or slot not in edits:
            normalized.append(row)
            continue
        fixed = dict(row)
        for key, lines in (("before", blocks[slot]["lines"]), ("after", edits[slot]["lines"])):
            statuses = row.get(key)
            if not isinstance(statuses, list) or not statuses or not all(isinstance(s, dict) for s in statuses):
                continue
            fields = set(statuses[0]) - {"status"}
            if (fields not in ({"option"}, {"text"}) or len(lines) != len(statuses)
                    or any(set(x) != fields | {"status"} for x in statuses)):
                changes["not_losslessly_alignable"] += 1
                continue
            name, = fields
            if (any(status[name] != line for status, line in zip(statuses, lines, strict=True))
                    or any(not isinstance(x["status"], str) or x["status"] not in method.FEASIBILITY for x in statuses)):
                changes["not_losslessly_alignable"] += 1
                continue
            fixed[key] = [item["status"] for item in statuses]
            changes["exactly_aligned_arrays"] += 1
        normalized.append(fixed)
    return dict(value, reviews=normalized), changes


def audit_review_shape():
    spec, _, roots, archive = run.prepare()
    cached_drafts = run.inherited(archive)[run.DRAFT]
    cached_drafts.update(run.read(run.OUT / f"{run.DRAFT}_EXACT.json"))
    run.probe.OUT, run.probe.RUN = run.OUT, run.RUN
    proposals = run.probe.stage_receipts(run.PROPOSE)
    details = []
    available = 0
    for (uid, arm), (record, raw) in run.probe.stage_receipts(run.REVIEW).items():
        if not raw:
            continue
        available += 1
        root = roots[uid]
        blocks = run.draft.read_draft(root, cached_drafts[spec["draft_request_sha256"][uid]][1])
        edits, _ = method.collect_edits(root, blocks, proposals[uid, arm][1])
        try:
            fixed, counts = normalize_status_records(blocks, edits, run.draft.read_object(raw))
            if not counts:
                continue
            before = method.collect_review(root, blocks, edits, raw)[0]
            after = method.collect_review(root, blocks, edits, json.dumps(fixed, ensure_ascii=False))[0]
        except (ValueError, TypeError, KeyError):
            continue
        a = method.compile_review(root, blocks, edits, before)[0]
        b = method.compile_review(root, blocks, edits, after)[0]
        details.append({
            "uid": uid, "request_sha256": record["request_sha256"], "reply_sha256": sha(raw),
            "changes": counts, "reinstated_blocks": sorted(set(after) - set(before)),
            "answers_changed": [m for m in (method.MODEL, method.WITNESS) if a[m] != b[m]],
            "restored_pair_equal": b[method.MODEL] == b[method.WITNESS],
            "restored_exact_original_aliases": {
                m: [arm for arm in method.MODES if a[arm] == b[m]]
                for m in (method.MODEL, method.WITNESS)
            },
        })
    return {"observed_replies": available, "details": details,
            "materializes_ungraded_answers": True, "new_model_requests": 0}


def review_shape_sensitivity(rows, spec):
    """Evaluate only answers identical to an already scored output."""
    _, _, roots, _ = run.prepare()
    primary = set(spec["outside_documented_diagnostics"])
    corrected, outcomes = [], []
    for row in rows:
        trace = row["execution"]
        corrected.append(row)
        raw = trace.get("review_raw")
        if trace.get("review") not in ("OK", "NO_VALID_REVIEW_ROWS") or not raw:
            continue
        uid = row["uid"]
        try:
            normalized, changes = normalize_status_records(trace["blocks"], trace["edits"], run.draft.read_object(raw))
            if not changes["exactly_aligned_arrays"]:
                continue
            result, _ = method.collect_review(
                roots[uid], trace["blocks"], trace["edits"], json.dumps(normalized, ensure_ascii=False))
            if not any(result.values()):
                continue
            revised, _ = method.compile_review(roots[uid], trace["blocks"], trace["edits"], result)
        except (KeyError, TypeError, ValueError):
            continue
        native, aliases = dict(row["native"]), {}
        for arm in (method.MODEL, method.WITNESS):
            if revised[arm] == trace["answers"].get(arm):
                continue
            alias = next((other for other, answer in trace["answers"].items() if answer == revised[arm]), None)
            aliases[arm] = alias
            native[arm] = native[alias] if alias else {"fields": {}, "status": "NO_EXISTING_SCORE_FOR_ANSWER"}
        if aliases:
            corrected[-1] = {**row, "native": native}
            outcomes.append({"uid": uid, "alternate_answer_sha256": {m: sha(revised[m]) for m in aliases},
                             "scoring_alias": aliases})
    original_panel = [r for r in rows if r["uid"] in primary]
    corrected_panel = [r for r in corrected if r["uid"] in primary]
    return {
        "cases_with_alternate_output": outcomes,
        "original_primary_pair": run.replay.paired(original_panel, method.MODEL, method.WITNESS),
        "exact_alias_only_primary_pair": run.replay.paired(corrected_panel, method.MODEL, method.WITNESS),
        "new_model_requests": 0,
        "interpretation": "Sensitivity only. Alternate text with no existing score stays missing.",
    }


def cost_analysis(rows, records):
    spec, _, roots, _ = run.prepare()
    primary = set(spec["outside_documented_diagnostics"])
    reference = run.read(run.prior.parent.joint.prior.formal.OUT / "PLAN.json")
    draft_receipts = run.read(run.prior.BASE_OUT / "smoke" / f"{run.prior.DRAFT_CALL}_EXACT.json")
    index = {(record["unit"]["stage"], record["request_sha256"]): record for record in records}
    index.update({(run.DRAFT, digest): entry[0] for digest, entry in draft_receipts.items()})
    arms = (method.MODEL, method.WITNESS, run.GATE, run.RP)
    call_counts, cost_rows = Counter(), []
    for row in rows:
        if row["uid"] not in primary:
            continue
        execution = row["execution"]
        steps = [(run.DRAFT, execution.get("draft_sha256")),
                 (run.PROPOSE, execution.get("proposal_sha256")),
                 (run.REVIEW, execution.get("review_sha256"))]
        generation = [index.get((stage, digest)) for stage, digest in steps if digest is not None]
        if any(receipt is None for receipt in generation):
            raise ValueError("Missing physical receipt for a documented generation step")
        measured = [numeric_cost(receipt.get("usage")) for receipt in generation]
        cost = {}
        if generation and all(value is not None for value in measured):
            for arm in (method.MODEL, method.WITNESS):
                if arm in execution["answers"]:
                    cost[arm] = sum(measured, Counter())
                    call_counts[f"{arm}/{len(generation)}"] += 1
        for arm in (run.GATE, run.RP):
            amount = old_cost(reference, roots[row["uid"]], arm)
            if amount is not None:
                cost[arm] = amount
        matches = {arm: row["native"][arm]["fields"]["match"]["matched"]
                   for arm in arms if "match" in row["native"][arm]["fields"]}
        cost_rows.append({"group": row["group"], "usage": cost, "matches": matches,
                          "positions": row["positions"]})
    same_denominator = [row for row in cost_rows if all(arm in row["usage"] and arm in row["matches"] for arm in arms)]
    return {
        "baseline_generation_calls": {arm: len(run.prior.parent.joint.prior.formal.STAGES[arm])
                                      for arm in (run.GATE, run.RP)},
        "observed_matched_review_calls": call_counts,
        "common_cost_and_native_match": {
            **profile(same_denominator, arms),
            "positions": sum(row["positions"] for row in same_denominator),
            "matches": {arm: sum(row["matches"][arm] for row in same_denominator) for arm in arms},
        },
        "judge_usage_excluded": True,
    }


def citation_analysis(rows, spec):
    _, _, roots, _ = run.prepare()
    primary = set(spec["outside_documented_diagnostics"])
    result = {"primary": Counter(), "regression": Counter()}
    for row in rows:
        uid, state = row["uid"], row["execution"]
        counts = result["primary" if uid in primary else "regression"]
        counts["assigned"] += 1
        if "edits" not in state:
            continue
        labels = dict(zip((x["memory_id"] for x in roots[uid]["original_sources"]),
                          row["labels"], strict=True))
        counts["valid_proposal"] += 1
        for slot, edit in state["edits"].items():
            cited = {labels[item["id"]] for item in edit["sources"]}
            cohort = ("only_A" if cited == {"A"} else "mixed_A_BC" if "A" in cited else "only_BC")
            counts[f"edits/{cohort}"] += 1
            review = state.get("checks", {}).get(slot)
            counts[f"model_accept/{cohort}"] += bool(review and review["model_accept"])
            trace = state.get("trace", {}).get(slot, "UNAVAILABLE")
            counts[f"witness/{cohort}/{trace}"] += 1
    return {
        "counts": result,
        "interpretation": "Author labels are joined at evaluation only. Citation and execution do not prove compliance.",
    }


def verify():
    state, spec, settled = (run.read(run.OUT / name)
                            for name in ("RUN_STATE.json", "FROZEN.json", "SETTLED.json"))
    if state["state"] != "COMPLETE":
        raise ValueError("The comparison has not reached terminal settlement")
    verified = []

    def compare(path, rebuilt):
        if run.read(path) != json.loads(json.dumps(rebuilt)):
            raise ValueError(f"Replay differs from {path.name}")
        verified.append(path.name)

    with patch.object(run.probe, "freeze", compare):
        run.run("report", run.prepare())

    receipts = [rec for phase in spec["caps"] for rec, _ in run.probe.stage_receipts(phase).values()]
    keys = {(rec["unit"]["stage"], rec["request_sha256"]) for rec in receipts}
    if receipts != settled["ledger"] or len(keys) != len(receipts) or len(keys) != state["physical_requests"]:
        raise ValueError("Physical receipt duplication or omission")
    if any(rec["status"] == "PENDING_DELIVERY_UNKNOWN" for rec in receipts):
        raise ValueError("Terminal run includes an in-flight receipt")
    return summarize_rows(settled["rows"], receipts, spec, verified, stage_status(spec["caps"]))


def summarize_rows(rows, receipts, spec, verified, stages):
    divergences, identical, unavailable = [], 0, 0
    for row in rows:
        state = row["execution"]
        a, b = (state["answers"].get(m) for m in (method.MODEL, method.WITNESS))
        if a is None or b is None:
            unavailable += 1
            continue
        native = {m: row["native"][m]["fields"] for m in (method.MODEL, method.WITNESS)}
        if a == b:
            if native[method.MODEL] != native[method.WITNESS]:
                raise ValueError("Identical outputs have unequal native fields")
            identical += 1
            continue
        divergences.append({
            "uid": row["uid"], "group": row["group"], "author_labels": row["labels"],
            "in_primary_panel": row["uid"] in spec["outside_documented_diagnostics"],
            "native_fields": native,
            "review": state["checks"], "trace": state["trace"],
            "answer_sha256": {method.MODEL: sha(a), method.WITNESS: sha(b)},
        })
    return {
        "verified": verified, "unique_physical_receipts": len(receipts),
        "stage_counts": stages, "common_answer_pairs": identical + len(divergences),
        "identical_answer_pairs": identical, "unavailable_pairs": unavailable,
        "changed_answer_pairs": len(divergences), "divergences": divergences,
        "edit_citations_and_application": citation_analysis(rows, spec),
        "primary_generation_cost": cost_analysis(rows, receipts),
        "review_parser_sensitivity": review_shape_sensitivity(rows, spec),
        "new_model_requests": 0,
    }


def verify_recovery():
    import recover_decision_repair_drafts as recovery

    original = verify()
    state, settled, freeze = (run.read(recovery.OUT / f) for f in
                              ("RUN_STATE.json", "SETTLED.json", "FROZEN.json"))
    if state["state"] != "COMPLETE":
        raise ValueError("Schema recovery has not reached terminal settlement")
    verified = []

    def compare(path, rebuilt):
        if run.read(path) != json.loads(json.dumps(rebuilt)):
            raise ValueError(f"Recovery replay differs from {path.name}")
        verified.append(path.name)

    with patch.object(run.probe, "freeze", compare):
        recovery.settle("report", recovery.prepare())
    before = run.read(run.OUT / "SETTLED.json")
    added = [record for phase in freeze["caps"] for record, _ in run.probe.stage_receipts(phase).values()]
    if added != settled["added_ledger"] or len(added) != state["new_physical_requests"]:
        raise ValueError("Schema recovery receipts differ from trace")
    if len(added) + original["unique_physical_receipts"] > 240:
        raise ValueError("Combined run exceeded initial request cap")
    for prev, after in zip(before["rows"], settled["rows"], strict=True):
        uid = prev["uid"]
        if uid != after["uid"] or (uid not in freeze["cases"] and prev != after):
            raise ValueError("Recovery altered an unrelated unit")
    return {
        **summarize_rows(settled["rows"], before["ledger"] + added,
                         run.read(run.OUT / "FROZEN.json"), verified, stage_status(freeze["caps"])),
        "recovered_cases": sorted(freeze["cases"]), "added_physical_receipts": len(added),
    }


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("live", "verify", "combined", "review-shape"))
    args = parser.parse_args()
    action = {"live": audit_live, "verify": verify, "combined": verify_recovery,
              "review-shape": audit_review_shape}[args.mode]
    print(json.dumps(action(), ensure_ascii=False, indent=2))
