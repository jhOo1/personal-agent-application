"""Compare archived source admissions before delivery formatting and native grading."""
from collections import Counter
import json

import run_outcome_contract as run


def compare():
    _, _, roots, _, _, _ = run.prepare()
    settled_folder = run.OUT / "item_header_recovery"
    if run.read(settled_folder / "RUN_STATE.json")["state"] != "COMPLETE":
        raise ValueError("Outcome run has not settled")
    completed = run.read(settled_folder / "SETTLED.json")
    previous = run.OUT.with_name("decision_realization_rpeval_v1")
    prior = {r["uid"]: r["selection"] for r in run.read(previous / "SETTLED.json")["rows"]}
    marginal = Counter()
    paired = Counter()
    cohorts = Counter()
    outcomes = []
    for row in completed["rows"]:
        uid = row["uid"]
        new = completed["contracts"][uid]
        old = prior[uid]
        labels = dict(zip((s["memory_id"] for s in roots[uid]["original_sources"]), row["labels"], strict=True))
        marginal.update(f"{label}/assigned" for label in labels.values())
        cohorts[f"{new['status']}/{old['status']}"] += 1
        if new["status"] != "OK":
            continue
        new_admitted = {u["witness"].rsplit(".", 1)[0] for u in new["uses"]}
        new_guard = {u["witness"].rsplit(".", 1)[0] for u in new["uses"] if u["force"] == "REQUIRE"}
        old_admitted = {u["memory_id"] for u in old.get("uses", [])}
        old_guard = {u["memory_id"] for u in old.get("uses", []) if u["use"] == "GUARD"}
        if any(not values <= labels.keys() for values in (new_admitted, new_guard, old_admitted, old_guard)):
            raise ValueError("Source IDs do not align across archives")
        if old["status"] == "OK":
            outcomes.append({"uid": uid, "group": row["group"], "old": sorted(old_admitted),
                             "new": sorted(new_admitted), "same_visibility": old_admitted == new_admitted,
                             "new_hard": sorted(new_guard), "old_hard": sorted(old_guard)})
        for mid, label in labels.items():
            marginal[f"{label}/valid_contract"] += 1
            marginal[f"{label}/admitted"] += mid in new_admitted
            marginal[f"{label}/hard"] += mid in new_guard
            if old["status"] != "OK":
                continue
            paired[f"{label}/total"] += 1
            paired[f"{label}/new_admitted"] += mid in new_admitted
            paired[f"{label}/old_admitted"] += mid in old_admitted
            paired[f"{label}/new_hard"] += mid in new_guard
            paired[f"{label}/old_hard"] += mid in old_guard
    return {"cohort_statuses": cohorts, "marginal_by_author_label": marginal, "paired_by_author_label": paired,
            "same_visibility": sum(u["same_visibility"] for u in outcomes), "shared_usable": len(outcomes),
            "rows": outcomes, "raw_native_scores_modified": 0, "real_requests": 0}


if __name__ == "__main__":
    print(json.dumps(compare(), ensure_ascii=False, indent=2, sort_keys=True))
