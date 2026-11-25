"""Run and settle a shared-Selector, two-call decision realization comparison."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path

from qamc.common import canonical, sha, token_estimate

import decision_realization as method
import run_joint_planning as joint
from settle_joint_planning import subsets


OUT = joint.OUT.with_name("decision_realization_rpeval_v1")
RUN = joint.RUN.with_name(OUT.name)
PLAN, ACTOR, JUDGE = joint.PLAN, joint.ACTOR, joint.JUDGE
RP, GATE, RULE = joint.parent.comparisons.RP, joint.parent.comparisons.GATE, joint.parent.comparisons.RULE
probe, read, v42 = joint.probe, joint.read, joint.v42


def prepare(reference):
    archived_file = joint.prior.OUT / "FROZEN.json"
    anchor_file = joint.OUT / "FROZEN.json"
    anchor, archive = read(anchor_file), read(archived_file)
    key = str(archived_file.relative_to(joint.HERE.parent.parent.parent))
    if sha(archived_file.read_bytes()) != anchor["hashes"][key]:
        raise ValueError("Exposed source archive changed")
    roots = archive["roots"]
    if len(roots) != 233 or {root["uid"] for root in roots} != anchor["planner_wires_sha256"].keys():
        raise ValueError("Required the same 233 exposed roots")
    jobs = [(root["uid"], "SHARED_USES", method.selector(root)) for root in roots]
    limit = max(token_estimate(canonical(wire["messages"])) for _, _, wire in jobs)
    if limit > 32768:
        raise ValueError("Selector input is outside the tested context")
    paths = (Path(__file__), Path(method.__file__), joint.HERE / "REALIZATION_PROTOCOL.md",
             archived_file, anchor_file, joint.parent.OUT / "SETTLED.json", joint.prior.formal.OUT / "PLAN.json",
             Path(joint.planning.__file__), Path(joint.parent.__file__), Path(v42.__file__),
             Path(joint.prior.__file__), Path(joint.prior.formal.__file__))
    return {
        "assigned": len(roots), "source_groups": len({root["group"] for root in roots}),
        "caps": {PLAN: len({sha(wire) for _, _, wire in jobs}), ACTOR: 2 * len(jobs), JUDGE: 2 * len(jobs)},
        "diagnostic_source_groups": anchor["diagnostic_source_groups"],
        "selector_wires": {uid: sha(wire) for uid, _, wire in jobs},
        "input_hashes": {"/".join(path.parts[-2:]): sha(path.read_bytes()) for path in paths},
        "service_reference_sha256": reference, "independent_confirmation": False,
        "thresholds": {"coverage": 0.9, "mixed_match_margin": 0.02, "harm_per_answer": 0.05},
    }, archive, jobs


def actor_jobs(roots, selected, frozen):
    traces, jobs = {}, []
    for root in roots:
        uid = root["uid"]
        record, reply = selected[uid, "SHARED_USES"]
        if record["request_sha256"] != frozen["selector_wires"][uid]:
            raise ValueError("Selector reply does not match the frozen public request")
        trace = {"status": record["status"], "raw": reply, "request_sha256": record["request_sha256"]}
        traces[uid] = trace
        if record["status"] != "OK":
            continue
        try:
            uses, rejected = method.compile_uses(root, reply)
        except (KeyError, TypeError, ValueError) as error:
            trace.update(status="INVALID_USE_CONTRACT", error=str(error))
            continue
        optional = any(edge["use"] == "OPTIONAL" for edge in uses)
        trace.update(uses=uses, rejected=rejected, route="SEGMENTED" if optional else "SHARED")
        order = method.METHODS if int(sha(uid)[0], 16) % 2 else method.METHODS[::-1]
        for arm in order:
            renderer = arm if optional else method.DIRECT
            wire = method.actor(root, uses, renderer) if uses else joint.prior.task_only_request(root)
            jobs.append((uid, arm, wire))
    return traces, jobs


def evaluate(inputs, stage):
    frozen, archive, selects = inputs
    roots = archive["roots"]
    traces, jobs = actor_jobs(roots, stage(PLAN, selects), frozen)
    actors = stage(ACTOR, jobs)
    outputs = {}
    for uid, arm, wire in jobs:
        record, reply = actors[uid, arm]
        if record["request_sha256"] != sha(wire):
            raise ValueError("Actor reply does not match its request")
        result = {"status": record["status"], "request_sha256": sha(wire), "answer": None, "raw": reply}
        if record["status"] == "OK":
            try:
                mode = arm if traces[uid]["route"] == "SEGMENTED" else method.DIRECT
                answer, added, rejected = method.compile_answer(reply, traces[uid]["uses"], mode)
                result.update(answer=answer, appended_sources=added, rejected_adjustments=rejected)
            except (KeyError, TypeError, ValueError) as error:
                result.update(status="INVALID_ACTOR_CONTRACT", error=str(error))
        outputs[uid, arm] = result

    # Native benchmark labels and scores enter only after generation.
    formal = read(joint.prior.formal.OUT / "PLAN.json")
    cases = joint.prior.author_cases(formal)
    baseline = {row["uid"]: row for row in read(joint.parent.OUT / "SETTLED.json")["rows"]}
    grade_jobs, graded = [], {}
    for root in roots:
        uid = root["uid"]
        for arm in method.METHODS:
            result = outputs.get((uid, arm), {"status": "NO_VALID_SELECTOR", "answer": None})
            answer = result["answer"]
            if not answer:
                graded[uid, arm] = {"fields": {}, "status": result["status"]}
                continue
            original = next((name for name, saved in root["archived"].items()
                             if saved["answer"] == answer and saved["raw_judge"] is not None), None)
            if original is not None:
                score = baseline[uid]["native"][original]
                if score["raw"] != root["archived"][original]["raw_judge"]:
                    raise ValueError("Exact-answer score does not match archive")
                graded[uid, arm] = {**score, "reuse": original}
            else:
                grade_jobs.append((uid, arm, joint.parent.grade_request(formal, cases[uid], answer)))
    judged = stage(JUDGE, grade_jobs)
    for uid, arm, wire in grade_jobs:
        record, reply = judged[uid, arm]
        if record["request_sha256"] != sha(wire):
            raise ValueError("Judge receipt does not match the compiled answer")
        graded[uid, arm] = joint.parent.parse_grade(record, reply, baseline[uid]["positions"])

    rows = []
    for old in baseline.values():
        uid = old["uid"]
        if uid not in traces:
            continue
        rows.append({**{key: old[key] for key in ("uid", "group", "positions", "labels", "less_exposed")},
                     "selection": traces[uid],
                     "actor": {arm: outputs.get((uid, arm), {"status": "NO_VALID_SELECTOR"})
                               for arm in method.METHODS},
                     "native": {**old["native"], **{arm: graded[uid, arm] for arm in method.METHODS}}})
    if len(rows) != len(roots):
        raise ValueError("Native scoring rows differ from the frozen source roster")
    return rows


def report(frozen, rows, ledger):
    panels = subsets(rows, frozen)
    panels["optional_treatment"] = [row for row in rows if row["selection"].get("route") == "SEGMENTED"]
    metrics = {name: {other: {
        "match": v42.paired(panel, other, method.SEGMENTED),
        **{field: joint.parent.comparisons.grade_pair(panel, other, method.SEGMENTED, field)
           for field in (*joint.SUPPORT, "VG")},
    } for other in (method.DIRECT, GATE, RP, RULE)} for name, panel in panels.items()}
    main, mixed = (metrics[part][method.DIRECT] for part in ("all", "contains_BC"))
    threshold = frozen["thresholds"]
    screen = {"coverage": main["match"]["valid_cases"] >= threshold["coverage"] * len(rows),
              "match": main["match"].get("95pct_source_bootstrap", [-1])[0] > 0,
              "mixed_match": mixed["match"].get("95pct_source_bootstrap", [-1])[0]
              >= -threshold["mixed_match_margin"],
              **{k: block[k].get("95pct_source_bootstrap", [0, 1])[1] <= threshold["harm_per_answer"]
                 for k, block in (("OPB", main), ("UPB", mixed), ("FM", mixed))}}
    counts = Counter(record["unit"]["stage"] for record in ledger)
    if any(count > frozen["caps"][stage] for stage, count in counts.items()):
        raise ValueError("Physical execution exceeded its frozen allocation")
    return {"assigned": len(rows), "metrics": metrics, "screen": screen, "screen_pass": all(screen.values()),
            "selector_status": Counter(row["selection"]["status"] for row in rows),
            "selected_uses": Counter(edge["use"] for row in rows for edge in row["selection"].get("uses", [])),
            "optional_treatment_roots": len(panels["optional_treatment"]),
            "actor_status": {arm: Counter(row["actor"][arm]["status"] for row in rows) for arm in method.METHODS},
            "physical_requests": counts, "transport": Counter(record["status"] for record in ledger),
            "reported_tokens": sum((r["usage"] or {}).get("total_tokens", 0) for r in ledger),
            "without_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
            "independent_confirmation": False}


def main(action):
    path = OUT / "FROZEN.json"
    if action in ("prepare", "freeze"):
        reference = "OFFLINE" if action == "prepare" else probe.read_reference()[1]
        design = prepare(reference)[0]
        if action == "freeze":
            probe.freeze(path, design)
        else:
            print(json.dumps(design, ensure_ascii=False, indent=2))
        return
    live = action == "run"
    frozen = read(path)
    design = prepare(frozen["service_reference_sha256"])
    if design[0] != frozen or (live and probe.read_reference()[1] != frozen["service_reference_sha256"]):
        raise ValueError("Frozen design or gateway fingerprint changed")
    cache = v42.old_receipts(design[1])
    for old in (joint.parent.OUT, joint.OUT, joint.OUT.with_name("rp_seed_minimal_revision_rpeval_v1"),
                joint.OUT.with_name("focal_memory_rpeval_v1")):
        for name in (ACTOR, JUDGE):
            exact = old / f"{name}_EXACT.json"
            if not exact.exists():
                continue
            for digest, entry in read(exact).items():
                if digest != entry[0]["request_sha256"]:
                    raise ValueError("Archived receipt and request hash disagree")
                cache[name].setdefault(digest, entry)
    probe.OUT, probe.RUN, v42.OUT = OUT, RUN, OUT

    def stage(name, jobs):
        records = v42.execute_stage(frozen, "main", name, jobs, cache[name], live)
        if any(record["status"] == "PENDING_DELIVERY_UNKNOWN" for record, _ in records.values()):
            raise RuntimeError(f"{name}: retained an indeterminate dispatch")
        return records

    state = OUT / "RUN_STATE.json"
    if live:
        probe.atomic_json(state, {"state": "RUNNING", "caps": frozen["caps"]})
    try:
        rows = evaluate(design, stage)
        ledger = [record for stage_name in (PLAN, ACTOR, JUDGE)
                  for record, _ in probe.stage_receipts(stage_name).values()]
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
