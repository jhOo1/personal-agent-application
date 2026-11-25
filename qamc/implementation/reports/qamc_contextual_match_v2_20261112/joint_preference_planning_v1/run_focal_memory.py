"""Matched selector-context intervention with the original RP Actor and native grading."""
from argparse import ArgumentParser
from collections import Counter
from pathlib import Path
import json

from qamc.common import sha, token_estimate, canonical

from audit_archived_policy_edits import policy_only_request
import focal_memory as focal
import run_joint_planning as joint


OUT = joint.OUT.with_name("focal_memory_rpeval_v1")
RUN = joint.RUN.with_name(OUT.name)
PLAN, ACTOR, JUDGE = joint.PLAN, joint.ACTOR, joint.JUDGE
RP, GATE, RULE = joint.parent.comparisons.RP, joint.parent.comparisons.GATE, joint.parent.comparisons.RULE
read, probe, v42 = joint.read, joint.probe, joint.v42


def prepare(reference):
    archive_path = joint.prior.OUT / "FROZEN.json"
    parent_path = joint.OUT / "FROZEN.json"
    score_path = joint.parent.OUT / "SETTLED.json"
    archive, parent = read(archive_path), read(parent_path)
    archive_key = str(archive_path.relative_to(joint.HERE.parent.parent.parent))
    if sha(archive_path.read_bytes()) != parent["hashes"][archive_key]:
        raise ValueError("The exposed candidate archive changed")
    roots = archive["roots"]
    roster = [root["uid"] for root in roots]
    if len(roster) != len(set(roster)) or set(roster) != parent["planner_wires_sha256"].keys():
        raise ValueError("Focal intervention requires the existing exposed cohort")
    foci, pairs = focal.choose_foci(roots)
    packets, jobs = {}, []
    for root in roots:
        uid = root["uid"]
        methods = focal.METHODS if int(sha(uid)[0], 16) % 2 else focal.METHODS[::-1]
        for method in methods:
            packet = focal.packet(root, foci[uid], method)
            packets[uid, method] = packet
            jobs.append((uid, method, focal.request(packet)))
        if (sha(policy_only_request(root, {})) != root["archived_actor_sha256"]
                or root["archived"][RP]["actor_sha256"] != root["archived_actor_sha256"]):
            raise ValueError("Archived RP Actor identity changed")
    wire_hashes = {(uid, method): sha(wire) for uid, method, wire in jobs}
    for pair in pairs:
        a, b = pair["uids"]
        if (wire_hashes[a, focal.ISOLATED] != wire_hashes[b, focal.ISOLATED]
                or wire_hashes[a, focal.CONTEXTUAL] == wire_hashes[b, focal.CONTEXTUAL]):
            raise ValueError("Natural cross-context pair does not isolate the same task and source")
    estimated = max(token_estimate(canonical(wire["messages"])) for _, _, wire in jobs)
    if estimated > 32768:
        raise ValueError("Focal predictor input exceeds the preflight context bound")
    paths = (Path(__file__), Path(focal.__file__), joint.HERE / "FOCAL_PROTOCOL.md",
             archive_path, parent_path, score_path, joint.prior.formal.OUT / "PLAN.json",
             Path(joint.prior.formal.__file__), Path(joint.v42.__file__),
             Path(joint.prior.__file__), Path(joint.parent.__file__),
             Path(joint.planning.__file__), Path(joint.v42.__file__).with_name("audit_archived_policy_edits.py"))
    config = {
        "assigned": len(roster), "source_groups": len({r["group"] for r in roots}),
        "caps": {PLAN: len(set(wire_hashes.values())), ACTOR: len(jobs), JUDGE: len(jobs)},
        "independent_confirmation": False, "max_estimated_selector_input": estimated,
        "focus_index": foci, "natural_pairs": pairs, "diagnostic_source_groups": parent["diagnostic_source_groups"],
        "selector_wires": {uid: {method: wire_hashes[uid, method] for method in focal.METHODS} for uid in roster},
        "service_reference_sha256": reference,
        "input_hashes": {"/".join(path.parts[-2:]): sha(path.read_bytes()) for path in paths},
        "thresholds": {"coverage": 0.9, "mixed_match_margin": 0.02, "harm_per_answer": 0.05},
    }
    return config, archive, packets, jobs


def parse_selection(receipt, raw, packet, digest):
    if receipt["request_sha256"] != digest:
        raise ValueError("Selector response is bound to a different request")
    result = {"status": receipt["status"], "request_sha256": digest, "raw": raw}
    if result["status"] == "OK":
        try:
            result["decision"] = focal.decision(packet, raw)
        except (KeyError, TypeError, ValueError) as error:
            result.update(status="INVALID_FOCAL_CONTRACT", error=str(error))
    return result


