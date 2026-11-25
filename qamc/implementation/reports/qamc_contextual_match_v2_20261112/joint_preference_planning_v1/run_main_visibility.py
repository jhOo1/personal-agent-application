"""Isolate the effect of optional evidence visibility on the compiled main answer."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path

from qamc.common import sha, token_estimate

import run_realization_append_ablation as ablation
from settle_decision_realization import checked
from settle_joint_planning import subsets, usage


parent, method, v42, probe, read = ablation.parent, ablation.method, ablation.v42, ablation.probe, ablation.read
OUT = parent.OUT.with_name("decision_main_visibility_rpeval_v1")
RUN = parent.RUN.with_name(OUT.name)
ACTOR, JUDGE = parent.ACTOR, parent.JUDGE
ARM = "MAIN_MASK_OPTIONAL"


def actor_view(root, uses):
    kept = [edge for edge in uses if edge["use"] != "OPTIONAL"]
    removed = {edge["memory_id"] for edge in uses if edge["use"] == "OPTIONAL"}
    before, after = (method.actor(root, edges, method.SEGMENTED) for edges in (uses, kept))
    a, b = (json.loads(wire["messages"][1]["content"]) for wire in (before, after))
    expected = {**a, "licensed_uses": [e for e in a["licensed_uses"] if e["memory_id"] not in removed],
                "source_evidence": [e for e in a["source_evidence"] if e["memory_id"] not in removed]}
    for wire in (before, after):
        if len(wire["messages"]) != 2:
            raise ValueError("Expected the two-message realization wire")
    envelope = lambda w: {**w, "messages": w["messages"][:1]}
    if not removed or b != expected or envelope(before) != envelope(after):
        raise ValueError("Isolation must change only optional memory visibility")
    return before, after, kept, sorted(removed)


def prepare():
    old_frozen, rows, _ = checked()
    archive_path = parent.joint.prior.OUT / "FROZEN.json"
    archive = read(archive_path)
    roots = {root["uid"]: root for root in archive["roots"]}
    changed = ablation.changed_answers(rows)
    jobs, provenance = [], {}
    for row in rows:
        selection = row["selection"]
        if selection.get("route") != "SEGMENTED":
            continue
        uid = row["uid"]
        before, after, kept, removed = actor_view(roots[uid], selection["uses"])
        old = row["actor"][method.SEGMENTED]
        if old["request_sha256"] != sha(before) or uid not in changed:
            raise ValueError("Masked Actor must match the pinned same-draft intervention set")
        jobs.append((uid, ARM, after))
        provenance[uid] = {"group": row["group"], "before_sha256": sha(before), "after_sha256": sha(after),
                           "removed": removed, "kept": kept,
                           "estimated_input_tokens_removed": token_estimate(before["messages"][1]["content"])
                           - token_estimate(after["messages"][1]["content"])}
    if set(provenance) != changed.keys() or len(jobs) != 80:
        raise ValueError("Expected the fixed 80 treated roots")
    paths = (Path(__file__), Path(__file__).with_name("MAIN_VISIBILITY_PROTOCOL.md"),
             Path(method.__file__), archive_path, parent.OUT / "FROZEN.json", parent.OUT / "SETTLED.json",
             ablation.OUT / "FROZEN.json", ablation.OUT / "SETTLED.json", ablation.OUT / "ACTOR_COHORT.json")
    plan = {
        "assigned": len(rows), "intervention_roots": provenance,
        "caps": {ACTOR: len({sha(wire) for _, _, wire in jobs}), JUDGE: len(jobs)},
        "service_reference_sha256": old_frozen["service_reference_sha256"],
        "diagnostic_source_groups": old_frozen["diagnostic_source_groups"],
        "thresholds": old_frozen["thresholds"], "independent_confirmation": False,
        "parents": {"/".join(path.parts[-2:]): sha(path.read_bytes()) for path in paths},
    }
    return plan, archive, jobs, changed


def render(plan, actors):
    answers = {}
    for uid, evidence in plan["intervention_roots"].items():
        rec, reply = actors[uid, ARM]
        if rec["request_sha256"] != evidence["after_sha256"]:
            raise ValueError("Actor reply does not match the frozen removal")
        status, answer = rec["status"], None
        if status == "OK":
            try:
                answer, added, rejected = method.compile_answer(reply, evidence["kept"], method.SEGMENTED)
                if added:
                    raise ValueError("A masked Actor unexpectedly added optional content")
            except (ValueError, KeyError, TypeError):
                status, answer, rejected = "INVALID_ACTOR_CONTRACT", None, []
        else:
            rejected = []
        answers[uid] = {"status": status, "answer": answer, "raw": reply,
                        "request_sha256": evidence["after_sha256"], "rejected_adjustments": rejected}
    return answers


def settlement(plan, stage, jobs, changed):
    answers = render(plan, stage(ACTOR, jobs))
    base = read(ablation.OUT / "SETTLED.json")["rows"]
    grading = {uid: (r["answer"],) for uid, r in answers.items() if r["answer"] and r["answer"] != changed[uid][0]}
    requests = [(uid, ARM, wire) for uid, _, wire in ablation.grading_jobs(grading)]
    maps = {uid: sha(wire) for uid, _, wire in requests}
    grades = stage(JUDGE, requests)
    result = []
    for row in base:
        uid = row["uid"]
        native = dict(row["native"])
        answer = answers.get(uid)
        if answer is None or answer["answer"] == changed[uid][0]:
            value = {**native[ablation.MAIN_ONLY], "reuse": ablation.MAIN_ONLY}
        elif uid not in grading:
            value = {"fields": {}, "status": answer["status"]}
        else:
            rec, reply = grades[uid, ARM]
            if rec["request_sha256"] != maps[uid]:
                raise ValueError("Native response doesn't match the new answer")
            value = parent.joint.parent.parse_grade(rec, reply, row["positions"])
        native[ARM] = value
        result.append({**row, "native": native})
    return result, answers


def outcome(plan, rows, answers, receipts):
    panels = subsets(rows, plan)
    panels["intervention"] = [row for row in rows if row["uid"] in answers]
    panels["retained_nonoptional"] = [row for row in panels["intervention"]
                                    if plan["intervention_roots"][row["uid"]]["kept"]]
    comparisons = {key: {control: {
        "match": v42.paired(panel, control, ARM),
        **{field: parent.joint.parent.comparisons.grade_pair(panel, control, ARM, field)
           for field in ("OPB", "UPB", "FM")},
    } for control in (ablation.MAIN_ONLY, parent.GATE, parent.RP, parent.RULE)} for key, panel in panels.items()}
    used = usage(receipts)
    if any(n > plan["caps"][stage] for stage, n in used["stage_counts"].items()):
        raise ValueError("Execution exceeded the frozen cap")
    limit = plan["thresholds"]
    main = comparisons["all"][ablation.MAIN_ONLY]
    mixed = comparisons["contains_BC"][ablation.MAIN_ONLY]
    checks = {
        "coverage": main["match"]["valid_cases"] >= limit["coverage"] * len(rows),
        "match": main["match"].get("95pct_source_bootstrap", [-1])[0] > 0,
        "mixed_match": mixed["match"].get("95pct_source_bootstrap", [-1])[0] >= -limit["mixed_match_margin"],
        **{key: metrics[key].get("95pct_source_bootstrap", [0, 1])[1] <= limit["harm_per_answer"]
           for key, metrics in (("OPB", main), ("UPB", mixed), ("FM", mixed))},
    }
    return {"comparisons": comparisons, "treatment_actor_status": Counter(r["status"] for r in answers.values()),
            "development_screen": checks, "screen_pass": all(checks.values()), "usage": used,
            "new_selector_requests": 0, "independent_confirmation": False}


def main(action):
    plan, archive, jobs, changed = prepare()
    path = OUT / "FROZEN.json"
    if action == "freeze":
        probe.freeze(path, plan)
        return
    live = action == "run"
    if read(path) != plan or (live and probe.read_reference()[1] != plan["service_reference_sha256"]):
        raise ValueError("The same-task diagnostic inputs or service fingerprint changed")
    cache = v42.old_receipts(archive)
    for folder in (parent.joint.parent.OUT, parent.OUT, ablation.OUT,
                   ablation.OUT.with_name("decision_optional_release_rpeval_v1")):
        for name in (ACTOR, JUDGE):
            exact = folder / f"{name}_EXACT.json"
            if exact.exists():
                for digest, pair in read(exact).items():
                    if digest != pair[0]["request_sha256"]:
                        raise ValueError("Old receipt hash mismatch")
                    cache[name].setdefault(digest, pair)
    probe.OUT, probe.RUN, v42.OUT = OUT, RUN, OUT
    state = OUT / "RUN_STATE.json"

    def stage(name, positions):
        values = v42.execute_stage(plan, "main", name, positions, cache[name], live)
        if any(rec["status"] == "PENDING_DELIVERY_UNKNOWN" for rec, _ in values.values()):
            raise RuntimeError("Retained an indeterminate delivery")
        return values

    if live:
        probe.atomic_json(state, {"state": "RUNNING", "caps": plan["caps"]})
    try:
        rows, answers = settlement(plan, stage, jobs, changed)
        physical = [rec for name in (ACTOR, JUDGE) for rec, _ in probe.stage_receipts(name).values()]
        probe.freeze(OUT / "SETTLED.json", {"rows": rows, "answers": answers, "ledger": physical})
        probe.freeze(OUT / "RESULTS.json", outcome(plan, rows, answers, physical))
    except (OSError, RuntimeError, ValueError) as error:
        if live:
            probe.atomic_json(state, {"state": "STOPPED", "error": str(error)})
        raise
    if live:
        probe.atomic_json(state, {"state": "COMPLETE", "physical_requests": len(physical)})


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "report"))
    with probe.runner_lock(RUN / "runner.lock"):
        main(parser.parse_args().action)
