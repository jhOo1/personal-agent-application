"""Check evidence parity, compiled adjustments and cost without dispatching requests."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
import json

from deployment_cost import numeric_cost, old_cost, profile
from qamc.common import parse_object, sha

import decision_realization as method
import run_decision_realization as run
from settle_joint_planning import replay_readonly, usage


def selector_checkpoint():
    """Inspect accepted and rejected uses without opening scoring inputs."""
    frozen = run.read(run.OUT / "FROZEN.json")
    _, public, _ = run.prepare(frozen["service_reference_sha256"])
    run.probe.OUT, run.probe.RUN = run.OUT, run.RUN
    observed = run.probe.stage_receipts(run.PLAN)
    stored = {record["request_sha256"]: (record, raw) for record, raw in observed.values() if record}
    logical, uses, rejects = Counter(), Counter(), Counter()
    for root in public["roots"]:
        digest = frozen["selector_wires"][root["uid"]]
        rec, raw = stored.get(digest, (None, None))
        if rec is None:
            logical["NO_RECEIPT"] += 1
        elif rec["status"] != "OK":
            logical[rec["status"]] += 1
        else:
            try:
                edges, rejected = method.compile_uses(root, raw)
            except (KeyError, TypeError, ValueError) as error:
                logical["INVALID_USE_CONTRACT"] += 1
                rejects[str(error)] += 1
                continue
            keys = [edge["use"] for edge in edges]
            logical["SEGMENTED" if "OPTIONAL" in keys else "SHARED_WITH_EVIDENCE" if keys else "SHARED_TASK_ONLY"] += 1
            uses.update(keys)
            rejects.update(row["reason"] for row in rejected)
    return {"state": run.read(run.OUT / "RUN_STATE.json")["state"],
            "physical_selector_status": Counter(record["status"] for record, _ in stored.values()),
            "logical_routes": logical, "accepted_uses": uses, "rejected_uses_or_rows": rejects, "new_calls": 0}


def checked():
    state = run.read(run.OUT / "RUN_STATE.json")
    if state["state"] != "COMPLETE":
        raise ValueError(f"Expected a terminal realization run, got {state['state']}")
    frozen = run.read(run.OUT / "FROZEN.json")
    settled = run.read(run.OUT / "SETTLED.json")
    rows, ledger = settled["rows"], settled["ledger"]
    digest_keys = {(record["unit"]["stage"], record["request_sha256"]) for record in ledger}
    if (len(rows) != frozen["assigned"] or len(rows) != len({row["uid"] for row in rows})
            or {row["uid"] for row in rows} != frozen["selector_wires"].keys()
            or len(ledger) != len(digest_keys) or len(ledger) != state["physical_requests"]
            or {digest for stage, digest in digest_keys if stage == run.PLAN} != set(frozen["selector_wires"].values())
            or any(record["status"] == "PENDING_DELIVERY_UNKNOWN" for record in ledger)):
        raise ValueError("Frozen tasks, final ledger and terminal state disagree")
    return frozen, rows, ledger


def reconciling_actors(rows, roots):
    totals, source_effects, adjustment_effects, route_groups = (
        Counter(), defaultdict(Counter), Counter(), defaultdict(set),
    )
    cases = {}
    left, right = method.METHODS
    for row in rows:
        root = roots[row["uid"]]
        source_ids = [source["memory_id"] for source in root["original_sources"]]
        labels = dict(zip(source_ids, row["labels"], strict=True))
        trace = row["selection"]
        totals["assigned"] += 1
        if trace["status"] != "OK":
            totals[trace["status"]] += 1
            continue
        licenses, route = trace["uses"], trace["route"]
        cohort = "SEGMENTED" if route == "SEGMENTED" else "SHARED_EVIDENCE" if licenses else "TASK_ONLY"
        totals[cohort] += 1
        route_groups[cohort].add(row["group"])
        methods = method.METHODS if cohort == "SEGMENTED" else (left, left)
        wires = [method.actor(root, licenses, arm) if licenses else run.joint.prior.task_only_request(root)
                 for arm in methods]
        if (wires[0]["messages"][1:] != wires[1]["messages"][1:]
                or (wires[0] != wires[1]) != (cohort == "SEGMENTED")):
            raise ValueError("Realization arms did not share identical task and evidence")
        a, b = (row["actor"][arm] for arm in method.METHODS)
        if [a["request_sha256"], b["request_sha256"]] != [sha(wire) for wire in wires]:
            raise ValueError("Settled answers are not bound to the reconstructed requests")
        if cohort != "SEGMENTED" and (a["answer"], a["status"]) != (b["answer"], b["status"]):
            raise ValueError("No-treatment Actor diverged")
        selected = dict.fromkeys(source_ids, "UNLICENSED")
        for edge in licenses:
            selected[edge["memory_id"]] = edge["use"]
        for source, label in labels.items():
            source_effects[cohort][label + "/" + selected[source]] += 1
            source_effects["all_valid_selectors"][label + "/" + selected[source]] += 1
        if cohort != "SEGMENTED" or b["status"] != "OK":
            continue
        rebuilt, added, rejected = method.compile_answer(b["raw"], licenses, right)
        if (rebuilt, added, rejected) != (b["answer"], b["appended_sources"], b["rejected_adjustments"]):
            raise ValueError("Compiled answer does not match the stored text and adjustment audit")
        totals["segmented_usable"] += 1
        totals["segmented_with_appended_text"] += bool(added)
        totals["segmented_with_rejected_adjustment"] += bool(rejected)
        adjustment_effects.update(labels[mid] for mid in added)
        main = parse_object(b["raw"])["main_answer"]
        x, y = (row["native"][arm]["fields"].get("match") for arm in method.METHODS)
        cases[row["uid"]] = {"source_group": row["group"], "appended_author_labels": [labels[mid] for mid in added],
                             "main_answer_sha256": sha(main), "final_answer_sha256": sha(rebuilt),
                             "native_match_delta_positions": y["matched"] - x["matched"] if x and y else None}
    return {"routes": totals, "groups_by_route": {route: len(groups) for route, groups in route_groups.items()},
            "selected_uses_by_author_label": source_effects, "appended_sources_by_author_label": adjustment_effects,
            "segmented_cases": cases}


def deployment_cost(rows, ledger, roots):
    # Task-only reuse follows the pinned runner's cache priority.
    archive = run.read(run.joint.prior.OUT / "FROZEN.json")
    prior_actors = run.v42.old_receipts(archive)[run.ACTOR]
    actors = {digest: record for digest, (record, _) in prior_actors.items()}
    previous = (run.joint.parent.OUT, run.joint.OUT, run.OUT.with_name("rp_seed_minimal_revision_rpeval_v1"),
                run.OUT.with_name("focal_memory_rpeval_v1"))
    for experiment in previous:
        exact = experiment / f"{run.ACTOR}_EXACT.json"
        if exact.exists():
            for digest, (record, _) in run.read(exact).items():
                if digest != record["request_sha256"]:
                    raise ValueError("Archived Actor cost has the wrong request hash")
                actors.setdefault(digest, record)
    selector = {}
    for record in ledger:
        stage, digest = record["unit"]["stage"], record["request_sha256"]
        if stage == run.ACTOR:
            actors[digest] = record
        elif stage == run.PLAN:
            selector[digest] = record
    modes = (*method.METHODS, run.GATE, run.RP)
    official = run.read(run.joint.prior.formal.OUT / "PLAN.json")
    data = []

    def measure(mapping, digest):
        record = mapping.get(digest)
        return numeric_cost(record["usage"]) if record and record["status"] == "OK" else None

    for row in rows:
        if not all(row["native"][name]["fields"].get("match") for name in modes):
            continue
        root = roots[row["uid"]]
        costs = {name: old_cost(official, root, name) for name in (run.GATE, run.RP)}
        costs = {name: value for name, value in costs.items() if value is not None}
        shared = measure(selector, row["selection"]["request_sha256"])
        for arm in method.METHODS:
            rendered = measure(actors, row["actor"][arm].get("request_sha256"))
            if shared is not None and rendered is not None:
                costs[arm] = shared + rendered
        data.append({"group": row["group"], "usage": costs})
    stages = run.joint.prior.formal.STAGES
    return {"calls_before_cache": {**dict.fromkeys(method.METHODS, 2),
                                    run.GATE: len(stages[run.GATE]), run.RP: len(stages[run.RP])},
            "generation_only_on_common_scored_roots": profile(data, modes)}


def audit():
    frozen, rows, ledger = checked()
    public = run.read(run.joint.prior.OUT / "FROZEN.json")
    roots = {root["uid"]: root for root in public["roots"]}
    return {"assigned": frozen["assigned"], "independent_confirmation": False, "model_calls": 0,
            "settled_sha256": sha((run.OUT / "SETTLED.json").read_bytes()),
            "physical": usage(ledger), "realization": reconciling_actors(rows, roots),
            "deployment_cost": deployment_cost(rows, ledger, roots)}


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--verify", action="store_true")
    group.add_argument("--selector-checkpoint", action="store_true")
    args = parser.parse_args()
    if args.verify:
        checked()
        result = {"verified": replay_readonly(run), "model_calls": 0}
    elif args.selector_checkpoint:
        result = selector_checkpoint()
    else:
        result = audit()
    print(json.dumps(result, ensure_ascii=False, indent=2))
