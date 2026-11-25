"""Replay prediction-limited memory influences on frozen planner proposals."""
from collections import Counter, defaultdict
import json

from qamc.common import sha

from analyze_planning import domains_for, planning_receipts
from intervention import archived_packet
import planning
import run_joint_planning as run


def predicted_policy(root):
    _, packet = archived_packet(root)
    pairs = packet["preference_use_policy"]
    ids = [entry["memory_id"] for entry in packet["source_evidence"]]
    if ([entry["memory_id"] for entry in pairs] != ids or len(ids) != len(set(ids))
            or any(entry["policy"] not in ("A", "B", "C") for entry in pairs)):
        raise ValueError("The RP prediction must align to exact source IDs in wire order")
    return {entry["memory_id"]: entry["policy"] for entry in pairs}


def compile_flows(plan, policy):
    """Bound only declared effects. Free-text alternatives retain their provenance uncertainty."""
    compiled = {**plan, "hard": [], "soft": []}
    counts, affected = Counter(), []
    for kind in ("hard", "soft"):
        for row in plan[kind]:
            source = row["source_id"]
            label = "TASK" if source == "TASK" else policy[source]
            allowed = label in ("C", "TASK") if kind == "hard" else label == "B"
            action = ("KEPT" if allowed else "UNRESOLVED_STRENGTH" if label == "C" else "REJECTED")
            counts[f"{label}_{kind}_{action}"] += 1
            affected.append({"source_id": source, "policy": label, "kind": kind,
                             "choices": row["choices"], "action": action})
            if allowed:
                compiled[kind].append(row)
    return compiled, counts, affected


def compare(root, trace, original_actor_hashes):
    """Keep the original solver in both arms to isolate clause compilation."""
    policy = predicted_policy(root)
    plan = trace["plan"]
    compiled, counts, affected = compile_flows(plan, policy)
    original = trace["selections"][run.SOLVED]
    model = trace["selections"][run.MODEL]
    domains = domains_for(plan)
    recalc = planning.solve(domains, plan["hard"], plan["soft"], model)
    if recalc["selection"] != original:
        raise ValueError("The original choice cannot be reproduced")
    edited = planning.solve(domains, compiled["hard"], compiled["soft"], model)
    selection = edited["selection"]
    data = planning.packet(root)
    frozen_hash = sha(planning.actor_request(data, plan, original))
    bounded_hash = sha(planning.actor_request(data, compiled, selection))
    if frozen_hash not in original_actor_hashes:
        raise ValueError("The original solver request is absent from the Actor manifest")
    protected_c = set(x["source_id"] for x in compiled["hard"] if x["source_id"] != "TASK")
    ranked_b = set(x["source_id"] for x in compiled["soft"])
    ignored_support = [row["choices"] for row in affected if row["policy"] == "A" and row["kind"] == "soft"]
    result = {
        "sources": Counter(policy.values()),
        "clauses": counts,
        "flows": affected,
        "original_selection": original,
        "bounded_selection": selection,
        "actor_request_sha256": bounded_hash,
        "changed_plan_clauses": compiled != plan,
        "changed_selection": original != selection,
        "selection_differs_from_model": model != selection,
        "same_selection_with_changed_clauses": original == selection and compiled != plan,
        "changed_actor_wire": frozen_hash != bounded_hash,
        "new_actor_wire": bounded_hash not in original_actor_hashes,
        "predicts_BC": any(label in ("B", "C") for label in policy.values()),
        "eligible_B_sources_with_rank_support": len(ranked_b),
        "eligible_C_sources_with_hard_guard": len(protected_c),
        "predicted_C_sources_without_hard_guard": sum(label == "C" for label in policy.values()) - len(protected_c),
        "original_selected_choices_linked_to_rejected_A": bool(
            original and any(planning.dominates(original, choices) for choices in ignored_support)),
        "bounded_selected_choices_linked_to_rejected_A": bool(
            selection and any(planning.dominates(selection, choices) for choices in ignored_support)),
        "has_feasible_selection": selection is not None,
    }
    return result


def audit():
    frozen_path = run.OUT / "FROZEN.json"
    actor_path = run.OUT / f"{run.ACTOR}_MANIFEST.json"
    archive_path = run.prior.OUT / "FROZEN.json"
    if run.read(run.OUT / "RUN_STATE.json")["state"] != "COMPLETE":
        raise ValueError("The shared-planner replay requires terminal state")
    frozen = run.read(frozen_path)
    archive_key = str(archive_path.relative_to(run.HERE.parent.parent.parent))
    if sha(archive_path.read_bytes()) != frozen["hashes"][archive_key]:
        raise ValueError("Frozen source and policy archive changed")
    roots = run.read(archive_path)["roots"]
    traces, _ = planning_receipts(frozen)
    actor_jobs = run.read(actor_path)["units"]
    actor_wires = {sha(job["request"]) for job in actor_jobs}
    if {root["uid"] for root in roots} != traces.keys() or len(actor_wires) != len(actor_jobs):
        raise ValueError("The original task or Actor roster does not match")

    rows, counts, groups, policy, flows = {}, Counter(), defaultdict(Counter), Counter(), Counter()
    new_wires = set()
    for root in roots:
        uid, group = root["uid"], root["group"]
        trace = traces[uid]
        if "plan" not in trace or trace.get("actor_status"):
            counts[trace.get("actor_status", trace["status"])] += 1
            continue
        result = compare(root, trace, actor_wires)
        rows[uid] = {"source_group": group, **result}
        policy.update(result["sources"])
        flows.update(result["clauses"])
        counters = {
            "replayed": 1,
            **{key: result[key] for key in (
                "changed_plan_clauses", "changed_selection", "selection_differs_from_model",
                "same_selection_with_changed_clauses", "changed_actor_wire",
                "new_actor_wire", "predicts_BC", "has_feasible_selection",
                "eligible_B_sources_with_rank_support", "eligible_C_sources_with_hard_guard",
                "predicted_C_sources_without_hard_guard", "original_selected_choices_linked_to_rejected_A",
                "bounded_selected_choices_linked_to_rejected_A",
            )},
        }
        counts.update(counters)
        groups[group].update(counters)
        if result["new_actor_wire"]:
            new_wires.add(result["actor_request_sha256"])

    return {
        "assigned": len(roots),
        "case_counts": counts,
        "predicted_positions": policy,
        "explicit_flows": flows,
        "by_source_group": groups,
        "candidate_unique_new_actor_wires": len(new_wires),
        "new_requests": 0,
        "new_scores": 0,
        "inputs_sha256": {path.name: sha(path.read_bytes()) for path in (frozen_path, actor_path)},
        "limitations": [
            "Only the archived RP predictions are used for gating; author labels and scores are never read.",
            "The same deterministic solver is used on both sides; comparison to model choice is descriptive.",
            "Role and scope entailment are not structurally certified by the frozen proposal.",
            "Fixed option text and raw Actor memory can still carry unauthorized influences.",
        ],
        "per_case": rows,
    }


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
