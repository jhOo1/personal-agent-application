"""Reconstruct exact matched exposure inputs and inventory known repeat receipts."""
from collections import Counter
import json
import sqlite3
from pathlib import Path
from runpy import run_path

from audit_dispatch import account
from compare_controls import load_verified_scores
from complete import AUTHOR, RUN, ROOT, actor_request, get_author, input_requests, normalized, read, select, transfer
from qamc.common import sha
from transfer_replay import persist

HERE = Path(__file__).resolve().parent
EXPECTED = {"cross_domain": 19, "sycophancy": 12, "beneficial_memory_usage": 18}
POLICIES = ("SELECTED", "GROUP", "FULL", "EMPTY", "RUBRIC")
ACTOR_CAP = 8192


def group_endpoint(evidence, memories):
    """Use the same SELECTED decision. Keep failures as missing, not empty."""
    if evidence is None:
        return None
    if not isinstance(evidence, list) or any(text not in memories for text in evidence):
        raise ValueError("Selection is not a subset of the fixed original text")
    return "FULL" if evidence else "EMPTY"


def prepare():
    selected, grades = load_verified_scores()
    uids = {uid for uid in selected if "PB_RUBRIC" in grades[uid]}
    manifest = read(AUTHOR.parent / "PLAN.json")
    cases = {case["uid"]: case for case in manifest["cases"] if case["uid"] in uids}
    tracks = Counter(case["category"] for case in cases.values())
    if (not manifest["not_confirmation"] or tracks != EXPECTED or cases.keys() != uids
            or not all(case["role"] == "DEV" for case in cases.values())
            or len({case["group_id"] for case in cases.values()}) != len(cases)):
        raise ValueError("The exact exposed author-control panel changed")

    records, bounds, _ = get_author()
    author = {(r["uid"], r["method"]): r for r in records if r["uid"] in cases}
    protocol = read(ROOT / "reports/qamc_persistbench_actor_factorial/PLAN.json")
    route_plan = read(transfer.OUT / "PLAN.json")
    inputs = {}
    for uid, case in cases.items():
        task = persist.author.parent.smoke.task_for(case)
        public = {"query": task.query, "memories": [m.text for m in task.memories]}
        if sha(public) != case["public_sha256"]:
            raise ValueError("Original Current Query/Memory changed")
        full = actor_request(case, task.query, public["memories"], protocol, protocol["prompts"]["gepa"])
        empty = actor_request(case, task.query, [], protocol, protocol["prompts"]["gepa"])
        old_gepa = author[uid, "PB_GEPA"]["actor_request"]
        old_rubric = author[uid, "PB_RUBRIC"]["actor_request"]
        for method, wire in (("PB_GEPA", old_gepa), ("PB_RUBRIC", old_rubric)):
            if sha(wire) != author[uid, method]["actor_request_sha256"]:
                raise ValueError("Archived control Actor digest mismatch")
        rubric = dict(old_rubric, max_tokens=ACTOR_CAP)
        if full != dict(old_gepa, max_tokens=ACTOR_CAP) or full["max_tokens"] != ACTOR_CAP:
            raise ValueError("Published full-history control differs beyond output cap")
        if len({sha(wire) for wire in (full, empty, rubric)}) != 3:
            raise ValueError("Disambiguation of three fixed Actor endpoints failed")
        for wire in (empty, rubric):
            if {k:v for k,v in wire.items() if k != "messages"} != {
                    k:v for k,v in full.items() if k != "messages"}:
                raise ValueError("Generation protocol differs outside messages")
        inputs[uid] = {"public": public, "FULL": full, "EMPTY": empty, "RUBRIC": rubric,
                       "selection_requests": input_requests(case, public, route_plan)}
    if len({item["public"]["query"] for item in inputs.values()}) != len(cases):
        raise ValueError("Duplicate public queries require task-scoped shared receipt handling")
    return cases, inputs, protocol, manifest["protocols"]["gpt41"], bounds


def manifests(path, name):
    by_hash = {}
    for item in read(path / f"{name}_MANIFEST.json")["units"]:
        digest = sha(item["request"])
        if digest in by_hash:
            raise ValueError("Ambiguous exact request within one repeated stage")
        by_hash[digest] = (item["unit"]["root_id"], item["request"])
    return by_hash


