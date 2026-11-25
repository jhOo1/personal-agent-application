"""Assess saved-draft selection headroom against the C rule without making or grading answers."""
from collections import Counter, defaultdict
import json

from audit_completed import audited_rows
from qamc.common import sha

import run_decision_edit as r

ZERO, RP, GATE, RULE, REVIEW = (r.comparisons.ZERO, r.comparisons.RP, r.comparisons.GATE,
                                r.comparisons.RULE, r.comparisons.REVIEW)
SEVERITY = ("OPB", "UPB", "FM")
PRIMARY_DRAFTS = (ZERO, RP)
WITH_LOCAL_EDITS = (*PRIMARY_DRAFTS, *r.edit.METHODS)
WITH_STRONG_REFERENCES = (*WITH_LOCAL_EDITS, GATE, REVIEW)
EXTRA_ARCHIVES = ("DELTA", "DIRECT_MASKED", "SCOPED_FULL", "SCOPED_MASKED", "RP_POLICY_OVERRIDE")
POOLS = {
    "original_two_drafts": PRIMARY_DRAFTS,
    "plus_both_local_editors": WITH_LOCAL_EDITS,
    "plus_strong_gate_and_review": WITH_STRONG_REFERENCES,
    "plus_previous_qamc_variants": (*WITH_STRONG_REFERENCES, *EXTRA_ARCHIVES),
}


def checked_scores(native, width):
    fields = native.get("fields", {})
    match = fields.get("match")
    if not match or any(type(fields.get(name)) not in (float, int) for name in SEVERITY):
        return None
    if match["positions"] != width or not 0 <= match["matched"] <= width:
        raise ValueError("Native scoring position alignment changed")
    return (match["matched"], *(fields[name] for name in SEVERITY))


def old_candidates(parent):
    proof = {row["uid"]: row for wave, _ in audited_rows(parent) for row in wave}
    if len(proof) != len(parent["roots"]):
        raise ValueError("Whole V41 settled panel is required")
    visibility = r.v42.OUT
    plan = r.read(visibility / "FROZEN.json")
    if r.read(visibility / "RUN_STATE.json")["state"] != "COMPLETE":
        raise ValueError("Whole V42 settled panel is required")
    seen = {}
    for index, ids in enumerate(plan["waves"]):
        rows = r.read(visibility / f"wave_{index:02d}" / "COMPLETED.json")["rows"]
        if [row["uid"] for row in rows] != ids:
            raise ValueError("V42 source roster drifted")
        seen.update({row["uid"]: row for row in rows})
    override = r.read(visibility.with_name("rp_policy_override_rpeval_v43") / "COMPLETED.json")["rows"]
    policy = {row["uid"]: row for row in override}
    if proof.keys() != seen.keys() or proof.keys() != policy.keys():
        raise ValueError("Archived studies are not matched on the same tasks")
    return proof, seen, policy