def evaluate(inputs, stage):
    config, archive, packets, jobs = inputs
    roots = archive["roots"]
    received = stage(PLAN, jobs)
    selections = {(uid, method): parse_selection(*received[uid, method], packets[uid, method], sha(wire))
                  for uid, method, wire in jobs}
    original_by_hash = {root["archived_actor_sha256"]: root["archived"][RP]["answer"] for root in roots}
    outputs, actions = {}, []
    for root in roots:
        uid = root["uid"]
        source_id = root["original_sources"][config["focus_index"][uid]]["memory_id"]
        for method in focal.METHODS:
            key = (uid, method)
            prediction = selections[key].get("decision")
            if prediction is None:
                outputs[key] = {"status": "NO_VALID_SELECTOR", "answer": None}
                continue
            wire = policy_only_request(root, {source_id: prediction["policy"]})
            digest = sha(wire)
            if original_by_hash.get(digest):
                outputs[key] = {"status": "REUSED_RP_ACTOR", "answer": original_by_hash[digest],
                                "request_sha256": digest}
            else:
                actions.append((uid, method, wire))
    actors = stage(ACTOR, actions)
    for uid, method, wire in actions:
        receipt, answer = actors[uid, method]
        digest = sha(wire)
        if receipt["request_sha256"] != digest:
            raise ValueError("Actor response is bound to a different request")
        outputs[uid, method] = {"status": receipt["status"], "answer": answer, "request_sha256": digest}

    # Generation only consults public tasks, memory, predictions and exact cached answers.
    formal = read(joint.prior.formal.OUT / "PLAN.json")
    cases = joint.prior.author_cases(formal)
    baseline = {row["uid"]: row for row in read(joint.parent.OUT / "SETTLED.json")["rows"]}
    grades, native = [], {}
    for root in roots:
        uid = root["uid"]
        for method in focal.METHODS:
            key = uid, method
            actor = outputs[key]
            if actor["status"] not in ("OK", "REUSED_RP_ACTOR") or not actor["answer"]:
                native[key] = {"fields": {}, "status": actor["status"]}
                continue
            equal = next((m for m, saved in root["archived"].items()
                          if saved["answer"] == actor["answer"] and saved["raw_judge"] is not None), None)
            if equal is not None:
                score = baseline[uid]["native"][equal]
                if score["raw"] != root["archived"][equal]["raw_judge"]:
                    raise ValueError("Exact-answer score disagrees with the original rubric receipt")
                native[key] = {**score, "reuse": equal}
            else:
                grades.append((uid, method, joint.parent.grade_request(formal, cases[uid], actor["answer"])))
    receipts = stage(JUDGE, grades)
    for uid, method, wire in grades:
        receipt, raw = receipts[uid, method]
        if receipt["request_sha256"] != sha(wire):
            raise ValueError("Judge response is bound to a different answer")
        native[uid, method] = joint.parent.parse_grade(receipt, raw, baseline[uid]["positions"])

    rows = []
    for root in roots:
        uid = root["uid"]
        old = baseline[uid]
        if old["group"] != root["group"] or old["positions"] != len(root["original_sources"]):
            raise ValueError("The positions or source group differ from the exposed archive")
        rows.append({**{key: old[key] for key in ("uid", "group", "positions", "labels", "less_exposed")},
                     "focus_index": config["focus_index"][uid],
                     "selector": {m: selections[uid, m] for m in focal.METHODS},
                     "actor": {m: outputs[uid, m] for m in focal.METHODS},
                     "native": {**old["native"], **{m: native[uid, m] for m in focal.METHODS}}})
    return rows


def predictions(config, rows):
    by_uid = {row["uid"]: row for row in rows}

    def level(row, method):
        return row["selector"][method].get("decision", {}).get("policy")

    available = [row for row in rows if all(level(row, m) for m in focal.METHODS)]
    cm = {method: Counter(row["labels"][row["focus_index"]] + "→" + level(row, method)
                          for row in available) for method in focal.METHODS}
    paired = Counter()
    for pair in config["natural_pairs"]:
        a, b = (by_uid[uid] for uid in pair["uids"])
        levels = {m: (level(a, m), level(b, m)) for m in focal.METHODS}
        if not all(v for cells in levels.values() for v in cells):
            continue
        if levels[focal.ISOLATED][0] != levels[focal.ISOLATED][1]:
            raise ValueError("One exact isolated receipt produced two policies")
        paired["valid"] += 1
        flip = levels[focal.CONTEXTUAL][0] != levels[focal.CONTEXTUAL][1]
        paired["contextual_flip"] += flip
        paired["contextual_flip_same_index"] += flip and pair["same_index"]
        paired["contextual_flip_same_index_and_count"] += flip and pair["same_index"] and pair["same_candidate_count"]
    return {"common_roots": len(available), "focal_confusion": cm,
            "same_task_memory_cross_set": paired}


