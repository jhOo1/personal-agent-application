"""Verify archived response routing, matched costs, and mark coverage."""
from argparse import ArgumentParser
from collections import Counter
import json
from unittest.mock import patch

from deployment_cost import numeric_cost, old_cost, profile
import run_grounded_feasibility as run


def live():
    spec, _, _, _, _ = run.prepare()
    run.probe.OUT, run.probe.RUN = run.OUT, run.RUN
    return {stage: Counter(record["status"] if record else "UNISSUED"
                           for record, _ in run.probe.stage_receipts(stage).values())
            for stage in spec["caps"]}


def behavior(rows):
    method = run.method
    counts, witnesses, transitions = Counter(), Counter(), Counter()
    changes, changed_options, excluded_without_conflict = [], [], []
    for row in rows:
        ex = row["execution"]
        answers = ex["answers"]
        layer = "primary" if row["primary"] else "regression"
        counts[f"{layer}/histories"] += 1
        if any(arm not in answers for arm in method.MODES):
            continue
        counts[f"{layer}/compiled_histories"] += 1
        for base, candidate in ((method.DIRECT, method.STATUS), (method.STATUS, method.ANCHORED)):
            if answers[base]["answer"] != answers[candidate]["answer"]:
                counts[f"{layer}/{base}_to_{candidate}/answer_changed"] += 1
        counts[f"{layer}/guards_without_matrix"] += sum(
            decision.get("guard") is not None and slot not in ex.get("matrices", {})
            for slot, decision in ex.get("policy", {}).items())
        for slot, matrix in ex.get("matrices", {}).items():
            traces = {arm: answers[arm]["decisions"][slot]
                      for arm in (method.DIRECT, method.STATUS, method.ANCHORED)}
            proof_log = traces[method.ANCHORED]
            if any(t["excluded"] != proof_log["excluded"] for t in traces.values()):
                raise ValueError("Shared upstream exclusion has changed")
            for option in proof_log["excluded"]:
                checks = matrix["entries"].get(option, {}).get("checks", {})
                exact_conflicts = [check for check in checks.values()
                                   if check["predicted"] == "CONFLICT" and check["exact_witness"]]
                counts[f"{layer}/upstream_excluded_options"] += 1
                if not exact_conflicts:
                    excluded_without_conflict.append({
                        "uid": row["uid"], "slot": slot, "primary": row["primary"],
                        "condition": row["condition"], "option": option,
                        "properties": matrix["conditions"], "checks": checks,
                    })
            for option in proof_log["routed"]["DIRECT"]:
                support_checks = matrix["entries"][option]["checks"]
                if (len(support_checks) != len(matrix["conditions"])
                        or not all(w["predicted"] == "SUPPORTED" and w["exact_witness"]
                                   for w in support_checks.values())):
                    raise ValueError("Direct option lacks supported witnesses for each condition")
            counts[f"{layer}/matrix_slots"] += 1
            for arm, trace in traces.items():
                counts[f"{layer}/{arm}/displayed"] += len(trace["shown"])
                counts[f"{layer}/{arm}/direct"] += len(set(trace["shown"]) & set(trace["routed"]["DIRECT"]))
                counts[f"{layer}/{arm}/empty"] += not trace["shown"]
                for option, item in matrix["entries"].items():
                    if option not in trace["shown"]:
                        continue
                    if option not in trace["routed"]["DIRECT"]:
                        continue
                    support = item["checks"]
                    if len(support) < len(matrix["conditions"]) or any(
                            w["predicted"] != "SUPPORTED" or not w["exact_witness"] for w in support.values()):
                        counts[f"{layer}/{arm}/direct_with_missing_witness"] += 1
            before, after = (traces[arm] for arm in (method.STATUS, method.ANCHORED))
            routes = {
                arm: {option: kind for kind, options in trace["routed"].items() for option in options}
                for arm, trace in traces.items()
            }
            for option, old_kind in routes[method.STATUS].items():
                entry = matrix["entries"].get(option, {})
                checks = entry.get("checks", {})
                for check in checks.values():
                    location = check["location"] if check["location"] in ("TASK", "OPTION") else "NONE"
                    exact = "exact" if check["exact_witness"] else "unverified"
                    witnesses[f"{layer}/{check['predicted']}/{location}/{exact}"] += 1
                witnesses[f"{layer}/missing_check"] += len(matrix["conditions"]) - len(checks)
                for base, candidate in ((method.DIRECT, method.STATUS), (method.STATUS, method.ANCHORED)):
                    base_kind, new_kind = routes[base][option], routes[candidate][option]
                    was_shown = option in traces[base]["shown"]
                    is_shown = option in traces[candidate]["shown"]
                    transitions[f"{layer}/{base}_to_{candidate}/{base_kind}_to_{new_kind}"] += 1
                    if base_kind != new_kind or was_shown != is_shown:
                        changed_options.append({
                            "uid": row["uid"], "slot": slot, "primary": row["primary"],
                            "condition": row["condition"], "comparison": [base, candidate],
                            "option": option, "routes": [base_kind, new_kind],
                            "shown": [was_shown, is_shown],
                            "properties": matrix["conditions"], "checks": checks,
                        })
            if before != after:
                counts[f"{layer}/changed_by_anchoring"] += 1
                changes.append({"uid": row["uid"], "slot": slot, "primary": row["primary"],
                                "condition": row["condition"], "routing": traces})
    return {"counts": counts, "witness_counts": witnesses, "route_transitions": transitions,
            "anchoring_changes": changes, "changed_options": changed_options,
            "upstream_excluded_without_exact_conflict": excluded_without_conflict}


