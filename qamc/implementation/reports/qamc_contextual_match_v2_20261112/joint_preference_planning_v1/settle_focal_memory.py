"""Audit settled focal selection, downstream transmission and comparable costs."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
import json

from deployment_cost import numeric_cost, old_cost, profile
from qamc.common import sha

import focal_memory as focal
import run_focal_memory as run
from audit_archived_policy_edits import policy_only_request
from settle_joint_planning import replay_readonly, subsets, usage


def replay_soft_veto(rows, roots):
    """Withhold a predicted RP soft influence only when the new arm says ignore."""
    arms = {method: method + "_SOFT_VETO" for method in focal.METHODS}
    triggers, source_groups, cases, replayed = Counter(), defaultdict(set), [], []
    for row in rows:
        uid, index = row["uid"], row["focus_index"]
        root = roots[uid]
        saved = root["archived_policy"][index]
        if saved["memory_id"] != root["original_sources"][index]["memory_id"]:
            raise ValueError("Archived RP policy does not align with the focal source")
        native = dict(row["native"])
        applied = []
        for method, arm in arms.items():
            use_new = saved["policy"] == "B" and focal_level(row, method) == "A"
            native[arm] = native[method if use_new else run.RP]
            if use_new:
                triggers[method] += 1
                triggers[method + "/author_" + row["labels"][index]] += 1
                source_groups[method].add(row["group"])
                applied.append(method)
        if applied:
            cases.append({"uid": uid, "source_group": row["group"], "methods_triggered": applied,
                          "author_focal_label": row["labels"][index]})
        replayed.append({**row, "native": native})
    return arms, replayed, {"triggers": triggers, "source_group_counts": {
        method: len(groups) for method, groups in source_groups.items()}, "triggered_cases": cases}


def soft_veto_results(frozen, rows):
    public = run.read(run.joint.prior.OUT / "FROZEN.json")
    roots = {row["uid"]: row for row in public["roots"]}
    names, replayed, diagnostics = replay_soft_veto(rows, roots)
    comparisons = {name: {comparison: {
        "match": run.v42.paired(sample, comparator, candidate),
        **{field: run.joint.parent.comparisons.grade_pair(sample, comparator, candidate, field)
           for field in run.joint.SUPPORT},
    } for comparison, comparator, candidate in (
        ("isolation_veto_vs_context_veto", names[focal.CONTEXTUAL], names[focal.ISOLATED]),
        ("isolation_veto_vs_original_rp", run.RP, names[focal.ISOLATED]),
        ("isolation_veto_vs_gate", run.GATE, names[focal.ISOLATED]),
    )} for name, sample in subsets(replayed, frozen).items()}
    return {**diagnostics, "paired_results": comparisons, "new_calls": 0,
            "interpretation": "Exploratory archived replay specified after selector results and before native scores. "
                              "Valid vetoes use the already generated same-task focal arm, including its missing "
                              "scores. Other decisions reuse the original RP answer. Costs are not reduced to Gate."}


def selector_checkpoint():
    """Reconcile current receipts and estimate Actor allocation without evaluation data."""
    frozen = run.read(run.OUT / "FROZEN.json")
    _, public, packets, jobs = run.prepare(frozen["service_reference_sha256"])
    run.probe.OUT, run.probe.RUN = run.OUT, run.RUN
    received = run.probe.stage_receipts(run.PLAN)
    exact = {record["request_sha256"]: (record, raw) for record, raw in received.values() if record}
    logical_status, focal_policies = Counter(), {}
    for uid, method, wire in jobs:
        digest = sha(wire)
        if digest != frozen["selector_wires"][uid][method]:
            raise ValueError("Reconstructed selector input differs from the frozen manifest")
        if digest not in exact:
            logical_status[method + "/NO_RECEIPT"] += 1
            continue
        parsed = run.parse_selection(*exact[digest], packets[uid, method], digest)
        logical_status[method + "/" + parsed["status"]] += 1
        if "decision" in parsed:
            focal_policies[uid, method] = parsed["decision"]["policy"]
    physical = Counter(record["status"] for record, _ in exact.values())
    old_wires = {row["archived_actor_sha256"] for row in public["roots"] if row["archived"][run.RP]["answer"]}
    request_wires, classified = set(), Counter()
    for root in public["roots"]:
        uid = root["uid"]
        source = root["original_sources"][frozen["focus_index"][uid]]["memory_id"]
        levels = [focal_policies.get((uid, method)) for method in focal.METHODS]
        if all(levels):
            classified["valid_selector_pairs"] += 1
            classified["different_focal_policies"] += levels[0] != levels[1]
        for level in levels:
            if level is not None:
                request_wires.add(sha(policy_only_request(root, {source: level})))
    return {"state": run.read(run.OUT / "RUN_STATE.json")["state"],
            "physical_selector_budget": frozen["caps"][run.PLAN], "physical_selector_status": physical,
            "logical_selector_status": logical_status, "current_pairs": classified,
            "actor_wires_from_available_selectors": {"total": len(request_wires),
                                                     "matched_archived_RP": len(request_wires & old_wires),
                                                     "outside_original_RP": len(request_wires - old_wires)},
            "new_calls": 0, "author_data_used": False}


def checked_rows():
    state = run.read(run.OUT / "RUN_STATE.json")
    if state["state"] != "COMPLETE":
        raise ValueError(f"Focal experiment has not settled: {state['state']}")
    frozen = run.read(run.OUT / "FROZEN.json")
    settled = run.read(run.OUT / "SETTLED.json")
    rows, ledger = settled["rows"], settled["ledger"]
    roots = {row["uid"] for row in rows}
    selector = {digest for wires in frozen["selector_wires"].values() for digest in wires.values()}
    keys = {(record["unit"]["stage"], record["request_sha256"]) for record in ledger}
    if (len(roots) != len(rows) or len(rows) != frozen["assigned"] or roots != frozen["selector_wires"].keys()
            or len(ledger) != len(keys) or len(ledger) != state["physical_requests"]
            or {digest for stage, digest in keys if stage == run.PLAN} != selector):
        raise ValueError("Roster or physical requests disagree with the freeze")
    if any(record["status"] == "PENDING_DELIVERY_UNKNOWN" for record in ledger):
        raise ValueError("Pending deliveries must settle before interpretation")
    return frozen, rows, ledger


def focal_level(row, method):
    return row["selector"][method].get("decision", {}).get("policy")


def match(row, method):
    return row["native"][method]["fields"].get("match")


def trace_changes(rows):
    left, right = focal.METHODS
    totals, strata = Counter(), defaultdict(Counter)
    cases = {}
    for row in rows:
        uid = row["uid"]
        a, b = (focal_level(row, arm) for arm in focal.METHODS)
        if a is None or b is None:
            totals["selector_pair_missing"] += 1
            continue
        label = row["labels"][row["focus_index"]]
        status = ("same_policy" if a == b else "focal_correction" if b == label
                  else "focal_regression" if a == label else "both_wrong_with_different_levels")
        answers = [row["actor"][arm] for arm in focal.METHODS]
        wires = [actor.get("request_sha256") for actor in answers]
        if (a == b) != (wires[0] == wires[1] and wires[0] is not None):
            raise ValueError("Focal policy does not explain the paired Actor request")
        arrived = all(actor["status"] in ("OK", "REUSED_RP_ACTOR") and actor.get("answer") for actor in answers)
        same_answer = arrived and answers[0]["answer"] == answers[1]["answer"]
        if a == b and arrived and not same_answer:
            raise ValueError("An identical Actor request produced inconsistent answers")
        x, y = (match(row, arm) for arm in focal.METHODS)
        delta = y["matched"] - x["matched"] if x and y else None
        if same_answer and delta:
            raise ValueError("An identical answer received different frozen Match")
        if x and y and (x["positions"] != row["positions"] or y["positions"] != row["positions"]):
            raise ValueError("Native pair does not align with the author position count")
        facts = {"roots": 1, "both_answers": arrived, "same_answer": same_answer,
                 "native_pairs": delta is not None, "native_net_positions": delta or 0,
                 "native_wins": delta is not None and delta > 0,
                 "native_losses": delta is not None and delta < 0,
                 "native_ties": delta == 0}
        strata["all", status].update(facts)
        strata[label, status].update(facts)
        totals[status] += 1
        if a != b:
            cases[uid] = {"baseline_focal_policy": a, "isolated_focal_policy": b, "author_focal_label": label,
                          "selector_disposition": status, "shared_answer": same_answer,
                          "native_match_delta_positions": delta, "source_group": row["group"],
                          "actor_wires": wires}
    return {"counts": totals, "mechanism_by_author_focal_label": {
        f"{label}/{event}": facts for (label, event), facts in strata.items()}, "changed_policy_cases": cases}


def generation_cost(rows, ledger):
    records = {(record["unit"]["stage"], record["request_sha256"]): record for record in ledger}
    actor_records = {digest: rec for (stage, digest), rec in records.items() if stage == run.ACTOR}
    for suffix in ("rp_policy_override_rpeval_v43", "decision_edit_rpeval", "joint_preference_planning_rpeval_v1"):
        path = run.OUT.with_name(suffix) / f"{run.ACTOR}_EXACT.json"
        if path.exists():
            for digest, (rec, _) in run.read(path).items():
                if rec["request_sha256"] != digest:
                    raise ValueError("Unexpected cost receipt hash")
                if rec["status"] == "OK" and digest not in actor_records:
                    actor_records[digest] = rec
    old_plan = run.read(run.joint.prior.formal.OUT / "PLAN.json")
    public = run.read(run.joint.prior.OUT / "FROZEN.json")
    roots = {root["uid"]: root for root in public["roots"]}
    data = []
    modes = (*focal.METHODS, run.RP, run.GATE)

    def measured(record):
        return numeric_cost(record["usage"]) if record and record["status"] == "OK" else None

    for row in rows:
        if not all(match(row, method) for method in modes):
            continue
        root, costs = roots[row["uid"]], {}
        original_actor = run.joint.prior.receipt(old_plan, row["uid"], run.RP, run.ACTOR)
        base_actor = numeric_cost(original_actor["response"].get("usage")) if original_actor else None
        for method in (run.GATE, run.RP):
            old = old_cost(old_plan, root, method)
            if old is not None:
                costs[method] = old
        if base_actor is not None and run.RP in costs:
            prefix = costs[run.RP] - base_actor
            for arm in focal.METHODS:
                digest = row["selector"][arm]["request_sha256"]
                added = measured(records.get((run.PLAN, digest)))
                actor = row["actor"][arm]
                revised = base_actor if actor["request_sha256"] == root["archived_actor_sha256"] else measured(
                    actor_records.get(actor["request_sha256"]))
                if added is not None and revised is not None:
                    costs[arm] = prefix + added + revised
        data.append({"group": row["group"], "usage": costs})
    return {"candidate_archived_policy_based": True,
            "logical_calls": {run.RP: len(run.joint.prior.formal.STAGES[run.RP]),
                              run.GATE: len(run.joint.prior.formal.STAGES[run.GATE]),
                              **dict.fromkeys(focal.METHODS, len(run.joint.prior.formal.STAGES[run.RP]) + 1)},
            "common_full_generation_cost_excluding_judge": profile(data, modes)}


def audit():
    frozen, rows, ledger = checked_rows()
    return {"assigned": len(rows), "independent_confirmation": False,
            "settled_sha256": sha((run.OUT / "SETTLED.json").read_bytes()),
            "physical_requests": usage(ledger), "cost": generation_cost(rows, ledger),
            "panels": {name: trace_changes(panel) for name, panel in subsets(rows, frozen).items()},
            "native_results": run.read(run.OUT / "RESULTS.json")["screen"],
            "exploratory_soft_veto": soft_veto_results(frozen, rows), "new_calls": 0}


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--verify", action="store_true")
    actions.add_argument("--selector-checkpoint", action="store_true")
    options = parser.parse_args()
    if options.verify:
        checked_rows()
        result = {"verified": replay_readonly(run), "new_calls": 0}
    elif options.selector_checkpoint:
        result = selector_checkpoint()
    else:
        result = audit()
    print(json.dumps(result, ensure_ascii=False, indent=2))