def report(config, rows, ledger):
    groups = set(config["diagnostic_source_groups"])
    panels = {"all": rows,
              "all_A": [row for row in rows if set(row["labels"]) == {"A"}],
              "contains_BC": [row for row in rows if set(row["labels"]) & {"B", "C"}],
              "contains_C": [row for row in rows if "C" in row["labels"]],
              "outside_planning_diagnostics": [row for row in rows if row["group"] not in groups]}
    metrics = {name: {other: {
        "match": v42.paired(panel, other, focal.ISOLATED),
        **{field: joint.parent.comparisons.grade_pair(panel, other, focal.ISOLATED, field)
           for field in joint.SUPPORT},
    } for other in (focal.CONTEXTUAL, GATE, RP, RULE)} for name, panel in panels.items()}
    counts = Counter(record["unit"]["stage"] for record in ledger)
    if any(count > config["caps"][stage] for stage, count in counts.items()):
        raise ValueError("Physical usage exceeded the frozen limit")
    thresholds = config["thresholds"]
    main = metrics["all"][focal.CONTEXTUAL]
    mixed = metrics["contains_BC"][focal.CONTEXTUAL]
    screen = {
        "coverage": main["match"]["valid_cases"] >= thresholds["coverage"] * len(rows),
        "match": main["match"].get("95pct_source_bootstrap", [-1])[0] > 0,
        "mixed_match": mixed["match"].get("95pct_source_bootstrap", [-1])[0] >= -thresholds["mixed_match_margin"],
        **{field: cells[field].get("95pct_source_bootstrap", [0, 1])[1] <= thresholds["harm_per_answer"]
           for field, cells in (("OPB", main), ("UPB", mixed), ("FM", mixed))},
    }
    return {"assigned": len(rows), "predictions": predictions(config, rows), "native_metrics": metrics,
            "screen": screen, "screen_pass": all(screen.values()),
            "selector_status": {m: Counter(r["selector"][m]["status"] for r in rows) for m in focal.METHODS},
            "actor_status": {m: Counter(r["actor"][m]["status"] for r in rows) for m in focal.METHODS},
            "physical_requests": counts, "transport": Counter(r["status"] for r in ledger),
            "reported_tokens": sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger),
            "requests_without_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
            "independent_confirmation": False}


def main(action):
    path = OUT / "FROZEN.json"
    if action in ("prepare", "freeze"):
        reference = "OFFLINE_PLACEHOLDER" if action == "prepare" else probe.read_reference()[1]
        frozen = prepare(reference)[0]
        if action == "freeze":
            probe.freeze(path, frozen)
        else:
            print(json.dumps(frozen, ensure_ascii=False, indent=2))
        return
    live = action == "run"
    frozen = read(path)
    design = prepare(frozen["service_reference_sha256"])
    if design[0] != frozen or (live and probe.read_reference()[1] != frozen["service_reference_sha256"]):
        raise ValueError("Frozen candidate roster or gateway fingerprint changed")
    inherited = v42.old_receipts(design[1])
    for old_out in (joint.OUT.with_name("rp_policy_override_rpeval_v43"), joint.parent.OUT, joint.OUT,
                    joint.OUT.with_name("rp_seed_minimal_revision_rpeval_v1")):
        for name in (ACTOR, JUDGE):
            exact_path = old_out / f"{name}_EXACT.json"
            if exact_path.exists():
                exact = read(exact_path)
                if any(digest != receipt["request_sha256"] for digest, (receipt, _) in exact.items()):
                    raise ValueError("An archived exact receipt is misidentified")
                for digest, entry in exact.items():
                    if digest not in inherited[name] or inherited[name][digest][0]["status"] != "OK":
                        inherited[name][digest] = entry
    probe.OUT, probe.RUN, v42.OUT = OUT, RUN, OUT

    def stage(name, jobs):
        receipts = v42.execute_stage(frozen, "main", name, jobs, inherited[name], live)
        if any(record["status"] == "PENDING_DELIVERY_UNKNOWN" for record, _ in receipts.values()):
            raise RuntimeError(f"{name}: retained an indeterminate dispatch")
        return receipts

    state = OUT / "RUN_STATE.json"
    if live:
        probe.atomic_json(state, {"state": "RUNNING", "caps": frozen["caps"]})
    try:
        rows = evaluate(design, stage)
        ledger = [record for name in (PLAN, ACTOR, JUDGE) for record, _ in probe.stage_receipts(name).values()]
        probe.freeze(OUT / "SETTLED.json", {"rows": rows, "ledger": ledger})
        probe.freeze(OUT / "RESULTS.json", report(frozen, rows, ledger))
    except (OSError, RuntimeError, ValueError) as error:
        if live:
            probe.atomic_json(state, {"state": "STOPPED", "error": str(error)})
        raise
    if live:
        probe.atomic_json(state, {"state": "COMPLETE", "physical_requests": len(ledger)})


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "freeze", "run", "report"))
    arg = parser.parse_args().action
    if arg in ("freeze", "run"):
        with probe.runner_lock(RUN / "runner.lock"):
            main(arg)
    else:
        main(arg)
