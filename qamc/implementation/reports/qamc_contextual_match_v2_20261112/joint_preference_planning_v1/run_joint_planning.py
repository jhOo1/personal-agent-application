"""Run the joint preference planner on the original 233 exposed RPEval tasks."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path

from qamc.common import canonical, sha, token_estimate

import planning
import run_decision_edit as parent

HERE = Path(__file__).resolve().parent
OUT = HERE.with_name("joint_preference_planning_rpeval_v1")
RUN = parent.RUN.with_name(OUT.name)
prior, v42, probe, read = parent.prior, parent.v42, parent.probe, parent.read
PLAN, ACTOR, JUDGE = v42.SELECTOR, v42.ACTOR, v42.JUDGE
MODEL, SOLVED = planning.METHODS
CONTROLS = (MODEL, parent.comparisons.RP, parent.comparisons.RULE, parent.comparisons.GATE,
            parent.comparisons.ZERO, parent.comparisons.REVIEW)
SUPPORT = ("OPB", "UPB", "FM", "full_match")


def prepare(reference):
    archive_path = prior.OUT / "FROZEN.json"
    settled_path = parent.OUT / "SETTLED.json"
    previous_plan = parent.OUT / "FROZEN.json"
    archive = read(archive_path)
    roots = archive["roots"]
    if len(roots) != 233 or len({root["uid"] for root in roots}) != 233:
        raise ValueError("The panel is the original 233 distinct exposed tasks")
    if read(parent.OUT / "RUN_STATE.json")["state"] != "COMPLETE":
        raise ValueError("Parent results must be settled")
    controls = read(settled_path)["rows"]
    if any((row["uid"], row["group"]) != (root["uid"], root["group"])
           for row, root in zip(controls, roots, strict=True)):
        raise ValueError("The parent scores are not aligned to the exposed roster")
    packets = {root["uid"]: planning.packet(root) for root in roots}
    jobs = [(uid, "SHARED_PLAN", planning.planner_request(packet)) for uid, packet in packets.items()]
    input_limit = max(token_estimate(canonical(job[2]["messages"])) for job in jobs)
    if input_limit > 32768:
        raise ValueError("Planner input exceeds the locally tested limit")
    paths = (Path(__file__), Path(planning.__file__), HERE / "PROTOCOL.md", archive_path, settled_path,
             previous_plan, Path(v42.__file__), Path(prior.__file__), Path(parent.__file__),
             prior.formal.OUT / "PLAN.json", Path(prior.formal.__file__))
    plan = {
        "service_reference_sha256": reference,
        "hashes": {str(path.relative_to(HERE.parent.parent.parent)): sha(path.read_bytes()) for path in paths},
        "assigned": len(roots), "source_groups": len({root["group"] for root in roots}),
        "diagnostic_source_groups": read(previous_plan)["diagnostic_source_groups"],
        "independent_confirmation": False, "planner_max_estimated_input_tokens": input_limit,
        "request_caps": {PLAN: len(jobs), ACTOR: 2 * len(jobs), JUDGE: 2 * len(jobs)},
        "planner_wires_sha256": {uid: sha(wire) for uid, _, wire in jobs},
        "thresholds": {"coverage": 0.9, "mixed_match_margin": 0.02, "harm_per_answer": 0.05},
    }
    return plan, controls, packets, jobs, archive


def construct_actor_jobs(packets, planner, wires):
    traces, actor_jobs = {}, []
    for uid, packet in packets.items():
        record, raw = planner[uid, "SHARED_PLAN"]
        if record["request_sha256"] != wires[uid]:
            raise ValueError("Planner receipt does not match the original inputs")
        trace = {"status": record["status"], "raw": raw, "request_sha256": wires[uid]}
        traces[uid] = trace
        if record["status"] != "OK":
            continue
        try:
            plan, selectors, audit = planning.compile_plan(packet, raw)
        except (AttributeError, TypeError, KeyError, ValueError) as error:
            trace.update(status="INVALID_PLANNING_CONTRACT", error=str(error))
            continue
        trace.update(plan=plan, selections=selectors, solver=audit)
        jobs = [(uid, method, planning.actor_request(packet, plan, assignment))
                for method, assignment in selectors.items()]
        if any(token_estimate(canonical(wire["messages"])) > 32768 for _, _, wire in jobs):
            trace.update(actor_status="OVERSIZE_INPUT")
        else:
            actor_jobs.extend(jobs)
    return traces, actor_jobs


def evaluate(inputs, stage):
    frozen, controls, packets, planner_jobs, archive = inputs
    planners = stage(PLAN, planner_jobs)
    traces, actor_jobs = construct_actor_jobs(packets, planners, frozen["planner_wires_sha256"])
    actors = stage(ACTOR, actor_jobs)

    # Evaluation-only data are read after all generation requests are complete.
    original = read(prior.formal.OUT / "PLAN.json")
    cases = prior.author_cases(original)
    archived = {row["uid"]: row for row in archive["roots"]}
    grade_jobs, outputs, reused = [], {}, {}
    controls_by_uid = {row["uid"]: row for row in controls}
    for uid, method, wire in actor_jobs:
        record, answer = actors[uid, method]
        if record["request_sha256"] != sha(wire):
            raise ValueError("Actor receipt does not match the shared-plan request")
        out = {"status": record["status"], "answer": answer, "request_sha256": sha(wire)}
        outputs[uid, method] = out
        if record["status"] != "OK" or not isinstance(answer, str) or not answer.strip():
            continue
        grade = parent.grade_request(original, cases[uid], answer)
        out["judge_sha256"] = sha(grade)
        exact = next((m for m, saved in archived[uid]["archived"].items()
                      if saved["answer"] == answer and saved["raw_judge"] is not None), None)
        if exact is None:
            grade_jobs.append((uid, method, grade))
        else:
            saved = controls_by_uid[uid]["native"][exact]
            if saved["raw"] != archived[uid]["archived"][exact]["raw_judge"]:
                raise ValueError("Archived score and exact answer do not match")
            reused[uid, method] = {**saved, "reuse": exact}
    graders = stage(JUDGE, grade_jobs)

    rows = []
    for old in controls:
        uid, width = old["uid"], old["positions"]
        native, final = dict(old["native"]), {}
        for method in planning.METHODS:
            key = (uid, method)
            status = traces[uid].get("actor_status", traces[uid]["status"])
            final[method] = outputs.get(key, {"status": status})
            if key in reused:
                native[method] = reused[key]
            elif key in graders:
                record, raw = graders[key]
                if record["request_sha256"] != final[method]["judge_sha256"]:
                    raise ValueError("Native Judge receipt does not match the answer")
                native[method] = parent.parse_grade(record, raw, width)
            else:
                native[method] = {"fields": {}, "status": final[method]["status"]}
        rows.append({**{k: old[k] for k in ("uid", "group", "labels", "positions", "less_exposed")},
                     "native": native, "planning": traces[uid], "actors": final})
    return rows


def report(frozen, rows, ledger):
    diagnostic = set(frozen["diagnostic_source_groups"])
    panels = {
        "all": rows,
        "all_A": [r for r in rows if set(r["labels"]) == {"A"}],
        "contains_BC": [r for r in rows if "B" in r["labels"] or "C" in r["labels"]],
        "contains_C": [r for r in rows if "C" in r["labels"]],
        "B_without_C": [r for r in rows if "B" in r["labels"] and "C" not in r["labels"]],
        "outside_documented_diagnostics": [r for r in rows if r["group"] not in diagnostic],
    }
    metrics = {name: {m: {
        "match": v42.paired(panel, m, SOLVED),
        **{field: parent.comparisons.grade_pair(panel, m, SOLVED, field) for field in SUPPORT},
    } for m in CONTROLS} for name, panel in panels.items()}
    caps = frozen["thresholds"]
    screen = {}
    for m in (MODEL, parent.comparisons.RP, parent.comparisons.RULE, parent.comparisons.REVIEW):
        main, mixed = metrics["all"][m], metrics["contains_BC"][m]
        screen[m] = {
            "coverage": main["match"]["valid_cases"] >= caps["coverage"] * len(rows),
            "match": main["match"].get("95pct_source_bootstrap", [-1])[0] > 0,
            "OPB": main["OPB"].get("95pct_source_bootstrap", [0, 1])[1] <= caps["harm_per_answer"],
            "mixed_match": mixed["match"].get("95pct_source_bootstrap", [-1])[0] >= -caps["mixed_match_margin"],
            **{f: mixed[f].get("95pct_source_bootstrap", [0, 1])[1] <= caps["harm_per_answer"] for f in ("UPB", "FM")},
        }
    stages = Counter(record["unit"]["stage"] for record in ledger)
    if any(n > frozen["request_caps"].get(s, 0) for s, n in stages.items()):
        raise ValueError("Physical requests exceeded their frozen upper bound")
    valid = [r for r in rows if "solver" in r["planning"]]
    changed = [r for r in valid if r["planning"]["selections"][MODEL] != r["planning"]["selections"][SOLVED]]
    changes = {"structurally_valid": len(valid), "changed_selections": len(changed),
               "changed_source_groups": len({r["group"] for r in changed}),
               "model_plan_conflicts": sum(bool(r["planning"]["solver"]["control_conflicts"]) for r in valid),
               "no_enumerated_feasible_assignment": sum(not r["planning"]["solver"]["feasible_count"] for r in valid),
               "changed_final_answers": sum(
                   bool(r["actors"][MODEL].get("answer")) and bool(r["actors"][SOLVED].get("answer"))
                   and r["actors"][MODEL]["answer"] != r["actors"][SOLVED]["answer"] for r in rows)}
    return {
        "assigned": len(rows), "independent_confirmation": False, "metrics": metrics,
        "screen": screen, "screen_pass": all(all(checks.values()) for checks in screen.values()),
        "changes": changes, "physical_requests": stages,
        "planner_status": Counter(r["planning"]["status"] for r in rows),
        "actor_status": {m: Counter(r["actors"][m]["status"] for r in rows) for m in planning.METHODS},
        "transport_status": Counter(record["status"] for record in ledger),
        "reported_tokens": sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger),
        "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
    }


def main(action):
    config = OUT / "FROZEN.json"
    if action in ("prepare", "freeze"):
        reference = "OFFLINE_PLACEHOLDER" if action == "prepare" else probe.read_reference()[1]
        frozen = prepare(reference)[0]
        if action == "freeze":
            probe.freeze(config, frozen)
        else:
            print(json.dumps(frozen, ensure_ascii=False, indent=2))
        return
    live = action == "run"
    frozen = read(config)
    inputs = prepare(frozen["service_reference_sha256"])
    if frozen != inputs[0] or (live and probe.read_reference()[1] != frozen["service_reference_sha256"]):
        raise ValueError("Frozen design or current gateway fingerprint changed")
    cache = v42.old_receipts(inputs[-1])[JUDGE]
    prior_grades = read(parent.OUT / f"{JUDGE}_EXACT.json")
    if any(digest != record["request_sha256"] for digest, (record, _) in prior_grades.items()):
        raise ValueError("Parent grading cache contains a mismatched request hash")
    cache.update(prior_grades)
    probe.OUT, probe.RUN, v42.OUT = OUT, RUN, OUT

    def stage(name, jobs):
        receipts = v42.execute_stage(frozen, "main", name, jobs, cache if name == JUDGE else {}, live)
        if any(record["status"] == "PENDING_DELIVERY_UNKNOWN" for record, _ in receipts.values()):
            raise RuntimeError(f"{name}: receipt delivery remains unknown")
        return receipts

    state = OUT / "RUN_STATE.json"
    if live:
        probe.atomic_json(state, {"state": "RUNNING", "caps": frozen["request_caps"]})
    try:
        rows = evaluate(inputs, stage)
        ledger = [record for name in (PLAN, ACTOR, JUDGE) for record, _ in probe.stage_receipts(name).values() if record]
        for path, value in ((OUT / "SETTLED.json", {"rows": rows, "ledger": ledger}),
                            (OUT / "RESULTS.json", report(frozen, rows, ledger))):
            probe.freeze(path, value)
    except (OSError, RuntimeError, ValueError) as error:
        if live:
            probe.atomic_json(state, {"state": "STOPPED", "error": str(error)})
        raise
    if live:
        probe.atomic_json(state, {"state": "COMPLETE", "physical_requests": len(ledger)})


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "freeze", "run", "report"))
    action = parser.parse_args().action
    if action in ("freeze", "run"):
        with probe.runner_lock(RUN / "runner.lock"):
            main(action)
    else:
        main(action)