def observed_rows(inputs):
    cached = run.read(run.prior.OUT / f"{run.TASK}_EXACT.json")
    run.probe.OUT, run.probe.RUN = run.OUT, run.RUN
    returned = {stage: run.probe.stage_receipts(stage) for stage in (run.TASK, run.POLICY)}
    if not returned[run.POLICY]:
        raise ValueError("Wait for the decision request manifest")

    def snapshot(stage, work):
        outputs = {}
        for uid, arm, wire in work:
            digest = run.sha(wire)
            rec, text = (cached[digest] if stage == run.TASK and digest in cached
                         else returned[stage][uid, arm])
            outputs[uid, arm] = (rec, text) if text else (
                {"status": "RESULT_UNAVAILABLE", "request_sha256": digest}, None)
        return outputs

    return run.generate(inputs, snapshot)


def observed():
    rows = observed_rows(run.prepare())
    count = Counter(row["execution"].get("policy_state", row["execution"]["task_state"])
                    for row in rows.values())
    return {"partial": True, "states": count, **behavior(rows.values()), "new_model_requests": 0}


def scope():
    """Expose guarded answer sections alongside prose that bypassed the guard."""
    inputs = run.prepare()
    _, _, _, roots, _ = inputs
    settled = run.OUT / "SETTLED.json"
    rows = run.read(settled)["rows"] if settled.exists() else observed_rows(inputs).values()
    cases = []
    for row in rows:
        ex = row["execution"]
        guards = {slot: decision["guard"] for slot, decision in ex.get("policy", {}).items()
                  if decision.get("guard") is not None}
        if not guards:
            continue
        root = roots[row["uid"]]
        cases.append({
            "uid": row["uid"], "group": row["group"], "primary": row["primary"],
            "public_task": root["public_task"], "active_guards": guards,
            "unchecked_prose": {slot: block for slot, block in ex["blocks"].items()
                                if block["kind"] == "CONTENT"},
            "guarded_choices": {slot: ex["blocks"][slot] for slot in guards},
            "emitted": {arm: item["answer"] for arm, item in ex["answers"].items()},
            "archive": {arm: root["archived"][arm] for arm in run.BASELINES if arm in root["archived"]},
            "new_native": {arm: row["native"][arm] for arm in run.method.MODES if arm in row["native"]},
        })
    return {"settled": settled.exists(), "cases": cases, "new_model_requests": 0}


