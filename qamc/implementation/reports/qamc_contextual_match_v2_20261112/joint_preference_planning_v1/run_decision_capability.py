"""Run a two-call structured capability contrast on already exposed RPEval data."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path

from qamc.common import canonical, sha, token_estimate

import audit_main_guard_router as guard
import decision_capability as method
import replay_decision_capabilities as sample
import run_main_answer_revision as parent
from settle_joint_planning import score_matrix, subsets, usage


BASE_OUT = parent.OUT.with_name("decision_capability_rpeval_v1")
BASE_RUN = parent.RUN.with_name(BASE_OUT.name)
DRAFT_CALL, BIND_CALL, JUDGE = "CapabilityDraft", "CapabilityBind", parent.JUDGE
SHARED = "SHARED"
probe, read, replay = parent.probe, parent.read, parent.replay


def prepare(part):
    archive_path = parent.joint.prior.OUT / "FROZEN.json"
    archive = read(archive_path)
    roster = read(parent.OUT / "SETTLED.json")["rows"]
    roots = {r["uid"]: r for r in archive["roots"]}
    if len(roots) != 233 or roots.keys() != {row["uid"] for row in roster}:
        raise ValueError("RPEval exposed roster changed")
    if part == "smoke":
        chosen = {row["uid"] for row in sample.select(roster, n=12)}
        roster = [row for row in roster if row["uid"] in chosen]
    parent_routes = {r["uid"]: r["selection"] for r in read(parent.parent.parent.OUT / "SETTLED.json")["rows"]}
    exposed = {r["uid"]: roots[r["uid"]] for r in roster}
    jobs = [(uid, SHARED, method.draft_request(root)) for uid, root in exposed.items()]
    if any(token_estimate(canonical(wire["messages"])) > 32768 for _, _, wire in jobs):
        raise ValueError("Draft request exceeds the input cap")
    paths = (Path(__file__), Path(method.__file__), Path(method.planning.__file__),
             Path(sample.__file__), Path(replay.__file__), Path(replay.prior.__file__),
             Path(__file__).with_name("DECISION_CAPABILITY_PROTOCOL.md"),
             archive_path, parent.OUT / "SETTLED.json", parent.OUT / "FROZEN.json",
             parent.parent.parent.OUT / "SETTLED.json", parent.joint.prior.formal.OUT / "PLAN.json")
    root_dir = Path(__file__).resolve().parents[3]
    spec = {
        "part": part, "panel": {row["uid"]: row["group"] for row in roster},
        "draft_wire": {uid: sha(wire) for uid, _, wire in jobs},
        "cap": {DRAFT_CALL: len(roster), BIND_CALL: len(roster), JUDGE: 3 * len(roster)},
        "service_reference_sha256": read(parent.OUT / "FROZEN.json")["service_reference_sha256"],
        "inputs_sha256": {str(p.resolve().relative_to(root_dir)): sha(p.read_bytes()) for p in paths},
        "diagnostic_source_groups": read(parent.OUT / "FROZEN.json")["diagnostic_source_groups"],
        "independent_confirmation": False,
        "screen": {"primary_coverage": .90, "primary_lower": 0,
                   "protected_match_lower": -.02, "protected_loss_upper": .05},
        "smoke_min_valid": 10,
    }
    return spec, jobs, exposed, roster, parent_routes, archive


def analyze(inputs, stage):
    _, jobs, roots, old, parent_routes, _ = inputs
    drafts = stage(DRAFT_CALL, jobs)
    data, proposals = {}, []
    for uid, _, wire in jobs:
        rec, raw = drafts[uid, SHARED]
        if rec["request_sha256"] != sha(wire):
            raise ValueError("Draft receipt for a different request")
        state = data[uid] = {"draft_status": rec["status"], "draft_raw": raw, "draft_sha256": sha(wire), "answers": {}}
        if rec["status"] != "OK":
            continue
        try:
            blocks = method.read_draft(roots[uid], raw)
        except (ValueError, TypeError, KeyError):
            state["draft_status"] = "INVALID_DRAFT"
            continue
        state["blocks"] = blocks
        state["answers"][method.DRAFT] = {"answer": method.render(blocks), "status": "OK"}
        proposal = method.propose_request(roots[uid], blocks)
        if token_estimate(canonical(proposal["messages"])) > 32768:
            state["bind_status"] = "INPUT_CAP"
            continue
        state["bind_sha256"] = sha(proposal)
        proposals.append((uid, SHARED, proposal))
    received = stage(BIND_CALL, proposals)
    for uid, _, wire in proposals:
        rec, raw = received[uid, SHARED]
        if rec["request_sha256"] != sha(wire):
            raise ValueError("Binder receipt for a different request")
        state = data[uid]
        state.update(bind_status=rec["status"], bind_raw=raw)
        if rec["status"] != "OK":
            continue
        try:
            for arm in (method.GENERIC, method.BOUND):
                state["answers"][arm] = {
                    "status": "OK", **method.compile_edits(roots[uid], state["blocks"], raw, arm)}
        except (ValueError, TypeError, KeyError):
            state["bind_status"] = "INVALID_PROPOSAL"
            for arm in (method.GENERIC, method.BOUND):
                state["answers"][arm] = {**state["answers"][method.DRAFT], "status": "REUSE_DRAFT_INVALID_PROPOSAL"}

    official = read(parent.joint.prior.formal.OUT / "PLAN.json")
    author = parent.joint.prior.author_cases(official)
    score_jobs, rows = [], []
    for record in old:
        uid = record["uid"]
        state = data[uid]
        native = dict(record["native"])
        source = parent_routes[uid]
        if source["status"] == "OK":
            anchor = parent.MAIN if any(x["use"] == "GUARD" for x in source["uses"]) else guard.TASK
            native[guard.GUARD_ROUTE] = native[anchor]
        else:
            native[guard.GUARD_ROUTE] = {"fields": {}, "status": "NO_ARCHIVED_SELECTION"}
        rows.append({**{k: record[k] for k in ("uid", "group", "positions", "labels", "less_exposed")},
                     "execution": state, "native": native})
        for arm in method.MODES:
            response = state["answers"].get(arm)
            native[arm] = {"fields": {}, "status": state.get("bind_status", state["draft_status"])}
            if response is None:
                continue
            wire = parent.joint.parent.grade_request(official, author[uid], response["answer"])
            response["judge_sha256"] = sha(wire)
            score_jobs.append((uid, arm, wire))
    scores = stage(JUDGE, score_jobs)
    by_uid = {row["uid"]: row for row in rows}
    for uid, arm, wire in score_jobs:
        rec, raw = scores[uid, arm]
        if rec["request_sha256"] != sha(wire):
            raise ValueError("Scoring receipt for a different answer")
        row = by_uid[uid]
        row["native"][arm] = parent.joint.parent.parse_grade(rec, raw, row["positions"])
        generic = row["execution"]["answers"].get(method.GENERIC, {})
        if arm == method.BOUND and generic.get("judge_sha256") == sha(wire):
            row["native"][arm]["reuse"] = method.GENERIC
    return rows


def advancement(spec, pairs):
    thresholds = spec["screen"]
    ci = "95pct_source_bootstrap"
    primary = pairs["all"][method.GENERIC]["match"]
    gates = {
        "enough_common_match": primary["valid_cases"] >= thresholds["primary_coverage"] * len(spec["panel"]),
        "beats_equal_budget": bool(primary.get(ci) and primary[ci][0] > thresholds["primary_lower"]),
    }
    for panel in ("all_A", "contains_BC"):
        field = pairs[panel][parent.MAIN]["match"]
        gates[panel] = bool(field.get(ci) and field[ci][0] >= thresholds["protected_match_lower"])
    for panel, key in (("all", "OPB"), ("contains_BC", "UPB"), ("all", "FM")):
        field = pairs[panel][parent.MAIN][key]
        gates[key] = bool(field.get(ci) and field[ci][1] <= thresholds["protected_loss_upper"])
    return gates


def summarize(spec, rows, ledger):
    arms = (*method.MODES, parent.GATE, parent.RP, guard.GUARD_ROUTE, parent.MAIN)
    differences = Counter()
    for row in rows:
        state = row["execution"]
        differences[f"draft/{state['draft_status']}"] += 1
        differences[f"binder/{state.get('bind_status', 'NOT_RUN')}"] += 1
        answers = state["answers"]
        if method.GENERIC in answers and method.BOUND in answers:
            differences["programs_diverge"] += answers[method.GENERIC]["answer"] != answers[method.BOUND]["answer"]
            for reason in answers[method.BOUND].get("rejected", []):
                differences[reason["reason"]] += 1
    panels = subsets(rows, spec)
    panels["less_exposed"] = [row for row in rows if row["less_exposed"]]
    pairs = {name: {control: {
        "match": replay.paired(panel, control, method.BOUND),
        **{f: parent.joint.parent.comparisons.grade_pair(panel, control, method.BOUND, f)
           for f in ("OPB", "UPB", "FM", "VG", "full_match")},
    } for control in arms if control != method.BOUND} for name, panel in panels.items()}
    screen = advancement(spec, pairs) if spec["part"] == "pilot" else {}
    smoke_counts = {
        "valid_contract_and_match": sum(
            row["execution"].get("bind_status") == "OK"
            and all(bool(row["native"][m]["fields"].get("match")) for m in (method.GENERIC, method.BOUND))
            for row in rows),
        "arm_answers_differ": differences["programs_diverge"],
    } if spec["part"] == "smoke" else {}
    return {"assigned": len(rows), "execution": differences, "paired": pairs,
            "common": {name: score_matrix(panel, arms) for name, panel in panels.items()},
            "numeric_screen": screen, "numeric_screen_pass": bool(screen) and all(screen.values()),
            "smoke_counts": smoke_counts,
            "smoke_pass": bool(smoke_counts)
            and smoke_counts["valid_contract_and_match"] >= spec["smoke_min_valid"]
            and smoke_counts["arm_answers_differ"] > 0,
            "usage": {name: usage([rec for rec in ledger if rec["unit"]["stage"] == name])
                      for name in spec["cap"]}, "independent_confirmation": False}


def check(inputs):
    spec, jobs, roots, _, _, _ = inputs
    uid = jobs[0][0]
    root = roots[uid]
    anchor = next(s for s in method.task_text(root["public_task"]) if s.strip())
    quote_id, passage = next((item["memory_id"], phrase)
                             for item in root["original_sources"] for phrase in method.user_source(item["text"])
                             if phrase.strip())
    blocks = {"D1": {"kind": "CHOICE", "target": "affected group", "anchor": anchor,
                     "lines": ["First existing option.", "Second existing option."]},
              "D2": {"kind": "SIGNATURE", "target": "sender", "anchor": anchor, "lines": ["Sender"]}}
    op = {"block": "D2", "operation": "REPLACE", "source_id": quote_id, "quote": passage[:250],
          "target": "sender", "relation": "DIRECT", "extent": "SUPPORT", "source_kind": "ADDRESS",
          "value": "Courtesy name"}

    def run_edits(mode, operations):
        return method.compile_edits(root, blocks, json.dumps({"edits": operations}), mode)

    assert run_edits(method.BOUND, [op])["answer"] == method.render(blocks)
    assert run_edits(method.GENERIC, [op])["changed_slots"] == ["D2"]
    choice = dict(op, block="D1", operation="EXCLUDE", source_kind="CHOICE",
                  target="affected group", value=[1])
    assert run_edits(method.BOUND, [choice])["rejected"][0]["reason"] == "EXCLUSION_WITHOUT_REQUIREMENT"
    assert run_edits(method.BOUND, [dict(choice, extent="REQUIRE")])["changed_slots"] == ["D1"]
    assert run_edits(method.BOUND, [dict(choice, extent="REQUIRE", value=[1, 2])])["answer"] == method.render(blocks)
    assert run_edits(method.BOUND, [dict(choice, operation="ADD_OPTION", value="New suitable option.")])["answer"].startswith(
        "First existing option.\n\nSecond existing option.\n\nNew suitable option.")
    assert run_edits(method.BOUND, [dict(choice, quote="invalid quote not in source")])["changed_slots"] == []
    for raw in ('{"edits":[], "edits":[]}', '{"edits":[]} trailing'):
        try:
            method.compile_edits(root, blocks, raw, method.BOUND)
        except ValueError:
            continue
        raise AssertionError("Ambiguous output passed the edit contract")
    assert method.read_object('```json\n{"edits":[]}\n```') == {"edits": []}
    for key, _, wire in jobs:
        task = roots[key]["public_task"]
        assert set(task) <= {"query", "facts", "current_context"} and "query" in task
        assert json.loads(wire["messages"][1]["content"]) == {"task": task}
    # Read-only complete three-stage replay over the fixed roster; no live dispatcher is reachable.
    def simulated(name, work):
        replay.manifest("offline", name, work)
        output = {}
        for case, arm, wire in work:
            answer = '{"edits":[]}' if name == BIND_CALL else None
            status = "OK" if name != JUDGE else "OFFLINE"
            if name == DRAFT_CALL:
                quote = next(s for s in method.task_text(roots[case]["public_task"]) if s.strip())[:180]
                answer = json.dumps({"blocks": [{"kind": "CONTENT", "target": "task",
                                                  "anchor": quote, "lines": ["Offline contract witness."]}]})
            output[case, arm] = {"status": status, "request_sha256": sha(wire)}, answer
        return output
    rows = analyze(inputs, simulated)
    assert len(rows) == len(spec["panel"])
    assert all(len({r["execution"]["answers"][arm]["answer"] for arm in method.MODES}) == 1 for r in rows)
    assert not summarize(spec, rows, [])["numeric_screen_pass"]
    return {"checked_roots": len(rows), "caps": spec["cap"], "new_requests": 0}


def main(action, part):
    out, folder = BASE_OUT / part, BASE_RUN / part
    inputs = prepare(part)
    spec, _, _, _, _, archive = inputs
    path = out / "FROZEN.json"
    if action in ("check", "freeze"):
        print(json.dumps(check(inputs), sort_keys=True))
        if action == "freeze":
            probe.freeze(path, spec)
        return
    live = action == "run"
    if read(path) != spec or (live and probe.read_reference()[1] != spec["service_reference_sha256"]):
        raise ValueError("Frozen capability run inputs or gateway changed")
    cache = parent.grade_cache(archive)
    for digest, value in read(parent.OUT / f"{JUDGE}_EXACT.json").items():
        cache.setdefault(digest, value)
    inherited = {DRAFT_CALL: {}, BIND_CALL: {}, JUDGE: cache}
    if part == "pilot":
        smoke = BASE_OUT / "smoke"
        if (read(smoke / "RUN_STATE.json")["state"] != "COMPLETE"
                or not read(smoke / "RESULTS.json")["smoke_pass"]):
            raise ValueError("The engineering smoke has not passed")
        for phase in (DRAFT_CALL, BIND_CALL, JUDGE):
            for digest, value in read(smoke / f"{phase}_EXACT.json").items():
                if digest != value[0]["request_sha256"]:
                    raise ValueError("Smoke cache hash differs from its receipt")
                inherited[phase].setdefault(digest, value)
    probe.OUT, probe.RUN, replay.OUT = out, folder, out

    def stage(name, jobs):
        observed = replay.execute_stage(spec, part, name, jobs, inherited[name], live)
        if any(rec["status"] == "PENDING_DELIVERY_UNKNOWN" for rec, _ in observed.values()):
            raise RuntimeError(f"Unsettled {name} delivery")
        return observed

    state = out / "RUN_STATE.json"
    if live:
        probe.atomic_json(state, {"state": "RUNNING", "cap": spec["cap"]})
    try:
        rows = analyze(inputs, stage)
        ledger = [rec for phase in spec["cap"] for rec, _ in probe.stage_receipts(phase).values()]
        totals = Counter(rec["unit"]["stage"] for rec in ledger)
        if any(n > spec["cap"][name] for name, n in totals.items()):
            raise ValueError("Exceeded frozen physical request allocation")
        probe.freeze(out / "SETTLED.json", {"rows": rows, "ledger": ledger})
        probe.freeze(out / "RESULTS.json", summarize(spec, rows, ledger))
    except (ValueError, OSError, RuntimeError) as error:
        if live:
            probe.atomic_json(state, {"state": "STOPPED", "error": str(error)})
        raise
    if live:
        probe.atomic_json(state, {"state": "COMPLETE", "physical_requests": len(ledger)})


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "freeze", "run", "report"))
    parser.add_argument("part", choices=("smoke", "pilot"))
    args = parser.parse_args()
    if args.action == "check":
        main(args.action, args.part)
    else:
        with probe.runner_lock(BASE_RUN / args.part / "runner.lock"):
            main(args.action, args.part)