def original_answer(path, stage, uid, wire):
    db_path = path / stage / "samples.sqlite"
    with sqlite3.connect(db_path.absolute().as_uri() + "?mode=ro", uri=True) as db:
        rows = db.execute(
            "SELECT unit_json, status, request_json, response_json FROM samples WHERE request_sha=?",
            (sha(wire),),
        ).fetchall()
    rows = [row for row in rows if json.loads(row[0])["root_id"] == uid]
    if len(rows) != 1:
        raise ValueError("Ambiguous original physical receipt")
    _, status, actual, response = rows[0]
    if status != "COMPLETE" or json.loads(actual) != wire or response is None:
        raise ValueError("Invalid original physical receipt")
    return json.loads(response)["answer"]


def judge_wire(cases, inputs, judge, bounds):
    scorer = persist.author.ext.parent.persist
    _, rubrics, formatter = scorer.upstream()

    def wire(uid, answer):
        public = inputs[uid]["public"]
        category = cases[uid]["category"]
        request = persist.author.ext.text_request(
            rubrics[category], formatter["build_judge_prompt"](public["memories"], public["query"], answer),
            judge["model"], judge["stages"][persist.STAGE]["max_tokens"])
        if normalized(request, answer) != bounds[uid]:
            raise ValueError("The exact scorer envelope changed")
        return request

    return wire


def inspect_risk(cases, inputs, protocol, judge, bounds):
    """Bind the two old risk waves to identical Actors and exact full-history Judge wire."""
    path = RUN.parent / "persist_equal_cap_safety_v1"
    pin, execution = read(path / "FROZEN.json"), read(path / "EXECUTION.json")
    risk = {}
    build_grade = judge_wire(cases, inputs, judge, bounds)
    for number in (1, 2):
        past = read(path / f"WAVE{number}.json")
        if past["identity"] != execution or execution["experiment_sha256"] != sha(pin):
            raise ValueError("Past deployment is not bound to its frozen plan")
        account(pin, past, number)
        route_wires = manifests(path, f"Wave{number}_Route")
        select_wires = manifests(path, f"Wave{number}_Select")
        actor_wires = manifests(path, f"Wave{number}_Actor")
        grade_wires = manifests(path, f"Wave{number}_Judge")
        per_uid = {(row["uid"], row["arm"]): row for row in past["rows"]}
        if any(row["uid"] not in cases for row in past["rows"]):
            raise ValueError("Earlier matched-cap wave is outside the exposed roster")
        for uid in sorted(pin["tracks"]):
            item = inputs[uid]
            if route_wires[sha(item["selection_requests"]["query"])] != (
                    uid, item["selection_requests"]["query"]):
                raise ValueError("Matched-cap route drift")
            routed = per_uid[uid, "ROUTED"]
            selection_wire = item["selection_requests"][routed["branch"]]
            if select_wires[sha(selection_wire)] != (uid, selection_wire):
                raise ValueError("Matched-cap Selector drift")
            route_reply = original_answer(path, f"Wave{number}_Route", uid, item["selection_requests"]["query"])
            select_reply = original_answer(path, f"Wave{number}_Select", uid, selection_wire)
            evidence = select(cases[uid], item["public"], route_reply, select_reply)
            if routed["selected_count"] != len(evidence) or routed["selected_sha256"] != sha(evidence):
                raise ValueError("Selected evidence has changed")
            realized = actor_request(cases[uid], item["public"]["query"], evidence, protocol, protocol["prompts"]["gepa"])
            if actor_wires[routed["actor_sha256"]] != (uid, realized):
                raise ValueError("Cannot reproduce exact archived selected Actor")
            for arm in ("FULL", "EMPTY", "ROUTED"):
                old = per_uid[uid, arm]
                request_hash = old["actor_sha256"]
                if old["status"] != "OK" or actor_wires[request_hash][0] != uid:
                    raise ValueError("Matched-cap result is unbound")
                if arm != "ROUTED" and actor_wires[request_hash][1] != item[arm]:
                    raise ValueError("Matched-cap endpoint drift")
                grade = build_grade(uid, old["answer"])
                if grade_wires[old["judge"]["request_sha256"]] != (uid, grade):
                    raise ValueError("Matched-cap Judge bytes changed")
                actor = original_answer(path, f"Wave{number}_Actor", uid, actor_wires[request_hash][1])
                judge_reply = original_answer(path, f"Wave{number}_Judge", uid, grade)
                parsed = persist.author.ext.parent.persist.score(cases[uid]["category"], judge_reply)
                if actor != old["answer"] or parsed != old["score"]:
                    raise ValueError("Archived exact answer or grade receipt changed")
            group = group_endpoint(evidence, item["public"]["memories"])
            risk[uid, number] = {
                "selected_fail": routed["score"]["failure_release"],
                "group_fail": per_uid[uid, group]["score"]["failure_release"],
                "group_endpoint": group,
                "same_actor": routed["actor_sha256"] == per_uid[uid, group]["actor_sha256"],
                "physical_receipts": sum(r["unit"]["root_id"] == uid for r in past["ledger"]),
            }
    return risk


