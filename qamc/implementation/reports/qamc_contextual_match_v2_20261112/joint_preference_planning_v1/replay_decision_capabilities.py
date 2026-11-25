"""Exercise scoped option operations on a fixed, exposed sample of saved plans."""
from collections import Counter, defaultdict
import json

from qamc.common import sha

import planning
import run_main_answer_revision as run


def execute(domains, baseline, grants, actions):
    """Apply only option-level operations; preserve unaffected decisions."""
    rank = {key: Counter() for key in domains}
    blocked = {key: set() for key in domains}
    accepted, rejected = [], []
    for source, slot, operation, option in actions:
        command = source, slot, operation, option
        if (slot not in domains or option not in domains[slot] or operation not in ("GUARD", "RANK")
                or command not in grants):
            rejected.append(command)
        elif command not in accepted:
            accepted.append(command)
            if operation == "GUARD":
                blocked[slot].add(option)
            else:
                rank[slot][option] += 1
    output = {}
    for slot, options in domains.items():
        surviving = [key for key in options if key not in blocked[slot]]
        # Prefer the already selected option when no accepted action distinguishes the choices.
        output[slot] = sorted(surviving, key=lambda key: (
            options[key]["task_cost"], options[key]["conditional_on"] is not None,
            -rank[slot][key], key != baseline[slot],
        ))
    return output, accepted, rejected


def select(rows, n=30):
    groups = defaultdict(list)
    for row in rows:
        groups[row["group"]].append(row)
    if len(groups) < n:
        raise ValueError("Not enough exposed source groups")
    ranked = sorted(groups, key=lambda key: sha(["capability-replay-v1", key]))
    return [min(groups[key], key=lambda row: sha(["capability-replay-v1", row["uid"]])) for key in ranked[:n]]


def audit():
    stored = run.read(run.joint.OUT / "SETTLED.json")
    archive = run.read(run.joint.prior.OUT / "FROZEN.json")
    roots = {r["uid"]: r for r in archive["roots"]}
    sample = select(stored["rows"])
    cases, totals = [], Counter()
    for row in sample:
        uid = row["uid"]
        plan = row["planning"]
        totals["assigned"] += 1
        if plan["status"] != "OK":
            totals["unusable_plan"] += 1
            cases.append({"uid": uid, "source_group": row["group"], "status": plan["status"]})
            continue
        root = roots[uid]
        packed = planning.packet(root)
        parsed, matches, _ = planning.compile_plan(packed, plan["raw"])
        if parsed != plan["plan"] or matches != plan["selections"]:
            raise ValueError(f"Saved planning receipt changed: {uid}")
        domains = {f"D{i}": {f"O{j}": option for j, option in enumerate(d["options"], 1)}
                   for i, d in enumerate(parsed["decisions"], 1)}
        # The full history was sent to the archived Planner; alternative-level source exclusions were not recorded.
        totals["memory_visible_plans"] += 1
        totals["options_without_task_only_provenance"] += sum(len(choices) for choices in domains.values())
        grants, cross_slot = set(), 0
        for op, field in (("RANK", "soft"), ("GUARD", "hard")):
            for edge in parsed[field]:
                if len(edge["choices"]) != 1:
                    cross_slot += 1
                    continue
                (slot, option), = edge["choices"].items()
                grants.add((edge["source_id"], slot, op, option))
        baseline = matches[planning.MODEL]
        unchanged, _, _ = execute(domains, baseline, set(), [])
        allowed, accepted, _ = execute(domains, baseline, grants, sorted(grants))
        if any(set(unchanged[slot]) - set(allowed[slot])
               != {option for _, target, op, option in accepted if target == slot and op == "GUARD"}
               for slot in domains):
            raise ValueError("A soft ranking removed an option")
        invalid = {(src, other, op, option) for src, slot, op, option in grants
                   for other, values in domains.items() if other != slot and option in values} - grants
        checked, _, rejected = execute(domains, baseline, grants, sorted(grants | invalid))
        if checked != allowed or len(rejected) != len(invalid):
            raise ValueError("A replayed action escaped its designated decision")
        totals["cross_decision_uncompiled"] += cross_slot
        totals["invalid_rebindings_denied"] += len(invalid)
        totals["rank_or_filter_changed"] += allowed != unchanged
        totals["empty_option_domain"] += any(not values for values in allowed.values())
        cases.append({"uid": uid, "source_group": row["group"], "status": "OK",
                      "ranked_without_operators": unchanged, "ranked_with_operators": allowed,
                      "modifier_count": len(grants), "cross_decision_uncompiled": cross_slot,
                      "invalid_rebindings_denied": len(invalid)})
    return {"totals": totals, "cases": cases, "new_requests": 0, "new_native_scores": 0,
            "interpretation": "Old plan options and scope are model outputs already conditioned on memory. "
                              "The replay proves syntactic locality for typed operations, not semantic separation."}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, ensure_ascii=False, sort_keys=True))
