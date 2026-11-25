"""Run or replay the matched decision-edit experiment on the exposed RPEval cohort."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path

from qamc.common import parse_object, sha

import analyze_fixed_answer_choice_v44 as comparisons
import audit_prior_patches as prior_patches
import decision_edit as edit
from preflight_decision_edit import edit_wires, prior, task_only, witness

v42 = comparisons.run.stage.v42
probe, read = prior.probe, prior.read
HERE = Path(__file__).resolve().parent
OUT = HERE.with_name("decision_edit_rpeval")
RUN = prior.RUN.with_name(OUT.name)
EDIT, JUDGE = "PatchEdit", prior.NATIVE
GENERIC, DECISION = edit.METHODS
CONTROLS = (GENERIC, comparisons.RP, comparisons.GATE, comparisons.ZERO,
            comparisons.RULE, comparisons.GENERIC, comparisons.REVIEW)


def prepare(reference):
    preflight_path = HERE / "PREFLIGHT.json"
    archive_path = prior.OUT / "FROZEN.json"
    controls_path = comparisons.run.OUT / "COMPLETED.json"
    diagnostic_path = HERE / "PRIOR_PATCH_AUDIT.json"
    diagnostics = read(diagnostic_path)
    if diagnostics != prior_patches.audit():
        raise ValueError("Earlier patch and exposure audit changed")
    preflight = read(preflight_path)["RPEval"]
    original = read(archive_path)
    roots = original["roots"]
    saved = task_only.saved_drafts(original)
    expected = {row["uid"]: row for row in preflight["observed"]}
    payloads, jobs = {}, []
    for root in roots:
        uid = root["uid"]
        base = saved[root["task_wire_sha256"]]
        if not base["answer"]:
            if uid in expected:
                raise ValueError("A preflighted draft is no longer available")
            continue
        if sha(prior.task_only_request(root)) != root["task_wire_sha256"]:
            raise ValueError("An archived draft used a different task")
        payload, wires, _ = edit_wires(root, base["answer"])
        evidence = expected[uid]
        if sha(base["answer"]) != evidence["base_answer_sha256"]:
            raise ValueError("A preflighted answer changed")
        payloads[uid] = payload
        order = list(zip(edit.METHODS, wires, strict=True))
        if int(sha(["edit-order", uid])[:2], 16) % 2:
            order.reverse()
        for method, wire in order:
            if sha(wire) != evidence["edit_wires_sha256"][method]:
                raise ValueError("Editing request differs from the accepted input")
            jobs.append((uid, method, wire))
    if payloads.keys() != expected.keys():
        raise ValueError("Editor cohort changed")
    return {
        "service_reference_sha256": reference,
        "paths": {f"{path.parent.name}/{path.name}": sha(path.read_bytes()) for path in
                  (Path(__file__), Path(edit.__file__), preflight_path, archive_path, controls_path, diagnostic_path,
                   prior.formal.OUT / "PLAN.json", Path(prior.formal.__file__), HERE / "README.md")},
        "assigned": len(roots), "eligible": len(payloads), "independent_confirmation": False,
        "diagnostic_source_groups": diagnostics["diagnostic_groups"],
        "eligible_outside_diagnostic_groups": diagnostics["eligible_remaining"],
        "request_caps": {EDIT: len({sha(wire) for _, _, wire in jobs}), JUDGE: len(jobs)},
        "base_draft_requests": 0,
        "thresholds": {"coverage": 0.9, "mixed_match_margin": 0.02, "harm_per_answer": 0.05},
    }, roots, payloads, jobs


def parse_edit(record, raw, payload, wire_hash):
    if record["request_sha256"] != wire_hash:
        raise ValueError("Editor receipt does not match its request")
    entry = {"status": record["status"], "request_sha256": wire_hash, "reply": raw}
    if record["status"] != "OK":
        return entry
    try:
        return {**entry, **edit.compile_answer(payload, raw)}
    except (TypeError, ValueError) as error:
        return {**entry, "status": "INVALID_EDIT_CONTRACT", "error": str(error)}


def grade_request(original, case, answer):
    uid = case["uid"]
    row = {"uid": uid, "method": prior.GATE, "actor_status": "OK", "answer": answer}
    item, = prior.formal.grading_jobs(original, [case], [row])
    return item["request"]


def parse_grade(record, raw, positions):
    entry = {"status": record["status"], "request_sha256": record["request_sha256"],
             "fields": {}, "raw": raw}
    if record["status"] != "OK":
        return entry
    try:
        fields, invalid = probe.fields(parse_object(raw), positions, True)
    except (KeyError, TypeError, ValueError) as error:
        return {**entry, "status": "INVALID_JUDGE_CONTRACT", "error": str(error)}
    return {**entry, "fields": fields, "invalid_fields": invalid}


def evaluate(inputs, stage):
    plan, roots, payloads, edits = inputs
    editor_replies = stage(EDIT, edits)
    outputs = {(uid, method): parse_edit(*editor_replies[uid, method], payloads[uid], sha(wire))
               for uid, method, wire in edits}

    # Inspect reconstruction and evaluation metadata only after all editor calls.
    original = read(prior.formal.OUT / "PLAN.json")
    cases = prior.author_cases(original)
    archive = {r["uid"]: r for r in read(comparisons.run.OUT / "COMPLETED.json")["rows"]}
    proof = {row["uid"]: row for row in read(HERE / "PREFLIGHT.json")["RPEval"]["observed"]}
    reused, jobs = {}, []
    for root in roots:
        uid = root["uid"]
        if uid not in payloads:
            continue
        base = payloads[uid]["original_answer"]
        for method in edit.METHODS:
            key = uid, method
            answer = outputs[key].get("answer")
            if answer is None:
                continue
            wire = grade_request(original, cases[uid], answer)
            digest = sha(wire)
            outputs[key]["judge_sha256"] = digest
            if answer == base:
                if digest != proof[uid]["native_unchanged_sha256"]:
                    raise ValueError("Unchanged answer would receive a different grading request")
                reused[key] = {**archive[uid]["native"][comparisons.ZERO], "reuse": comparisons.ZERO}
                continue
            # The archived RP and Gate Actor and Judge wires were verified in the V41 inventory.
            exact = next((m for m, old in root["archived"].items()
                          if answer == old["answer"] and old["raw_judge"] is not None), None)
            if exact is not None:
                saved = archive[uid]["native"][exact]
                if saved["raw"] != root["archived"][exact]["raw_judge"]:
                    raise ValueError("Native score differs from the archived exact answer")
                reused[key] = {**saved, "reuse": exact}
            else:
                jobs.append((uid, method, wire))
    grades = stage(JUDGE, jobs)
    grade_wires = {(uid, method): sha(wire) for uid, method, wire in jobs}
    rows = []
    for root in roots:
        uid = root["uid"]
        row = archive[uid]
        native = dict(row["native"])
        decisions = {}
        for method in edit.METHODS:
            key = uid, method
            decisions[method] = outputs.get(key, {"status": "NO_USABLE_DRAFT"})
            if key in reused:
                native[method] = reused[key]
            elif key in grades:
                record, raw = grades[key]
                if grade_wires[key] != record["request_sha256"]:
                    raise ValueError("Judge graded a different answer")
                native[method] = parse_grade(record, raw, row["positions"])
            else:
                native[method] = {"fields": {}, "raw": None}
        rows.append({**row, "native": native, "edits": decisions})
    if len(rows) != plan["assigned"]:
        raise ValueError("Assigned rows disappeared during evaluation")
    return rows


def report(plan, rows, ledger):
    eligible = [row for row in rows if row["assignment"] != "NO_USABLE_DRAFT"]
    if len(eligible) != plan["eligible"]:
        raise ValueError("Evaluation cohort does not equal editor cohort")
    panels = {
        "eligible": eligible, "all_A": [r for r in eligible if set(r["labels"]) == {"A"}],
        "contains_BC": [r for r in eligible if set(r["labels"]) != {"A"}],
        "less_exposed": [r for r in eligible if r["less_exposed"]],
        "outside_documented_diagnostics": [r for r in eligible if r["group"] not in plan["diagnostic_source_groups"]],
    }
    if len(panels["outside_documented_diagnostics"]) != plan["eligible_outside_diagnostic_groups"]:
        raise ValueError("Documented diagnostic groups do not match the frozen split")
    metrics = {name: {m: {
        "match": v42.paired(panel, m, DECISION),
        **{f: comparisons.grade_pair(panel, m, DECISION, f) for f in ("OPB", "UPB", "FM", "full_match")},
    } for m in CONTROLS} for name, panel in panels.items()}
    caps = plan["thresholds"]
    checks = {}
    for m in (GENERIC, comparisons.RP, comparisons.RULE):
        main, mixed = metrics["eligible"][m], metrics["contains_BC"][m]
        checks[m] = {
            "coverage": main["match"]["valid_cases"] >= caps["coverage"] * len(eligible),
            "match": main["match"].get("95pct_source_bootstrap", [-1])[0] > 0,
            "OPB": main["OPB"].get("95pct_source_bootstrap", [0, 1])[1] <= caps["harm_per_answer"],
            "mixed_match": mixed["match"].get("95pct_source_bootstrap", [-1])[0] >= -caps["mixed_match_margin"],
            **{f: mixed[f].get("95pct_source_bootstrap", [0, 1])[1] <= caps["harm_per_answer"] for f in ("UPB", "FM")},
        }
    stages = Counter(rec["unit"]["stage"] for rec in ledger)
    if stages.keys() - plan["request_caps"].keys() or any(n > plan["request_caps"][s] for s, n in stages.items()):
        raise ValueError("Physical records exceeded the experimental envelope")
    activation_panels = {**panels, "contains_C": [r for r in eligible if "C" in r["labels"]]}
    return {
        "assigned": len(rows), "eligible": len(eligible), "new_requests": stages,
        "transport_status": Counter(rec["status"] for rec in ledger),
        "reported_tokens": sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger),
        "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
        "edit_status": {m: Counter(row["edits"][m].get("transaction", row["edits"][m]["status"]) for row in rows)
                        for m in edit.METHODS},
        "edit_activation": {name: {m: Counter(
            r["edits"][m].get("transaction", r["edits"][m]["status"]) for r in subset)
            for m in edit.METHODS} for name, subset in activation_panels.items()},
        "native_grade_reused": {m: sum("reuse" in row["native"][m] for row in rows) for m in edit.METHODS},
        "metrics": metrics, "screen": checks, "screen_pass": all(all(c.values()) for c in checks.values()),
    }


def main(action):
    frozen = OUT / "FROZEN.json"
    if action == "prepare":
        plan, _, _, _ = prepare("OFFLINE_PLACEHOLDER")
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return
    if action == "freeze":
        if read(witness.OUT / "RUN_STATE.json")["state"] != "COMPLETE":
            raise ValueError("Settle the previous wide-panel experiment before freezing this one")
        plan, _, _, _ = prepare(probe.read_reference()[1])
        probe.freeze(frozen, plan)
        return
    plan = read(frozen)
    inputs = prepare(plan["service_reference_sha256"])
    if plan != inputs[0] or (action == "run" and probe.read_reference()[1] != plan["service_reference_sha256"]):
        raise ValueError("Frozen design or live gateway fingerprint changed")
    cache = v42.old_receipts(read(prior.OUT / "FROZEN.json"))[JUDGE]
    probe.OUT, probe.RUN, v42.OUT = OUT, RUN, OUT

    def stage(name, jobs):
        receipts = v42.execute_stage(plan, "main", name, jobs, cache if name == JUDGE else {}, action == "run")
        if any(record["status"] == "PENDING_DELIVERY_UNKNOWN" for record, _ in receipts.values()):
            raise RuntimeError("A receipt is awaiting delivery settlement")
        return receipts

    state = OUT / "RUN_STATE.json"
    if action == "run":
        probe.atomic_json(state, {"state": "RUNNING", "caps": plan["request_caps"]})
    try:
        rows = evaluate(inputs, stage)
        ledger = [record for name in (EDIT, JUDGE)
                  for record, _ in probe.stage_receipts(name).values() if record]
        settled = {"rows": rows, "ledger": ledger}
        summary = report(plan, rows, ledger)
        for path, value in ((OUT / "SETTLED.json", settled), (OUT / "RESULTS.json", summary)):
            if action == "report":
                if read(path) != json.loads(json.dumps(value)):
                    raise ValueError("Offline regrade diverged from the settled record")
            else:
                probe.freeze(path, value)
    except (OSError, ValueError, RuntimeError) as error:
        if action == "run":
            probe.atomic_json(state, {"state": "STOPPED", "error": str(error)})
        raise
    if action == "run":
        probe.atomic_json(state, {"state": "COMPLETE", "physical_requests": len(ledger)})


if __name__ == "__main__":
    cli = ArgumentParser(description=__doc__)
    cli.add_argument("action", choices=("prepare", "freeze", "run", "report"))
    action = cli.parse_args().action
    if action in ("freeze", "run"):
        with probe.runner_lock(RUN / "runner.lock"):
            main(action)
    else:
        main(action)
