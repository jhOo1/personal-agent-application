"""Replay or run two matched revisions of the same archived QAMC main answers."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path

from qamc.common import canonical, sha, token_estimate

import main_answer_revision as edit
import run_realization_append_ablation as parent
from settle_decision_realization import checked
from settle_joint_planning import subsets, usage


OUT = parent.OUT.with_name("decision_main_revision_rpeval_v1")
RUN = parent.RUN.with_name(OUT.name)
EDITOR, JUDGE = "MainRevision", parent.JUDGE
MAIN, GATE, RP = parent.MAIN_ONLY, parent.parent.GATE, parent.parent.RP
probe, read, replay = parent.probe, parent.read, parent.v42
joint = parent.parent.joint


def prepare():
    _, rows, _ = checked()
    archive_path = joint.prior.OUT / "FROZEN.json"
    archive = read(archive_path)
    roots = {r["uid"]: r for r in archive["roots"]}
    settled = read(parent.OUT / "SETTLED.json")["rows"]
    if [(r["uid"], r["group"]) for r in settled] != [(r["uid"], r["group"]) for r in rows] or roots.keys() != {r["uid"] for r in rows}:
        raise ValueError("Expected the same exposed main-answer roster")

    requests, packets, omissions = [], {}, {}
    for row in rows:
        uid = row["uid"]
        draft = edit.draft_for(row)
        if draft is None:
            omissions[uid] = "NO_USABLE_PARENT_DRAFT"
            continue
        packet = edit.packet(roots[uid], row, draft)
        if not packet["licenses"]:
            omissions[uid] = "NO_MAIN_LICENSE"
            continue
        packets[uid] = packet
        requests.extend((uid, arm, edit.wire(packet, arm)) for arm in edit.ARMS)
    largest = max(token_estimate(canonical(wire["messages"])) for _, _, wire in requests)
    if largest > 32768:
        raise ValueError("The editor request exceeds the previously checked input size")
    frozen_parent = read(parent.OUT / "FROZEN.json")
    paths = (Path(__file__), Path(edit.__file__), Path(__file__).with_name("MAIN_ANSWER_REVISION_PROTOCOL.md"),
             Path(edit.realization.__file__), Path(edit.planning.__file__),
             Path(edit.oversized.__code__.co_filename), Path(edit.unique_keys.__code__.co_filename),
             Path(replay.__file__), archive_path, parent.OUT / "SETTLED.json",
             parent.parent.OUT / "SETTLED.json", joint.prior.formal.OUT / "PLAN.json")
    spec = {
        "assigned": len(rows), "source_groups": frozen_parent["source_groups"],
        "diagnostic_source_groups": frozen_parent["diagnostic_source_groups"],
        "cap": {EDITOR: len(requests), JUDGE: len(requests)},
        "service_reference_sha256": frozen_parent["service_reference_sha256"],
        "independent_confirmation": False, "max_estimated_input_tokens": largest,
        "screen": {"common_match_fraction": .90, "primary_match_ci_lower": 0,
                   "protected_match_ci_lower": -.02, "protected_bias_ci_upper": .05},
        "wire_sha256": {f"{uid}/{arm}": sha(wire) for uid, arm, wire in requests},
        "draft_sha256": {uid: sha(packet["draft"]) for uid, packet in packets.items()},
        "non_dispatch": omissions,
        "inputs_sha256": {str(p.resolve().relative_to(Path(__file__).resolve().parents[3])): sha(p.read_bytes()) for p in paths},
    }
    return spec, requests, packets, settled, archive


def evaluate(inputs, stage):
    spec, jobs, packets, old_scores, _ = inputs
    revisions = stage(EDITOR, jobs)
    protocol = read(joint.prior.formal.OUT / "PLAN.json")
    author = joint.prior.author_cases(protocol)
    results, grading_jobs = [], []
    for old in old_scores:
        uid = old["uid"]
        actions, native = {}, dict(old["native"])
        results.append({**old, "revisions": actions, "native": native})
        for arm in edit.ARMS:
            if uid in spec["non_dispatch"]:
                reason = spec["non_dispatch"][uid]
                actions[arm] = {"status": reason}
                native[arm] = {**native[MAIN], "reuse": MAIN} if reason == "NO_MAIN_LICENSE" else {"fields": {}, "status": reason}
                continue
            receipt, raw = revisions[uid, arm]
            if receipt["request_sha256"] != spec["wire_sha256"][f"{uid}/{arm}"]:
                raise ValueError("Editor receipt belongs to a different request")
            detail = {"status": receipt["status"], "editor_sha256": receipt["request_sha256"], "raw": raw}
            actions[arm] = detail
            if detail["status"] != "OK":
                native[arm] = {"fields": {}, "status": detail["status"]}
                continue
            detail.update(edit.apply(packets[uid], raw))
            if detail["answer_sha256"] == spec["draft_sha256"][uid]:
                native[arm] = {**native[MAIN], "reuse": MAIN}
                continue
            wire = joint.parent.grade_request(protocol, author[uid], detail["answer"])
            detail["judge_sha256"] = sha(wire)
            grading_jobs.append((uid, arm, wire))
    graded = stage(JUDGE, grading_jobs)
    for row in results:
        for arm, detail in row["revisions"].items():
            if "judge_sha256" not in detail:
                continue
            rec, raw = graded[row["uid"], arm]
            if rec["request_sha256"] != detail["judge_sha256"]:
                raise ValueError("Grade receipt belongs to a different answer")
            row["native"][arm] = joint.parent.parse_grade(rec, raw, row["positions"])
    return results


def compare(spec, rows, ledger):
    panels = subsets(rows, spec)
    panels["less_exposed"] = [row for row in rows if row["less_exposed"]]
    comparisons = {name: {f"{control}/{arm}": {
        "match": replay.paired(panel, control, arm),
        **{field: joint.parent.comparisons.grade_pair(panel, control, arm, field)
           for field in ("OPB", "UPB", "FM", "VG", "full_match")},
        } for control, arm in [(edit.GENERIC, edit.BOUND),
                               *((ref, arm) for ref in (MAIN, GATE, RP) for arm in edit.ARMS)]
        } for name, panel in panels.items()}
    screen, ci = spec["screen"], "95pct_source_bootstrap"
    primary = comparisons["all"][f"{edit.GENERIC}/{edit.BOUND}"]["match"]
    base = f"{MAIN}/{edit.BOUND}"

    def limit(panel, field, side, cut):
        interval = comparisons[panel][base][field].get(ci)
        return bool(interval and (interval[0] >= cut if side == "lower" else interval[1] <= cut))

    gates = {"enough_common_match": primary["valid_cases"] >= spec["assigned"] * screen["common_match_fraction"],
             "beats_equal_budget": bool(primary.get(ci) and primary[ci][0] > screen["primary_match_ci_lower"])}
    for panel in ("all_A", "contains_BC"):
        gates[f"match_{panel}"] = limit(panel, "match", "lower", screen["protected_match_ci_lower"])
    for panel, field in (("all", "OPB"), ("contains_BC", "UPB"), ("all", "FM")):
        gates[field] = limit(panel, field, "upper", screen["protected_bias_ci_upper"])
    return {"assigned": spec["assigned"], "comparisons": comparisons, "numeric_screen": gates,
            "numeric_screen_pass": all(gates.values()),
            "status_by_arm": {arm: Counter(r["revisions"][arm]["status"] for r in rows) for arm in edit.ARMS},
            "usage": {name: usage([rec for rec in ledger if rec["unit"]["stage"] == name])
                      for name in (EDITOR, JUDGE)}, "independent_confirmation": False}


def grade_cache(archive):
    cache = replay.old_receipts(archive)[JUDGE]
    directories = (joint.parent.OUT, joint.OUT, parent.parent.OUT, parent.OUT,
                   parent.OUT.with_name("decision_optional_release_rpeval_v1"))
    for directory in directories:
        for digest, pair in read(directory / f"{JUDGE}_EXACT.json").items():
            if digest != pair[0]["request_sha256"]:
                raise ValueError("A reused grading receipt is linked to the wrong request")
            cache.setdefault(digest, pair)
    return cache


def main(action):
    inputs = prepare()
    spec, jobs, packets, _, archive = inputs
    path = OUT / "FROZEN.json"
    if action in ("check", "freeze"):
        edit.self_test()
        for generic, treatment in zip(jobs[::2], jobs[1::2], strict=True):
            left, right = generic[2], treatment[2]
            assert generic[0] == treatment[0] and left["messages"][1] == right["messages"][1]
            assert left["messages"][0] != right["messages"][0]
            assert {k: v for k, v in left.items() if k != "messages"} == {k: v for k, v in right.items() if k != "messages"}

        def no_op(stage, work):
            assert stage == EDITOR or not work
            return {(uid, arm): ({"request_sha256": sha(wire), "status": "OK"}, '{"edits":[]}')
                    for uid, arm, wire in work}

        rows = evaluate(inputs, no_op)
        for row in rows:
            uid = row["uid"]
            if uid in packets or spec["non_dispatch"][uid] == "NO_MAIN_LICENSE":
                for arm in edit.ARMS:
                    assert row["native"][arm]["fields"] == row["native"][MAIN]["fields"]

        sample_uid, sample_arm, _ = jobs[0]
        sample = packets[sample_uid]
        patch = json.dumps({"edits": [{"sources": [sample["licenses"][0]["memory_id"]],
                                     "before": sample["draft"], "after": sample["draft"] + " offline probe"}]})
        sent_to_judge = []

        def changed(stage, work):
            if stage == EDITOR:
                records = no_op(stage, work)
                rec, _ = records[sample_uid, sample_arm]
                records[sample_uid, sample_arm] = rec, patch
                return records
            assert len(work) == 1 and work[0][:2] == (sample_uid, sample_arm)
            sent_to_judge.extend(work)
            uid, arm, wire = work[0]
            return {(uid, arm): ({"request_sha256": sha(wire), "status": "MOCK_DELIVERY_UNKNOWN"}, None)}

        changed_rows = evaluate(inputs, changed)
        selected = next(row for row in changed_rows if row["uid"] == sample_uid)
        assert selected["revisions"][sample_arm]["status"] == "APPLIED"
        assert not selected["native"][sample_arm]["fields"] and len(sent_to_judge) == 1
        assert not compare(spec, rows, [])["numeric_screen_pass"]
        cache = grade_cache(archive)
        if action == "freeze":
            probe.freeze(path, spec)
        print(json.dumps({"assigned": spec["assigned"], "source_groups": spec["source_groups"],
                          "eligible": len(packets), "non_dispatch": Counter(spec["non_dispatch"].values()),
                          "caps": spec["cap"], "max_estimated_input_tokens": spec["max_estimated_input_tokens"],
                          "verified_prior_judge_wires": len(cache)}, sort_keys=True))
        return

    live = action == "run"
    if read(path) != spec or (live and probe.read_reference()[1] != spec["service_reference_sha256"]):
        raise ValueError("Frozen editor, source or service reference changed")
    reuse = grade_cache(archive)
    probe.OUT, probe.RUN, replay.OUT = OUT, RUN, OUT

    def stage(name, work):
        data = replay.execute_stage(spec, "main", name, work, reuse if name == JUDGE else {}, live)
        if any(rec["status"] == "PENDING_DELIVERY_UNKNOWN" for rec, _ in data.values()):
            raise RuntimeError(f"{name}: delivery still unknown")
        return data

    state = OUT / "RUN_STATE.json"
    if live:
        probe.atomic_json(state, {"state": "RUNNING", "cap": spec["cap"]})
    try:
        rows = evaluate(inputs, stage)
        ledger = [rec for phase in (EDITOR, JUDGE) for rec, _ in probe.stage_receipts(phase).values()]
        counts = Counter(rec["unit"]["stage"] for rec in ledger)
        if any(count > spec["cap"][name] for name, count in counts.items()):
            raise ValueError("Physical request count exceeded the frozen cap")
        probe.freeze(OUT / "SETTLED.json", {"rows": rows, "ledger": ledger})
        probe.freeze(OUT / "RESULTS.json", compare(spec, rows, ledger))
    except (OSError, ValueError, RuntimeError) as error:
        if live:
            probe.atomic_json(state, {"state": "STOPPED", "error": str(error)})
        raise
    if live:
        probe.atomic_json(state, {"state": "COMPLETE", "physical_requests": len(ledger)})


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "freeze", "run", "report"))
    command = parser.parse_args().action
    if command == "check":
        main(command)
    else:
        with probe.runner_lock(RUN / "runner.lock"):
            main(command)
