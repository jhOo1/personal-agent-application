"""Score exact V45 selections and replay the unanchored ablation from identical model outputs."""
from argparse import ArgumentParser
from collections import Counter
import json

from qamc.common import sha

import analyze_fixed_answer_choice_v44 as archived
import run_decision_witness_v45 as run

RP, GATE, ZERO, C_PRIOR, GENERIC, REVIEW = (
    archived.RP, archived.GATE, archived.ZERO, archived.RULE, archived.GENERIC, archived.REVIEW)
ANCHORED, SHAPE = "ANCHORED", "SHAPE_ONLY"
CONTROLS = (GENERIC, RP, REVIEW, C_PRIOR, GATE, ZERO, SHAPE)


def collected():
    plan, _, aliases = run.artifacts()
    run.probe.OUT, run.probe.RUN = run.OUT, run.RUN
    physical = {uid: item for (uid, _), item in run.probe.stage_receipts(run.STAGE).items()}
    ledger = [rec for rec, _ in physical.values() if rec]
    for alias in aliases:
        source, raw = physical[alias["physical_uid"]]
        if source and source["request_sha256"] != alias["request_sha256"]:
            raise ValueError("An alias no longer refers to the exact request")
        physical[alias["uid"]] = source, raw
    _, rows, old_ledger = archived.reconstruct()
    saved = run.read(run.parent.OUT / "COMPLETED.json")
    if saved != {"rows": rows, "ledger": old_ledger}:
        raise ValueError("V44 outcome archive differs from raw receipts")
    parent = run.read(run.stage.prior.OUT / "FROZEN.json")
    drafts = archived.task.saved_drafts(parent)
    roots = {root["uid"]: root for root in parent["roots"]}
    for row in rows:
        uid = row["uid"]
        root = roots[uid]
        zero = drafts[root["task_wire_sha256"]]["answer"]
        rp = root["archived"][RP]["answer"]
        record, raw = physical.get(uid, (None, None))
        state = record["status"] if record else "UNDISPATCHED" if zero else "NO_USABLE_DRAFT"
        result = row["witness"] = {"status": state}
        outputs = {}
        if state == "OK":
            body = run.contract.packet(root, rp, zero)
            if sha(run.contract.request(body)) != record["request_sha256"]:
                raise ValueError("Witness came from a different request")
            result["raw"] = raw
            try:
                compiled = run.contract.compile_effects(body, root, raw)
            except (ValueError, TypeError):
                result["status"] = "INVALID_WITNESS_ENVELOPE"
            else:
                result.update(compiled, status="COMPILED")
                outputs = {ANCHORED: compiled["anchored"], SHAPE: compiled["shape_only"]}
        for method in (ANCHORED, SHAPE):
            if method in outputs:
                item = outputs[method]
                source = RP if item["source"] == "SOURCE_RP" else ZERO
                row["native"][method] = {**row["native"][source], "reuse": source}
                item["chosen_answer_sha256"] = sha(rp if source == RP else zero)
            else:
                row["native"][method] = {"fields": {}, "raw": None}
    return plan, rows, ledger


def summarize(plan, rows, ledger):
    eligible = [row for row in rows if row["assignment"] != "NO_USABLE_DRAFT"]
    subsets = {
        "assigned": rows, "eligible": eligible,
        "all_A": [r for r in eligible if set(r["labels"]) == {"A"}],
        "contains_BC": [r for r in eligible if set(r["labels"]) != {"A"}],
        "less_exposed": [r for r in eligible if r["less_exposed"]],
    }
    comps = {name: {method: {
        "match": run.stage.v42.paired(sample, method, ANCHORED),
        **{field: archived.grade_pair(sample, method, ANCHORED, field) for field in ("OPB", "UPB", "FM")},
    } for method in CONTROLS} for name, sample in subsets.items()}
    limits = plan["thresholds"]
    checks = {}
    for method in (GENERIC, RP, REVIEW, C_PRIOR):
        main = comps["eligible"][method]["match"]
        protection = comps["contains_BC"][method]
        main_margin = limits["overall_gain_lower_bound"] if method != C_PRIOR else -limits["C_prior_match_noninferiority_margin"]
        checks[method] = {
            "coverage": main["valid_cases"] >= limits["coverage"] * len(eligible),
            "main": main.get("95pct_source_bootstrap", [-1])[0] > main_margin,
            "BC_match": protection["match"].get("95pct_source_bootstrap", [-1])[0] >= -limits["contains_BC_match_noninferiority_margin"],
            **{field: protection[field].get("95pct_source_bootstrap", [0, 1])[1]
               <= limits["contains_BC_UPB_and_FM_harm_margin_per_answer"] for field in ("UPB", "FM")},
        }
    status = Counter(row["witness"]["status"] for row in rows)
    compiled = [row["witness"] for row in rows if row["witness"]["status"] == "COMPILED"]
    rejects = Counter(e["reason"] for w in compiled for e in w["rejected"])
    witnessed = [row for row in rows if row["witness"]["status"] == "COMPILED"]
    comparisons_per_claim = {kind: len({row["group"] for row in witnessed if row["witness"]["anchored"]["reason"] == kind})
                             for kind in sorted({w["anchored"]["reason"] for w in compiled})}
    strict = [r for r in eligible if all(r["native"][m]["fields"].get("match") is not None
                                         for m in (ANCHORED, GENERIC, RP, REVIEW, C_PRIOR, GATE))]
    same_denominator = {m: sum(r["native"][m]["fields"]["match"]["matched"] for r in strict)
                        for m in (ANCHORED, GENERIC, RP, REVIEW, C_PRIOR, GATE)}
    return {
        "state": run.read(run.OUT / "RUN_STATE.json")["state"], "assigned": len(rows), "eligible": len(eligible),
        "physical_requests": len(ledger), "transport": Counter(r["status"] for r in ledger),
        "reported_tokens": sum((r.get("usage") or {}).get("total_tokens", 0) for r in ledger),
        "unknown_usage": sum("total_tokens" not in (r.get("usage") or {}) for r in ledger),
        "physical_non_success": [r for r in ledger if r["status"] != "OK"],
        "witness_status": status,
        "compiler": {
            "proposed": sum(w["proposed"] for w in compiled), "accepted": sum(w["accepted"] for w in compiled),
            "rejects": rejects, "reasons": Counter(w["anchored"]["reason"] for w in compiled),
            "reason_source_groups": comparisons_per_claim,
            "different_from_C_prior": sum(w["anchored"]["source"] != w["fallback"] for w in compiled),
            "different_from_shape_only": sum(w["anchored"]["source"] != w["shape_only"]["source"] for w in compiled),
        },
        "strict_common": {"roots": len(strict), "groups": len({r["group"] for r in strict}),
                          "positions": sum(r["positions"] for r in strict), "matched": same_denominator},
        "comparisons": comps, "prespecified_screen": checks,
        "screen_pass": all(all(d.values()) for d in checks.values()),
        "new_actor_requests": 0, "new_judge_requests": 0, "behavior_independently_validated": False,
    }


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()
    plan, rows, ledger = collected()
    result = summarize(plan, rows, ledger)
    if args.save:
        if result["state"] != "COMPLETE" or len(ledger) != plan["witness_request_cap"]:
            raise ValueError("Terminal output requires all frozen physical calls")
        run.probe.freeze(run.OUT / "SETTLED.json", {"rows": rows, "ledger": ledger})
        run.probe.freeze(run.OUT / "RESULTS.json", result)
    print(json.dumps({k: v for k, v in result.items() if k not in ("comparisons", "physical_non_success")},
                     ensure_ascii=False, indent=2))
