"""Separate the saved-receipt bill from a standalone V43 generation footprint."""
from argparse import ArgumentParser
from collections import Counter
import json

from deployment_cost import numeric_cost, old_cost, profile
from trace_cost import samples

import run_policy_override_v43 as stage

RP, GATE = stage.prior.RP, stage.prior.GATE
REVIEW = "REVIEW"


def parent_selection(plan):
    data, physical = {}, {}
    for item in plan["input_sources"]:
        path = stage.v42.OUT / f"wave_{item['wave']:02d}" / "COMPLETED.json"
        if stage.sha(path.read_bytes()) != item["sha256"]:
            raise ValueError("Parent receipt snapshot changed")
        saved = stage.read(path)
        data.update({r["uid"]: r["selected"] for r in saved["rows"]})
        physical.update({r["request_sha256"]: r for r in saved["ledger"]
                         if r["unit"]["stage"] == stage.v42.SELECTOR})
    return data, physical


def cost(roots, selection, selector_receipts, edits, final=None):
    formal = stage.prior.read(stage.prior.formal.OUT / "PLAN.json")
    answer_usage, reviews = {}, {}
    if final is not None:
        _, rows, receipts = samples()
        reviews = {row["uid"]: row for row in rows}
        review_receipts = {(r["stage"], r["request_sha256"]): r for r in receipts}
        answer_usage = final["actor_receipts"]
    results = []
    for uid, policies in selection.items():
        root = roots[uid]
        has_b = any(p["policy"] == "B" for p in root["archived_policy"])
        selectors = [numeric_cost(selector_receipts[p["request_sha256"]].get("usage"))
                     for p in policies.values()] if has_b else []
        overhead = sum(selectors, Counter()) if all(s is not None for s in selectors) else None
        rp = old_cost(formal, root, RP)
        row = {"uid": uid, "group": root["group"], "archived_RP_has_B": has_b,
               "usage": {"two_extra_selectors": overhead} if overhead is not None else {}}
        if rp is not None:
            row["usage"][RP] = rp
        earlier = stage.prior.receipt(formal, uid, RP, stage.ACTOR) if rp is not None and edits[uid] else None
        prior_actor = numeric_cost(earlier["response"].get("usage")) if earlier else None
        if rp is not None and overhead is not None and (not edits[uid] or prior_actor is not None):
            row["usage"]["minimum_if_edited_actor_free"] = rp + overhead - (prior_actor or Counter())
        if final is not None:
            tr = final["by_uid"][uid]
            review = reviews[uid]
            gate = old_cost(formal, root, GATE)
            if gate is not None:
                row["usage"][GATE] = gate
            if rp is not None and overhead is not None and tr["answer"]:
                if not tr["trace"]["edits"]:
                    merged = rp + overhead
                else:
                    after = numeric_cost(answer_usage.get(tr["trace"]["actor_sha256"], {}).get("usage"))
                    merged = rp - prior_actor + overhead + after if prior_actor is not None and after is not None else None
                if merged is not None:
                    row["usage"][stage.METHOD] = merged
            if rp is not None and review["answers"][REVIEW]["status"] == "OK":
                revision = review_receipts.get((stage.prior.FINAL, review["trace"]["review_sha256"][REVIEW]))
                draft = review_receipts.get((stage.prior.DRAFT, root["task_wire_sha256"]))
                values = [numeric_cost(r.get("usage")) if r else None for r in (draft, revision)]
                if all(v is not None for v in values):
                    row["usage"][REVIEW] = rp + sum(values, Counter())
            native = {**tr["native"], REVIEW: review["native"][REVIEW]}
            row["matched"] = {m: v["fields"]["match"]["matched"] for m, v in native.items()
                              if "match" in v["fields"]}
            row["positions"] = tr["positions"]
        results.append(row)
    return results


def summarize(expected=None):
    plan, roots = stage.prepare(expected)
    selection, selector_cache = parent_selection(plan)
    final = None
    if expected is None:
        if stage.read(stage.OUT / "RUN_STATE.json")["state"] != "COMPLETE" or stage.read(
            stage.OUT / "FROZEN.json"
        ) != plan:
            raise ValueError("V43 needs to settle before costing its amended answers")
        result = stage.read(stage.OUT / "COMPLETED.json")
        inherited = stage.inherited_receipts(plan)[stage.ACTOR]
        final = {"by_uid": {row["uid"]: row for row in result["rows"]},
                 "actor_receipts": {**{k: r for k, (r, _) in inherited.items()},
                                     **{r["request_sha256"]: r for r in result["ledger"]
                                        if r["unit"]["stage"] == stage.ACTOR}}}
        formal = stage.prior.read(stage.prior.formal.OUT / "PLAN.json")
        for uid, root in roots.items():
            digest = root["archived_actor_sha256"]
            old = stage.prior.receipt(formal, uid, RP, stage.ACTOR)
            if old is not None:
                final["actor_receipts"].setdefault(digest, {"usage": old["response"].get("usage")})
    rows = cost(roots, selection, selector_cache, {r["uid"]: bool(r["edits"]) for r in plan["roots"]}, final)
    report = {"roots": len(rows), "has_RP_B": sum(r["archived_RP_has_B"] for r in rows),
              "pre_edit_overhead": profile(rows, (RP, "two_extra_selectors", "minimum_if_edited_actor_free")),
              "new_model_calls": 0,
              "interpretation": ("Two selectors can be skipped when the RP output has no B. "
                                 "Missing usage stays missing. Cold costs exclude grading and count only "
                                 "one actor per standalone V43 answer. No semantic scores in preview.")}
    if final is not None:
        methods = (RP, GATE, REVIEW, stage.METHOD)
        matched = [r for r in rows if set(methods) <= r["matched"].keys() and set(methods) <= r["usage"].keys()]
        report["shared_cost_and_match"] = {
            **profile(matched, methods), "positions": sum(r["positions"] for r in matched),
            "matched": {m: sum(r["matched"][m] for r in matched) for m in methods},
        }
        report["comparison_call_counts"] = {RP: 3, GATE: 2, REVIEW: 5,
                                            stage.METHOD: {"RP_B": 5, "no_RP_B": 3}}
        report["available_per_method"] = Counter(m for r in rows for m in methods if m in r["usage"])
    return report


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--expected", type=int, help="Run a receipt-only preflight over a settled prefix.")
    args = parser.parse_args()
    print(json.dumps(summarize(args.expected), ensure_ascii=False, indent=2))
