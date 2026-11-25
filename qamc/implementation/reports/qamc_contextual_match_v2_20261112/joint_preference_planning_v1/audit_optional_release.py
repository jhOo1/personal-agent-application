"""Measure the support and score-reuse ceiling of an archived RP-B release rule."""
from collections import Counter
import json

from qamc.common import parse_object, sha

import decision_realization as method
import run_realization_append_ablation as ablation
from settle_decision_realization import checked


def release(row, archived_policy):
    actor = row["actor"][method.SEGMENTED]
    main = parse_object(actor["raw"])["main_answer"]
    full, added, rejected = method.compile_answer(actor["raw"], row["selection"]["uses"], method.SEGMENTED)
    if (full, added, rejected) != (actor["answer"], actor["appended_sources"], actor["rejected_adjustments"]):
        raise ValueError("Structured Actor receipt no longer matches the compiler")
    predicted = {item["memory_id"]: item["policy"] for item in archived_policy}
    allowed = {mid for mid in added if predicted.get(mid) == "B"}
    uses = [edge for edge in row["selection"]["uses"] if edge["use"] != "OPTIONAL" or edge["memory_id"] in allowed]
    answer, kept, _ = method.compile_answer(actor["raw"], uses, method.SEGMENTED)
    if set(kept) != allowed or not (answer == main or answer.startswith(main + "\n\n")):
        raise ValueError("Release rule changed answer outside retained additions")
    if answer == main:
        control = ablation.MAIN_ONLY
    elif answer == full:
        control = method.SEGMENTED
    else:
        control = None
    return main, answer, kept, control


def audit():
    _, rows, _ = checked()
    inputs = ablation.read(ablation.parent.joint.prior.OUT / "FROZEN.json")["roots"]
    by_uid = {root["uid"]: root for root in inputs}
    changed = ablation.changed_answers(rows)
    counts, transitions, accepted = Counter(), Counter(), Counter()
    records, choices = [], {}
    for row in rows:
        uid = row["uid"]
        if uid not in changed:
            choices[uid] = ablation.MAIN_ONLY
            continue
        root = by_uid[uid]
        main, answer, kept, control = release(row, root["archived_policy"])
        choices[uid] = control
        labels = dict(zip((m["memory_id"] for m in root["original_sources"]), row["labels"], strict=True))
        predicted = {m["memory_id"]: m["policy"] for m in root["archived_policy"]}
        added = changed[uid][2]
        transitions.update(labels[mid] + "/" + predicted.get(mid, "UNKNOWN") for mid in added)
        accepted.update(labels[mid] for mid in kept)
        counts[control or "NEW_COMBINATION"] += 1
        records.append({"uid": uid, "group": row["group"], "kept": kept, "old": added,
                        "archived_score_source": control, "answer_sha256": sha(answer), "main_sha256": sha(main)})
    settled = ablation.read(ablation.OUT / "SETTLED.json")["rows"]
    compared = []
    for row in settled:
        known = choices[row["uid"]]
        if known:
            compared.append({**row, "native": {**row["native"], "RP_B_RELEASE": row["native"][known]}})
    common = {control: ablation.v42.paired(compared, control, "RP_B_RELEASE")
              for control in (ablation.MAIN_ONLY, method.SEGMENTED, ablation.parent.GATE, ablation.parent.RP)}
    opportunities = {row["uid"]: row for row in records}
    ceilings = {baseline: ceiling(settled, opportunities, baseline)
                for baseline in (ablation.parent.RP, ablation.parent.GATE, ablation.MAIN_ONLY, ablation.parent.RULE)}
    return {"assigned": len(rows), "appended_cases": len(changed), "append_prediction_confusion": transitions,
            "retained_by_author_label": accepted, "routes_on_appended_cases": counts,
            "retained_cases": sum(bool(row["kept"]) for row in records),
            "retained_source_groups": len({row["group"] for row in records if row["kept"]}),
            "known_only_common_valid": common, "optimistic_bounds": ceilings,
            "rows": records, "new_live_requests": 0}


def ceiling(rows, opportunities, baseline):
    """Grant full marks to every case where a genuinely new RP-B subset can be formed."""
    totals = Counter({"cases": 0, "positions": 0, "baseline": 0, "main": 0,
                      "best_saved_either_arm": 0, "best_rp_b_subset_upper_bound": 0,
                      "unknown_subset_cases": 0, "unknown_subset_positions": 0})
    for row in rows:
        names = (ablation.MAIN_ONLY, method.SEGMENTED, baseline)
        scores = [row["native"][name]["fields"].get("match") for name in names]
        if any(score is None for score in scores):
            continue
        main, full, control = [score["matched"] for score in scores]
        n = row["positions"]
        opp = opportunities.get(row["uid"], {})
        eligible = len(opp.get("kept", ()))
        original = len(opp.get("old", ()))
        totals["cases"] += 1
        totals["positions"] += n
        totals["main"] += main
        totals["baseline"] += control
        totals["best_saved_either_arm"] += max(main, full)
        unknown = eligible > 1 or 0 < eligible < original
        if unknown:
            totals["unknown_subset_cases"] += 1
            totals["unknown_subset_positions"] += n
        upper = n if unknown else max(main, full) if eligible else main
        totals["best_rp_b_subset_upper_bound"] += upper
    return totals


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2, sort_keys=True))
