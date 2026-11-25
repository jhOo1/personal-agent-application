"""Compare archived B/C permissions and RP predictions on exposed RPEval roots."""
from collections import Counter, defaultdict
import json

import run_main_answer_revision as run
from settle_decision_realization import reconciling_actors


def audit():
    _, rows, _ = run.checked()
    archives = run.read(run.joint.prior.OUT / "FROZEN.json")
    roots = {row["uid"]: row for row in archives["roots"]}
    plan = run.read(run.joint.prior.formal.OUT / "PLAN.json")
    public_tracks = {row["uid"]: row["track"] for row in plan["cases"]
                     if not row["independent_confirmation"] and row["uid"] in roots}
    reconciling_actors(rows, roots)
    counts, supported_groups = defaultdict(Counter), defaultdict(set)
    rp_common, case_details = Counter(), []
    for row in rows:
        uid = row["uid"]
        root = roots[uid]
        track = public_tracks.get(uid, "other_exposed")
        selection = row["selection"]
        licenses = {item["memory_id"]: item for item in selection.get("uses", [])}
        policies = {item["memory_id"]: item["policy"] for item in root["archived_policy"]}
        actor_usable = row["actor"][run.edit.realization.SEGMENTED]["status"] == "OK"
        for source, label in zip(root["original_sources"], row["labels"], strict=True):
            if label not in ("B", "C"):
                continue
            mid = source["memory_id"]
            license = licenses.get(mid)
            strength = license["use"] if license else "OMITTED"
            if not actor_usable:
                strength = "NO_ACTOR"
            key = f"{label}/{strength}"
            counts[track][key] += 1
            supported_groups[track, key].add(row["group"])
            if actor_usable and row["native"][run.RP]["fields"].get("match") is not None:
                rp_common[f"{label}/{strength}/{policies[mid]}"] += 1
            if label == "C" and strength not in ("GUARD", "NO_ACTOR"):
                case_details.append({
                    "uid": uid, "group": row["group"], "track": track, "source_id": mid,
                    "main_use": strength, "archived_rp_policy": policies[mid],
                    "license": license, "original_source": source["text"],
                })
    return {"by_track": counts, "source_groups_by_track_and_use": {
                "/".join(key): len(groups) for key, groups in supported_groups.items()},
            "rp_common_action_labels": rp_common,
            "c_available_actor_non_guard_cases": case_details,
            "non_guard_c_source_groups": len({row["group"] for row in case_details}),
            "new_requests": 0, "native_scores_modified": 0,
            "interpretation": "Author C and actual hard constraints are distinct. "
                              "The table tracks permissions, not necessarily the effect of the final answer."}


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2, sort_keys=True))
