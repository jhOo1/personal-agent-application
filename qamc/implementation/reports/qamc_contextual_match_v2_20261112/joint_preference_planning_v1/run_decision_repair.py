"""Resume or audit a matched RPEval compare of two executions of one independent review."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path

from qamc.common import canonical, sha, token_estimate

import decision_capability as draft
import decision_repair as repair
import run_decision_capability as prior
from settle_joint_planning import score_matrix, usage


OUT = prior.BASE_OUT.with_name("decision_repair_rpeval_v2")
RUN = prior.BASE_RUN.with_name(OUT.name)
DRAFT, PROPOSE, REVIEW, JUDGE = "RepairDraft", "RepairProposal", "RepairReview", prior.JUDGE
GATE, RP = prior.parent.GATE, prior.parent.RP
probe, read, replay = prior.probe, prior.read, prior.replay


def prepare():
    _, _, roots, roster, _, archive = prior.prepare("pilot")
    smoke = prior.BASE_OUT / "smoke"
    old = read(smoke / "FROZEN.json")["panel"]
    retired = read(prior.BASE_OUT / "pilot/FROZEN.json")
    excluded = set(old.values()) | set(retired["diagnostic_source_groups"])
    groups = {}
    for row in sorted(roster, key=lambda row: sha(["decision-repair-v2", row["uid"]])):
        if row["group"] not in excluded:
            groups.setdefault(row["group"], row["uid"])
    fresh = set(groups.values())
    if len(fresh) != 24 or len(old) != 12:
        raise ValueError("Frozen development panel changed")
    rows = [r for r in roster if r["uid"] in fresh or r["uid"] in old]
    packet = {r["uid"]: roots[r["uid"]] for r in rows}
    source = [Path(__file__), Path(repair.__file__), Path(draft.__file__),
              Path(prior.__file__), Path(draft.planning.__file__), Path(replay.__file__),
              Path(replay.prior.__file__),
              Path(__file__).with_name("DECISION_REPAIR_PROTOCOL.md"),
              prior.BASE_OUT / "pilot/FROZEN.json", prior.parent.OUT / "SETTLED.json",
              smoke / "FROZEN.json", smoke / f"{prior.DRAFT_CALL}_EXACT.json",
              smoke / f"{JUDGE}_EXACT.json",
              prior.parent.joint.prior.OUT / "FROZEN.json",
              prior.parent.joint.prior.formal.OUT / "PLAN.json"]
    base = Path(__file__).resolve().parents[3]
    spec = {
        "panel": {r["uid"]: r["group"] for r in rows},
        "outside_documented_diagnostics": sorted(fresh),
        "caps": {DRAFT: len(fresh), PROPOSE: len(rows), REVIEW: len(rows), JUDGE: 4 * len(rows)},
        "inputs_sha256": {str(path.resolve().relative_to(base)): sha(path.read_bytes()) for path in source},
        "draft_request_sha256": {uid: sha(draft.draft_request(root)) for uid, root in packet.items()},
        "service_reference_sha256": retired["service_reference_sha256"],
        "screen": {"min_common_fraction": .9, "primary_ci_lower": 0, "protected_match_delta": -.02,
                   "protected_loss_delta": .05},
        "independent_confirmation": False,
    }
    return spec, rows, packet, archive


def generate(rows, roots, stage):
    work = [(uid, prior.SHARED, draft.draft_request(root)) for uid, root in roots.items()]
    received = stage(DRAFT, work)
    states, proposals = {}, []
    for uid, arm, wire in work:
        rec, raw = received[uid, arm]
        state = states[uid] = {"draft": rec["status"], "draft_sha256": sha(wire), "answers": {}}
        if rec["status"] != "OK":
            continue
        try:
            blocks = draft.read_draft(roots[uid], raw)
        except (TypeError, ValueError):
            state["draft"] = "INVALID_DRAFT"
            continue
        state["blocks"] = blocks
        state["answers"][repair.DRAFT] = draft.render(blocks)
        proposals.append((uid, arm, repair.proposal_request(roots[uid], blocks)))

    received = stage(PROPOSE, proposals)
    reviews = []
    for uid, arm, wire in proposals:
        state = states[uid]
        rec, raw = received[uid, arm]
        state.update(proposal=rec["status"], proposal_raw=raw, proposal_sha256=sha(wire))
        if rec["status"] != "OK":
            continue
        try:
            edits, invalid = repair.collect_edits(roots[uid], state["blocks"], raw)
        except (TypeError, ValueError):
            state["proposal"] = "INVALID_PROPOSAL"
            continue
        state.update(edits=edits, invalid_edits=invalid)
        answers, _ = repair.compile_review(roots[uid], state["blocks"], edits, {})
        state["answers"][repair.RAW] = answers[repair.RAW]
        if edits:
            reviews.append((uid, arm, repair.review_request(roots[uid], state["blocks"], edits)))
        else:
            state["review"] = "NO_EDIT"
            state["answers"] = answers

    received = stage(REVIEW, reviews)
    for uid, arm, wire in reviews:
        rec, raw = received[uid, arm]
        state = states[uid]
        state.update(review=rec["status"], review_raw=raw, review_sha256=sha(wire))
        if rec["status"] != "OK":
            continue
        try:
            checked, invalid = repair.collect_review(roots[uid], state["blocks"], state["edits"], raw)
        except (TypeError, ValueError):
            state["review"] = "INVALID_REVIEW"
            continue
        if not any(checked.values()):
            state["review"] = "NO_VALID_REVIEW_ROWS"
            continue
        state["answers"], state["trace"] = repair.compile_review(
            roots[uid], state["blocks"], state["edits"], checked)
        state["checks"] = checked
        state["invalid_review_rows"] = invalid
    return [{**{key: row[key] for key in ("uid", "group", "labels", "positions")},
             "native": {m: row["native"][m] for m in (GATE, RP, prior.parent.MAIN)},
             "execution": states[row["uid"]]} for row in rows]


def grade(rows, stage):
    author = prior.parent.joint.prior
    official = read(author.formal.OUT / "PLAN.json")
    refs = author.author_cases(official)
    scorer = prior.parent.joint.parent
    indexes = {row["uid"]: row for row in rows}
    jobs = []
    for row in rows:
        uid, state = row["uid"], row["execution"]
        for arm in repair.MODES:
            row["native"][arm] = {"fields": {}, "status": state.get("review", state.get("proposal", state["draft"]))}
            if arm in state["answers"]:
                jobs.append((uid, arm, scorer.grade_request(official, refs[uid], state["answers"][arm])))
    for (uid, arm), (rec, raw) in stage(JUDGE, jobs).items():
        row = indexes[uid]
        row["native"][arm] = scorer.parse_grade(rec, raw, row["positions"])
        answers = row["execution"]["answers"]
        if arm == repair.WITNESS and answers.get(repair.MODEL) == answers[arm]:
            row["native"][arm]["reuse"] = repair.MODEL


def summarize(spec, rows, ledger):
    fresh_ids = set(spec["outside_documented_diagnostics"])
    fresh = [r for r in rows if r["uid"] in fresh_ids]
    controls = (*repair.MODES[:-1], GATE, RP, prior.parent.MAIN)
    panels = {"primary": fresh, "all": rows,
              "all_A": [r for r in fresh if set(r["labels"]) == {"A"}],
              "contains_BC": [r for r in fresh if any(ch in r["labels"] for ch in "BC")]}
    compare = prior.parent.joint.parent.comparisons.grade_pair
    stats = {key: {arm: {"match": replay.paired(group, arm, repair.WITNESS),
                        **{f: compare(group, arm, repair.WITNESS, f)
                           for f in ("OPB", "UPB", "FM", "VG", "full_match")}}
                    for arm in controls}
             for key, group in panels.items()}
    primary = stats["primary"][repair.MODEL]["match"]
    screen = spec["screen"]
    ci = primary.get("95pct_source_bootstrap")
    protection = [(panel, field) for panel, field in
                  (("all_A", "match"), ("contains_BC", "match"), ("primary", "OPB"),
                   ("contains_BC", "UPB"), ("primary", "FM"))]
    gates = {"enough_paired": primary["valid_cases"] >= screen["min_common_fraction"] * len(fresh),
             "beats_model_review": bool(ci and ci[0] > screen["primary_ci_lower"])}
    for panel, field in protection:
        value = stats[panel][repair.MODEL][field]
        low = field == "match"
        sufficient_pairs = value.get("valid_cases" if low else "n", 0) >= screen["min_common_fraction"] * len(panels[panel])
        delta = value.get("match_delta" if low else "delta")
        gates[f"{panel}/{field}"] = bool(sufficient_pairs and delta is not None and (
            delta >= screen["protected_match_delta"] if low else delta <= screen["protected_loss_delta"]))
    execution = Counter(f"{step}/{r['execution'].get(step, 'NOT_RUN')}"
                        for r in rows for step in ("draft", "proposal", "review"))
    execution.update(outcome for r in rows for outcome in r["execution"].get("trace", {}).values())
    return {"assigned": len(rows), "paired": stats,
            "common": {key: score_matrix(group, (*controls, repair.WITNESS)) for key, group in panels.items()},
            "execution": execution, "screen": gates, "screen_passed": all(gates.values()),
            "usage": {stage: usage([r for r in ledger if r["unit"]["stage"] == stage]) for stage in spec["caps"]}}


def inherited(archive):
    smoke = prior.BASE_OUT / "smoke"
    exact = {DRAFT: read(smoke / f"{prior.DRAFT_CALL}_EXACT.json"),
             PROPOSE: {}, REVIEW: {}, JUDGE: prior.parent.grade_cache(archive)}
    for directory in (prior.parent.OUT, smoke):
        for digest, result in read(directory / f"{JUDGE}_EXACT.json").items():
            exact[JUDGE].setdefault(digest, result)
    for cache in exact.values():
        if any(digest != result[0]["request_sha256"] for digest, result in cache.items()):
            raise ValueError("Inherited receipt has wrong request hash")
    return exact


def run(action, inputs):
    spec, rows, roots, archive = inputs
    live = action == "run"
    if spec != read(OUT / "FROZEN.json") or live and probe.read_reference()[1] != spec["service_reference_sha256"]:
        raise ValueError("Frozen artifacts or the service reference changed")
    exact = inherited(archive)
    probe.OUT, probe.RUN, replay.OUT = OUT, RUN, OUT

    def stage(name, jobs):
        if any(token_estimate(canonical(wire["messages"])) > 32768 for _, _, wire in jobs):
            raise ValueError(f"{name} request exceeds frozen input limit")
        unique = {sha(wire) for _, _, wire in jobs} - exact[name].keys()
        if len(unique) > spec["caps"][name]:
            raise ValueError(f"{name} exceeds physical request cap")
        results = replay.execute_stage(spec, "main", name, jobs, exact[name], live)
        for uid, arm, wire in jobs:
            rec, _ = results[uid, arm]
            if rec["request_sha256"] != sha(wire) or rec["status"] == "PENDING_DELIVERY_UNKNOWN":
                raise RuntimeError(f"{name} has an unmatched or unsettled receipt")
        return results

    state = OUT / "RUN_STATE.json"
    if live:
        probe.atomic_json(state, {"state": "RUNNING", "caps": spec["caps"]})
    try:
        results = generate(rows, roots, stage)
        grade(results, stage)
        ledger = [rec for phase in spec["caps"] for rec, _ in probe.stage_receipts(phase).values()]
        probe.freeze(OUT / "SETTLED.json", {"rows": results, "ledger": ledger})
        probe.freeze(OUT / "RESULTS.json", summarize(spec, results, ledger))
    except (ValueError, RuntimeError, OSError) as exc:
        if live:
            probe.atomic_json(state, {"state": "STOPPED", "error": str(exc)})
        raise
    if live:
        probe.atomic_json(state, {"state": "COMPLETE", "physical_requests": len(ledger)})


def check(inputs):
    spec, rows, roots, archive = inputs
    cached = inherited(archive)[DRAFT]
    smoke = prior.read(prior.BASE_OUT / "smoke/SETTLED.json")
    root = next(roots[r["uid"]] for r in smoke["rows"] if r["uid"].endswith("explicit/054"))
    draft_raw = cached[sha(draft.draft_request(root))][1]
    blocks = draft.read_draft(root, draft_raw)
    data = next(r["execution"] for r in smoke["rows"] if r["uid"] == root["uid"])
    suggestion = draft.read_object(data["bind_raw"])["edits"][0]
    slot = suggestion["block"]
    assert blocks[slot]["kind"] == "CHOICE"
    option = suggestion["value"]
    rejected = blocks[slot]["lines"][0]
    raw = json.dumps({"edits": [{"block": slot, "lines": [rejected, option],
                               "sources": [{"id": suggestion["source_id"], "quote": suggestion["quote"]}]}]})
    edits, invalid = repair.collect_edits(root, blocks, raw)
    assert not invalid and set(edits) == {slot}
    reviewed = {"block": slot, "model_accept": False, "binding": "PARTICIPANT_LIMIT",
                "strength": "HARD", "task_fit": "OK", "before": ["UNSUITABLE"] * len(blocks[slot]["lines"]),
                "after": ["UNSUITABLE", "FEASIBLE"], "scope_quote": None}
    reviews, invalid = repair.collect_review(root, blocks, edits, json.dumps({"reviews": [reviewed]}))
    answers, _ = repair.compile_review(root, blocks, edits, reviews)
    assert not invalid and option in answers[repair.WITNESS] and rejected not in answers[repair.WITNESS]
    assert answers[repair.DRAFT] == answers[repair.MODEL]
    for result in (dict(reviewed, binding="UNSUPPORTED"), dict(reviewed, strength="SOFT", before=[], after=[]),
                   dict(reviewed, binding="COVERED_RECIPIENTS")):
        approved, _ = repair.collect_review(root, blocks, edits, json.dumps({"reviews": [result]}))
        answers, _ = repair.compile_review(root, blocks, edits, approved)
        assert answers[repair.WITNESS] == answers[repair.DRAFT]

    def mock(stage, work):
        replay.manifest("offline", stage, work)
        assert all(token_estimate(canonical(wire["messages"])) <= 32768 for _, _, wire in work)
        result = {}
        for uid, arm, wire in work:
            if stage == DRAFT:
                assert json.loads(wire["messages"][1]["content"]) == {"task": roots[uid]["public_task"]}
                anchor = roots[uid]["public_task"]["query"]
                raw = json.dumps({"blocks": [{"kind": "CONTENT", "target": "task", "anchor": anchor,
                                              "lines": ["Offline contract check."]}]})
                status = "OK"
            elif stage == PROPOSE:
                raw, status = '{"edits":[]}', "OK"
            else:
                assert stage == JUDGE
                raw, status = None, "OFFLINE"
            result[uid, arm] = {"status": status, "request_sha256": sha(wire)}, raw
        return result

    updated = generate(rows, roots, mock)
    grade(updated, mock)
    assert all(set(r["execution"]["answers"]) == set(repair.MODES) for r in updated)
    replay.manifest("offline", REVIEW, [(root["uid"], prior.SHARED, repair.review_request(root, blocks, edits))])
    assert not summarize(spec, updated, [])["screen_passed"]
    assert sum(digest in cached for digest in spec["draft_request_sha256"].values()) == 12
    print(json.dumps({"cases": len(rows), "cached_drafts": 12, "caps": spec["caps"], "new_requests": 0}))


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "freeze", "run", "report"))
    action = parser.parse_args().action
    inputs = prepare()
    if action in ("check", "freeze"):
        check(inputs)
        if action == "freeze":
            probe.freeze(OUT / "FROZEN.json", inputs[0])
    else:
        with probe.runner_lock(RUN / "runner.lock"):
            run(action, inputs)