def cost(rows, ledger, roots):
    reference = run.read(run.prior.parent.prior.parent.joint.prior.formal.OUT / "PLAN.json")
    task_cache = run.read(run.prior.OUT / f"{run.TASK}_EXACT.json")
    index = {(rec["unit"]["stage"], rec["request_sha256"]): rec for rec in ledger}
    index.update({(run.TASK, digest): value[0] for digest, value in task_cache.items()})
    modes = (run.method.DIRECT, run.method.ANCHORED, *run.BASELINES)
    data, invocations = [], Counter()
    for row in rows:
        if not row["primary"]:
            continue
        ex, amounts = row["execution"], {}
        receipts = [index[name, ex[key]] for name, key in (
            (run.TASK, "task_sha256"), (run.POLICY, "policy_sha256")) if key in ex]
        sizes = [numeric_cost(rec["usage"]) for rec in receipts if rec["status"] == "OK"]
        for arm in modes[:2]:
            if len(sizes) == len(receipts) and all(size is not None for size in sizes) and arm in ex["answers"]:
                amounts[arm] = sum(sizes, Counter())
                invocations[f"{arm}/{len(receipts)}"] += 1
        for arm in run.BASELINES:
            cached = old_cost(reference, roots[row["uid"]], arm)
            if cached is not None:
                amounts[arm] = cached
        grades = {arm: row["native"][arm]["fields"]["match"]["matched"]
                  for arm in modes if "match" in row["native"][arm]["fields"]}
        if all(arm in grades and arm in amounts for arm in modes):
            data.append({"group": row["group"], "usage": amounts, "marks": grades, "positions": row["positions"]})
    return {**profile(data, modes), "positions": sum(row["positions"] for row in data),
            "matched": {arm: sum(row["marks"][arm] for row in data) for arm in modes},
            "logical_generation_calls": invocations, "excludes_judge_usage": True}


def verify():
    inputs = run.prepare()
    spec, _, _, roots, _ = inputs
    state = run.read(run.OUT / "RUN_STATE.json")
    if state["state"] != "COMPLETE":
        raise ValueError("Expected completed settlement")
    checked = []

    def confirm(path, rebuilt):
        if run.read(path) != json.loads(json.dumps(rebuilt)):
            raise ValueError(f"Replay differs from {path.name}")
        checked.append(path.name)

    with patch.object(run.probe, "freeze", confirm):
        run.execute("report", inputs)
    settled = run.read(run.OUT / "SETTLED.json")
    ledger = [record for name in spec["caps"] for record, _ in run.probe.stage_receipts(name).values()]
    keys = {(row["unit"]["stage"], row["request_sha256"]) for row in ledger}
    if ledger != settled["ledger"] or not len(ledger) == state["physical_requests"] == len(keys):
        raise ValueError("Ledger mismatch or duplicate physical requests")
    rows = {row["uid"]: row for row in settled["rows"]}
    for pair in spec["pairs"]:
        a, b = (rows[pair[key]]["execution"] for key in run.CONDITIONS)
        if (a["task_sha256"], a["blocks"]) != (b["task_sha256"], b["blocks"]):
            raise ValueError("Shared task catalog differs between the two histories")
    for row in rows.values():
        answers = row["execution"]["answers"]
        seen = {}
        for arm, item in answers.items():
            if seen.setdefault(item["answer"], row["native"][arm]["fields"]) != row["native"][arm]["fields"]:
                raise ValueError("Identical answers have unequal native grades")
    return {"verified_files": checked, "physical_requests": len(keys),
            "behavior": behavior(rows.values()), "primary_cost": cost(rows.values(), ledger, roots),
            "new_model_requests": 0}


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("live", "verify", "behavior", "scope"))
    args = parser.parse_args()
    check = {"live": live, "verify": verify, "behavior": observed, "scope": scope}[args.mode]
    print(json.dumps(check(), ensure_ascii=False, indent=2))
