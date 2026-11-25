"""Run or replay the archived-RP minimal-revision control on the 233 exposed cases."""
from argparse import ArgumentParser
from collections import Counter
from pathlib import Path
import json

from qamc.common import canonical, sha, token_estimate

import run_joint_planning as joint
import seed_control as edit

OUT = joint.OUT.with_name("rp_seed_minimal_revision_rpeval_v1")
RUN = joint.RUN.with_name(OUT.name)
PLAN, JUDGE = joint.PLAN, joint.JUDGE
RP = joint.parent.comparisons.RP
read, probe = joint.read, joint.probe


def prepare(reference):
    archive = read(joint.prior.OUT / "FROZEN.json")
    previous = read(joint.OUT / "FROZEN.json")
    controls = read(joint.parent.OUT / "SETTLED.json")["rows"]
    roots = archive["roots"]
    if len(roots) != 233 or {root["uid"] for root in roots} != previous["planner_wires_sha256"].keys():
        raise ValueError("The RP control must use the frozen exposed roster")
    if [(root["uid"], root["group"]) for root in roots] != [(row["uid"], row["group"]) for row in controls]:
        raise ValueError("Archived answers differ from the common score roster")
    data = {root["uid"]: edit.payload(root, RP) for root in roots}
    jobs = [(uid, edit.METHOD, edit.request(packet)) for uid, packet in data.items()]
    max_estimated = max(token_estimate(canonical(wire["messages"])) for _, _, wire in jobs)
    if max_estimated > 32768:
        raise ValueError("The edit input exceeds the tested size limit")
    paths = [Path(__file__), Path(__file__).with_name("SEED_CONTROL.md"), Path(edit.__file__),
             Path(joint.planning.__file__), Path(joint.parent.edit.__file__),
             joint.parent.HERE / "audit_edit_size.py", joint.OUT / "FROZEN.json",
             joint.prior.OUT / "FROZEN.json", joint.parent.OUT / "SETTLED.json",
             joint.prior.formal.OUT / "PLAN.json", Path(joint.prior.formal.__file__),
             Path(joint.v42.__file__), Path(joint.prior.__file__)]
    spec = {
        "assigned": len(roots), "independent_confirmation": False, "source_groups": previous["source_groups"],
        "service_reference_sha256": reference, "request_caps": {PLAN: len(jobs), JUDGE: len(jobs)},
        "review_screen_match_gain": 0.03,
        "max_estimated_input_tokens": max_estimated,
        "wire_sha256": {uid: sha(wire) for uid, _, wire in jobs},
        "inputs_sha256": {str(p.relative_to(joint.HERE.parent.parent.parent)): sha(p.read_bytes()) for p in paths},
    }
    return spec, jobs, data, controls, archive


def evaluate(inputs, stage):
    frozen, jobs, data, controls, archive = inputs
    revisions = stage(PLAN, jobs)
    # Native evaluation is consulted only after the revision requests have returned.
    official = read(joint.prior.formal.OUT / "PLAN.json")
    cases = joint.prior.author_cases(official)
    archived = {row["uid"]: row["archived"] for row in archive["roots"]}
    output, grades, reused = {}, [], {}
    for old in controls:
        uid = old["uid"]
        rec, raw = revisions[uid, edit.METHOD]
        if rec["request_sha256"] != frozen["wire_sha256"][uid]:
            raise ValueError("Revision receipt does not match the frozen request")
        result = {"status": rec["status"], "raw": raw, "request_sha256": rec["request_sha256"]}
        output[uid] = result
        if rec["status"] != "OK":
            continue
        try:
            result.update(edit.compile_revision(data[uid], raw))
        except (ValueError, TypeError) as error:
            result.update(status="INVALID_REVISION_CONTRACT", error=str(error))
        answer = result.get("answer")
        if not answer:
            continue
        grade = joint.parent.grade_request(official, cases[uid], answer)
        result["judge_sha256"] = sha(grade)
        exact = next((m for m, saved in archived[uid].items()
                      if saved["answer"] == answer and saved["raw_judge"] is not None), None)
        if exact is None:
            grades.append((uid, edit.METHOD, grade))
        else:
            saved = old["native"][exact]
            if saved["raw"] != archived[uid][exact]["raw_judge"]:
                raise ValueError("Native score and archived exact answer differ")
            reused[uid] = {**saved, "reuse": exact}
    received = stage(JUDGE, grades)
    rows = []
    for old in controls:
        uid = old["uid"]
        result = output[uid]
        if uid in reused:
            native = reused[uid]
        elif (uid, edit.METHOD) in received:
            record, response = received[uid, edit.METHOD]
            if record["request_sha256"] != result["judge_sha256"]:
                raise ValueError("Native score receipt names a different answer")
            native = joint.parent.parse_grade(record, response, old["positions"])
        else:
            native = {"fields": {}, "status": result["status"]}
        rows.append({**{k: old[k] for k in ("uid", "group", "labels", "positions", "less_exposed")},
                     "native": {**old["native"], edit.METHOD: native}, "revision": result})
    return rows


def main(action):
    path = OUT / "FROZEN.json"
    if action in ("prepare", "freeze"):
        reference = "OFFLINE_PLACEHOLDER" if action == "prepare" else probe.read_reference()[1]
        spec = prepare(reference)[0]
        if action == "prepare":
            print(json.dumps(spec, ensure_ascii=False, indent=2))
        else:
            probe.freeze(path, spec)
        return
    live = action == "run"
    frozen = read(path)
    inputs = prepare(frozen["service_reference_sha256"])
    if frozen != inputs[0] or (live and probe.read_reference()[1] != frozen["service_reference_sha256"]):
        raise ValueError("Frozen revision design or live gateway fingerprint changed")
    cache = joint.v42.old_receipts(inputs[-1])[JUDGE]
    recent = read(joint.parent.OUT / f"{JUDGE}_EXACT.json")
    if any(digest != record["request_sha256"] for digest, (record, _) in recent.items()):
        raise ValueError("Inconsistent reused grading request hash")
    cache.update(recent)
    probe.OUT, probe.RUN, joint.v42.OUT = OUT, RUN, OUT

    def stage(name, jobs):
        returned = joint.v42.execute_stage(frozen, "main", name, jobs, cache if name == JUDGE else {}, live)
        if any(record["status"] == "PENDING_DELIVERY_UNKNOWN" for record, _ in returned.values()):
            raise RuntimeError(f"{name}: receipt delivery remains unknown")
        return returned

    state = OUT / "RUN_STATE.json"
    if live:
        probe.atomic_json(state, {"state": "RUNNING", "caps": frozen["request_caps"]})
    try:
        rows = evaluate(inputs, stage)
        ledger = [record for name in (PLAN, JUDGE) for record, _ in probe.stage_receipts(name).values() if record]
        counts = Counter(record["unit"]["stage"] for record in ledger)
        if any(n > frozen["request_caps"].get(s, 0) for s, n in counts.items()):
            raise ValueError("Physical requests exceeded the revision budget")
        probe.freeze(OUT / "SETTLED.json", {"rows": rows, "ledger": ledger})
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