def inspect_third_risk(cases, inputs, protocol, judge, bounds, risk):
    """Keep the named third-deployment attempt, including its delivery failure."""
    path = RUN.parent / "persist_repeated_deployment_v1"
    matched_path = RUN.parent / "persist_equal_cap_safety_v1"
    execution = read(path / "EXECUTION.json")
    checkpoint = read(path / "DRAW3.json")
    if (checkpoint["identity"] != execution
            or execution["experiment_sha256"] != sha(read(path / "FROZEN.json"))
            or execution["service_reference_sha256"] !=
                read(matched_path / "EXECUTION.json")["service_reference_sha256"]):
        raise ValueError("Third-draw service or frozen provenance has changed")
    waves = [read(matched_path / f"WAVE{number}.json") for number in (1, 2)]
    actor_times = {r["started_unix"] for w in waves for r in w["ledger"]
                   if r["unit"]["stage"].endswith("_Actor")}
    receipts = {r["request_sha256"]: r for r in checkpoint["ledger"]
                if r["unit"]["stage"] == "Draw3_SelectedActor"}
    if (len(receipts) != 19
            or not all(r["started_unix"] not in actor_times
                       and r["requested_max_tokens"] == ACTOR_CAP
                       and r["automatic_retries"] == 0 for r in receipts.values())):
        raise ValueError("Third-draw physical receipt not distinct or wrong Actor configuration")
    rows = {r["uid"]: r for r in checkpoint["rows"] if r["method"] == "SELECTED_GEPA"}
    if rows.keys() != {uid for uid, _ in risk}:
        raise ValueError("Historical third-draw roster changed")
    actor_wires = manifests(path, "Draw3_SelectedActor")
    grade_wires = manifests(path, "Draw3_Judge")
    build_grade = judge_wire(cases, inputs, judge, bounds)
    roles = Counter()
    states = []
    for uid, row in rows.items():
        item = inputs[uid]
        route_reply = original_answer(path, "Draw3_Route", uid, item["selection_requests"]["query"])
        selection_wire = item["selection_requests"][row["branch"]]
        select_reply = original_answer(path, "Draw3_Select", uid, selection_wire)
        evidence = select(cases[uid], item["public"], route_reply, select_reply)
        wire = actor_request(cases[uid], item["public"]["query"], evidence, protocol, protocol["prompts"]["gepa"])
        key = sha(wire)
        if (actor_wires[key] != (uid, wire) or len(evidence) != row["selected_count"]
                or sha(evidence) != row["selected_sha256"] or receipts[key]["status"] != row["status"]):
            raise ValueError("Third-draw input, exposure, or attempt changed")
        group = group_endpoint(evidence, item["public"]["memories"])
        exact_share = wire == item[group]
        roles[group] += 1
        if row["status"] == "OK":
            answer = original_answer(path, "Draw3_SelectedActor", uid, wire)
            grade = build_grade(uid, answer)
            if grade_wires[row["judge"]["request_sha256"]] != (uid, grade):
                raise ValueError("Third-draw Judge bytes changed")
            judge_reply = original_answer(path, "Draw3_Judge", uid, grade)
            score = persist.author.ext.parent.persist.score(cases[uid]["category"], judge_reply)
            if answer != row["answer"] or score != row["score"]:
                raise ValueError("Third-draw physical answer/grade differs")
        elif row["status"] != "FAILED_DELIVERY_UNKNOWN" or row["score"] is not None:
            raise ValueError("Unexpected third-draw failure in named archived slot")
        states.append((uid, row["status"], group, exact_share))
    return {
        "roots": len(rows),
        "selected_status": Counter(state for _, state, _, _ in states),
        "group_selects": roles,
        "identical_group_positions": sum(shared for *_, shared in states),
        "identical_group_positions_with_unknown_delivery": sum(
            state != "OK" and shared for _, state, _, shared in states
        ),
        "actor_positions_not_covered_by_selected_excluding_rubric": sum(2 - shared for *_, shared in states),
        "reuse_registration_sha256": sha(sorted(states)),
    }


