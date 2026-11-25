"""Trace author B/C positions to the same-draft main answer's input and contract."""
from collections import Counter, defaultdict
import json

import run_realization_append_ablation as ablation
from settle_decision_realization import checked, reconciling_actors


def audit():
    _, rows, _ = checked()
    archive = ablation.read(ablation.parent.joint.prior.OUT / "FROZEN.json")
    roots = {root["uid"]: root for root in archive["roots"]}
    reconciling_actors(rows, roots)
    main_rows = {r["uid"]: r for r in ablation.read(ablation.OUT / "SETTLED.json")["rows"]}
    by_arm = defaultdict(Counter)
    cases = []
    for row in rows:
        uid = row["uid"]
        if set(row["labels"]) == {"A"}:
            continue
        trace = row["selection"]
        usable = row["actor"][ablation.method.SEGMENTED]["status"] == "OK"
        segmented = trace.get("route") == "SEGMENTED"
        licenses = {item["memory_id"]: item["use"] for item in trace.get("uses", ())}
        labeled = dict(zip((s["memory_id"] for s in roots[uid]["original_sources"]), row["labels"], strict=True))
        by_position = {}
        for mid, label in labeled.items():
            if label == "A":
                continue
            use = licenses.get(mid)
            if not usable:
                route = "NO_USABLE_ACTOR"
            elif not use:
                route = "SOURCE_NOT_IN_ACTOR"
            elif segmented and use == "OPTIONAL":
                route = "VISIBLE_OPTIONAL_FORBIDDEN_IN_MAIN"
            else:
                route = use
            by_position[mid] = {"author_label": label, "main_contract": route}
        metrics = main_rows[uid]["native"]
        main = metrics[ablation.MAIN_ONLY]["fields"].get("UPB")
        gate = metrics[ablation.parent.GATE]["fields"].get("UPB")
        comparison = "MISSING" if main is None or gate is None else "WORSE" if main > gate else "BETTER" if main < gate else "TIE"
        blocked = {"SOURCE_NOT_IN_ACTOR", "VISIBLE_OPTIONAL_FORBIDDEN_IN_MAIN"}
        blocked_positions = sum(entry["main_contract"] in blocked for entry in by_position.values())
        row_counts = by_arm[comparison]
        row_counts["cases"] += 1
        row_counts["with_main_unavailable_position"] += blocked_positions > 0
        row_counts["usable_actor_all_author_BC_eligible"] += usable and blocked_positions == 0
        row_counts["without_usable_actor"] += not usable
        for entry in by_position.values():
            row_counts[entry["author_label"] + "/" + entry["main_contract"]] += 1
        if comparison != "MISSING":
            row_counts["UPB_MAIN"] += main
            row_counts["UPB_GATE"] += gate
        cases.append({"uid": uid, "group": row["group"], "gate_upb": gate, "main_upb": main,
                      "comparison": comparison, "positions": by_position})
    return {"assigned": len(rows), "mixed_cases": len(cases), "coverage_by_upb_comparison": by_arm,
            "cases": cases, "new_requests": 0,
            "interpretation": "Visibility and eligibility are not evidence of actual use."}


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2, sort_keys=True))
