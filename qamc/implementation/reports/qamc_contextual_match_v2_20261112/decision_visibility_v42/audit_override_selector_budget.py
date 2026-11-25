"""Compare saved prediction routes with one or two selectors. Native outcomes stay untouched."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
import json

from cost_policy_override_v43 import parent_selection
from deployment_cost import numeric_cost, profile
import run_policy_override_v43 as run


def audit(expected=None):
    plan, roots = run.prepare(expected)
    parent, receipts = parent_selection(plan)
    truth = {row["uid"]: row["labels"] for wave in plan["input_sources"] for row in run.read(
        run.v42.OUT / f"wave_{wave['wave']:02d}" / "COMPLETED.json"
    )["rows"]}
    counts, groups = defaultdict(Counter), defaultdict(set)
    equivalence, usage, jointly_usable = defaultdict(Counter), [], 0
    archived_actors = run.inherited_receipts(plan)[run.ACTOR]
    known_hashes = {*archived_actors, *(r["archived_actor_sha256"] for r in roots.values())}
    scheduled_hashes = {item["actor_sha256"] for item in plan["roots"] if item["edits"]}
    unknown_hashes = defaultdict(set)
    shared_unknown_hashes = defaultdict(set)
    for record in plan["roots"]:
        uid, group = record["uid"], record["group"]
        root, chosen = roots[uid], parent[uid]
        baseline = {p["memory_id"]: p["policy"] for p in root["archived_policy"]}
        controls = {m: run.candidate(root, {arm: chosen[m] for arm in chosen})[0]
                    for m in ("DIRECT", "SCOPED")}
        controls["AGREEMENT"] = record["edits"]
        for m in ("DIRECT", "SCOPED"):
            target = equivalence[m]
            wire = run.sha(run.policy_only_request(root, controls[m]))
            if (wire == record["actor_sha256"]) != (controls[m] == record["edits"]):
                raise ValueError("Equivalent policies no longer compile to the same Actor request")
            target.update(roots=1, same_actor_request=controls[m] == record["edits"],
                          edited_in_both=bool(controls[m] and record["edits"]),
                          extra_edited=bool(controls[m] and not record["edits"]),
                          matches_archived_receipt=wire in known_hashes,
                          matches_other_v43_plan_hash=wire in scheduled_hashes and wire != record["actor_sha256"])
            if wire not in known_hashes and wire not in scheduled_hashes:
                unknown_hashes[m].add(wire)
            if wire in archived_actors and archived_actors[wire][0]["status"] != "OK":
                shared_unknown_hashes[m].add(wire)
        has_b = "B" in baseline.values()
        bill = {m: numeric_cost(receipts[chosen[m]["request_sha256"]].get("usage"))
                if has_b else Counter() for m in ("DIRECT", "SCOPED")}
        if all(amount is not None for amount in bill.values()):
            bill["AGREEMENT"] = bill["DIRECT"] + bill["SCOPED"]
            usage.append({"group": group, "usage": bill})
        if any(v["scope"] is None for v in chosen.values()):
            continue
        jointly_usable += 1
        labels = truth[uid]
        scope = ("all", "reviewed_prefix" if record["parent_wave"] <= 4 else "later_prefix",
                 "all_A" if set(labels) == {"A"} else "contains_BC")
        for (mid, previous), label in zip(baseline.items(), labels, strict=True):
            if previous != "B":
                continue
            for method, actions in controls.items():
                action = actions.get(mid)
                for name in scope:
                    key = (method, name)
                    counts[key].update(old_B_positions=1, edited=action is not None,
                                       corrected=action == label, changed_author_B=action is not None and label == "B",
                                       wrong_to_wrong=action is not None and label not in (action, "B"),
                                       C_restored=action == label == "C", C_erased=action == "A" and label == "C")
                    if action:
                        groups[key].add(group)
    return {
        "roots": len(plan["roots"]), "complete_parent": not plan["preview"], "valid_two_selectors": jointly_usable,
        "label_position_diagnostics": {f"{m}/{tag}": {**row, "edited_source_groups": len(groups[m, tag])}
                                       for (m, tag), row in counts.items()},
        "same_frozen_actor_input": equivalence,
        "unknown_actor_requests_even_after_v43": {method: len(unknown_hashes[method]) for method in ("DIRECT", "SCOPED")},
        "archived_non_successful_actor_hashes": {
            method: len(shared_unknown_hashes[method]) for method in ("DIRECT", "SCOPED")
        },
        "standalone_selector_usage": profile(usage, ("DIRECT", "SCOPED", "AGREEMENT")),
        "new_calls": 0, "semantic_scores": 0,
    }


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--expected", type=int, help="Analyze the specified settled prefix offline.")
    args = parser.parse_args()
    print(json.dumps(audit(args.expected), ensure_ascii=False, indent=2))