def analyze():
    parent = r.read(r.prior.OUT / "FROZEN.json")
    if r.read(r.OUT / "RUN_STATE.json")["state"] != "COMPLETE":
        raise ValueError("Whole local-edit study is required")
    primary_path = r.OUT / "SETTLED.json"
    diagnostic_groups = set(r.read(r.OUT / "FROZEN.json")["diagnostic_source_groups"])
    roots = {root["uid"]: root for root in parent["roots"]}
    local = r.read(primary_path)["rows"]
    older, visibility, override = old_candidates(parent)
    drafts = r.task_only.saved_drafts(parent)
    aggregates, origins, groups, detail = defaultdict(Counter), defaultdict(Counter), defaultdict(set), []
    for row in local:
        uid, labels, width = row["uid"], row["labels"], row["positions"]
        root, original, v42, v43 = roots[uid], older[uid], visibility[uid], override[uid]
        if any(row["group"] != saved["group"] or labels != saved["labels"] for saved in (original, v42, v43)):
            raise ValueError("Archive source labels and groups disagree")
        objective = {m: checked_scores(rating, width) for m, rating in row["native"].items()}
        if not all(objective.get(m) for m in (ZERO, RP, RULE)):
            continue
        if original["native"][REVIEW]["fields"] != row["native"][REVIEW]["fields"]:
            raise ValueError("V41 review originally had a different native score")
        hard = any(v["policy"] == "C" for v in root["archived_policy"])
        chosen = RP if hard else ZERO
        base = objective[RULE]
        if base != objective[chosen]:
            raise ValueError("C-rule score does not match the exact original answer")
        answers = {m: root["archived"][m]["answer"] for m in (RP, GATE)}
        answers[ZERO] = drafts[root["task_wire_sha256"]]["answer"]
        if not answers[ZERO] or not answers[RP]:
            raise ValueError("Score-valid initial drafts require actual saved text")
        for m in r.edit.METHODS:
            answers[m] = row["edits"][m].get("answer")
        for m in (REVIEW, "DELTA"):
            answers[m] = original["answers"][m]["answer"]
        objective["DELTA"] = checked_scores(original["native"]["DELTA"], width)
        for m in ("DIRECT_MASKED", "SCOPED_FULL", "SCOPED_MASKED"):
            answers[m] = v42["answers"][m]["answer"]
            objective[m] = checked_scores(v42["native"][m], width)
        answers["RP_POLICY_OVERRIDE"] = v43["answer"]
        objective["RP_POLICY_OVERRIDE"] = checked_scores(v43["native"]["RP_POLICY_OVERRIDE"], width)

        route = "RP_predicts_C" if hard else "RP_does_not_predict_C"
        author_profile = "all_A" if set(labels) == {"A"} else "contains_C" if "C" in labels else "B_without_C"
        strata = ["all", route, author_profile, f"{author_profile}/{route}"]
        if root["group"] not in diagnostic_groups:
            strata.append("outside_documented_diagnostics")
            if "C" in labels:
                strata.append("has_C_outside_documented_diagnostics")
        cells = {}
        for name, methods in POOLS.items():
            unique = {sha(answers[chosen]): RULE}
            conflicts = set()
            for m in methods:
                if not answers[m] or not objective.get(m):
                    continue
                digest = sha(answers[m])
                existing = unique.setdefault(digest, m)
                if objective[existing] != objective[m]:
                    conflicts.add(digest)
            candidates = list(unique.values())
            protected = [m for m in candidates if all(b <= a for a, b in zip(base[1:], objective[m][1:], strict=True))]
            raw_winner = max(candidates, key=lambda m: objective[m][0])
            protected_winner = max(protected, key=lambda m: objective[m][0])
            cell = {"distinct_scored_answers": len(candidates), "conflicting_answer_hashes": len(conflicts),
                    "unconstrained_max": objective[raw_winner][0],
                    "protected_max": objective[protected_winner][0], "protected_origin": protected_winner}
            cells[name] = cell
            for label in strata:
                key = label, name
                groups[key].add(row["group"])
                aggregates[key].update(
                    roots=1, positions=width, C_rule_match=base[0],
                    RP_match=objective[RP][0], task_only_match=objective[ZERO][0],
                    unconstrained_max=cell["unconstrained_max"], protected_max=cell["protected_max"],
                    complete_match_possible=cell["unconstrained_max"] == width,
                    protected_gain_roots=cell["protected_max"] > base[0],
                    identical_answer_scoring_conflicts=bool(conflicts))
                if cell["protected_max"] > base[0]:
                    origins[key][protected_winner] += 1
        detail.append({"uid": uid, "group": row["group"], "strata": strata, "positions": width,
                       "C_rule_match": base[0], "C_rule_answer_sha256": sha(answers[chosen]), "pools": cells})
    return {
        "local_settlement_sha256": sha(primary_path.read_bytes()), "pools": POOLS,
        "strata": {label: {name: {**values, "source_groups": len(groups[label, name]),
                                   "protected_improvement_origins": origins[label, name]}
                          for (k, name), values in aggregates.items() if k == label}
                   for label in dict.fromkeys(k for k, _ in aggregates)},
        "roots": detail, "new_model_calls": 0, "new_native_scores": 0,
        "note": "Same-answer variants are collapsed, preferring the C-rule score then the declared pool order. "
                "The protected maximum requires case-level OPB, UPB and FM at most the observed C-rule values. "
                "These maxima use already-seen native grades for hindsight, not a deployable selector, new scores or generalization evidence.",
    }


if __name__ == "__main__":
    print(json.dumps(analyze(), ensure_ascii=False, indent=2))