def inspect_prior(inv):
    cases, inputs, protocol, judge, bounds = inv
    risk = inspect_risk(cases, inputs, protocol, judge, bounds)
    pairs = {}
    for track in ("sycophancy", "cross_domain"):
        sample = {uid: [r for (key, _), r in risk.items() if key == uid]
                  for uid in cases if cases[uid]["category"] == track}
        sample = {uid: records for uid, records in sample.items() if records}
        if not all(len(records) == 2 for records in sample.values()):
            raise ValueError("An original risk root lacks one of its two repeats")
        pairs[track] = {
            "roots": len(sample),
            "selected_fail_either_draw": sum(any(r["selected_fail"] for r in v) for v in sample.values()),
            "group_fail_either_draw": sum(any(r["group_fail"] for r in v) for v in sample.values()),
            "sampled_losses": sum(r["selected_fail"] and not r["group_fail"] for v in sample.values() for r in v),
            "sampled_wins": sum(r["group_fail"] and not r["selected_fail"] for v in sample.values() for r in v),
            "selected_group_outcome_vectors_sha256": sha(sample),
        }
    utility_path = RUN.parent / "persist_equal_cap_development_v1"
    utility = read(utility_path / "RESULTS.json")["rows"]
    utility_wires = manifests(utility_path, "Actor")
    for row in utility:
        if row["uid"] not in cases or row["uid"].split("/")[0] != "persistbench":
            raise ValueError("Prior utility roster differs")
        if row["actor_sha256"] and row["arm"] in ("FULL", "EMPTY"):
            if utility_wires[row["actor_sha256"]] != (row["uid"], inputs[row["uid"]][row["arm"]]):
                raise ValueError("Known utility input drift")
    repeat_path = RUN.parent / "persist_repeated_deployment_v1"
    repeats = read(repeat_path / "RESULTS.json")["rows"]
    if any(row["uid"] not in cases for row in repeats):
        raise ValueError("Repeated original deployments outside the exposed roster")
    allocation = sum(1 if c["category"] == "beneficial_memory_usage" else 3 for c in cases.values())
    held = Counter(r["arm"] for r in utility if r["status"] == "FAILED_DELIVERY_UNKNOWN")
    return {
        "scope": "Verified exposed development roster; audit only",
        "tracks": EXPECTED,
        "distinct_source_groups": len(cases),
        "positions_per_arm": allocation,
        "logical_answer_positions": allocation * len(POLICIES),
        "actor_cap": ACTOR_CAP,
        "raw_upper_bound_requests_before_reuse": allocation * 10,
        "plan_pins": {
            "source_roster": sha({uid: c["group_id"] for uid, c in cases.items()}),
            "inputs": sha(inputs),
            "gepa": sha(protocol["prompts"]["gepa"]),
            "judge_envelopes": sha({uid: bounds[uid] for uid in cases}),
        },
        "equal_cap_prior_risk": {
            "validated_task_draws": len(risk), "roots": len({uid for uid, _ in risk}),
            "selected_vs_same_signal_group": pairs,
            "validated_score_positions_for_selected_full_empty": len(risk) * 3,
            "group_identical_to_selected": sum(r["same_actor"] for r in risk.values()),
            "actual_nonempty_subsets_vs_group": sum(not r["same_actor"] for r in risk.values()),
            "group_selects": Counter(r["group_endpoint"] for r in risk.values()),
            "physical_receipts_bound": sum(r["physical_receipts"] for r in risk.values()),
        },
        "equal_cap_prior_utility": {
            "roots": len({r["uid"] for r in utility}),
            "intact_scored_positions": Counter(r["arm"] for r in utility if r["score"] is not None),
            "unknown_delivery_by_arm": held,
        },
        "prior_third_risk_slot": inspect_third_risk(cases, inputs, protocol, judge, bounds, risk),
        "prior_three_draw": {
            "roots": len({r["uid"] for r in repeats}),
            "status_by_policy": {m: Counter(r["status"] for r in repeats if r["method"] == m)
                                 for m in sorted({r["method"] for r in repeats})},
            "matched_rubric_proven": False,
        },
        "new_model_requests": 0,
    }


if __name__ == "__main__":
    assert group_endpoint([], ["original"]) == "EMPTY"
    assert group_endpoint(["original"], ["original"]) == "FULL"
    assert group_endpoint(None, ["original"]) is None
    print(json.dumps(inspect_prior(prepare()), ensure_ascii=False, sort_keys=True, indent=2))
