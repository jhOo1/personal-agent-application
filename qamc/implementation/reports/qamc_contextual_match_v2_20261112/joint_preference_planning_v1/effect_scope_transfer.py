"""Use the same effect compiler and the existing benchmark-native Judge adapters."""
from collections import Counter, defaultdict
import json

from qamc.common import sha
from qamc.contextual_match.persist_author_bridge import PersistAuthorBridge

import run_effect_scope as core
import transfer_edit as transfer


def persist_drafts(panel, archived):
    """Recover exact no-memory author drafts with their physical Actor receipts."""
    output = transfer.persist.AUTHOR_OUT
    plan = transfer.read(output / "PLAN.json")
    state = transfer.read(output / "RUN_STATE.json")
    if state["phase"] != "AUTHOR_CONTROLS_TERMINAL" or set(state["completed_waves"]) != set(range(len(plan["waves"]))):
        raise ValueError("PersistBench no-memory archive has not settled")
    known = {root["uid"]: root for root in panel}
    cases = {case["uid"]: case for case in plan["cases"] if case["uid"] in known}
    bridge = PersistAuthorBridge(transfer.persist.author.parent.persist.UP)
    if bridge.manifest() != plan["author_manifest"]:
        raise ValueError("PersistBench author's locked assets changed")
    runtime = transfer.bench.ROOT / "runs" / output.parent.name / output.name
    receipts = defaultdict(list)
    for path in (runtime / "qwen" / "outputs").glob("*.json"):
        record = transfer.read(path)
        unit = record["unit"]
        if (unit["stage"] == "Actor" and unit["method"] == "PB_NO_MEMORY"
                and unit["root_id"] in known and record["status"] == "OK"):
            receipts[unit["root_id"], record["request_sha256"]].append(record)
    reply = {}
    for row in archived:
        if row["method"] != "PB_NO_MEMORY" or row["actor_status"] != "OK":
            continue
        uid = row["uid"]
        root, task = known[uid], transfer.development.task_for(cases[uid])
        expected = bridge.actor(task, "PB_NO_MEMORY", "", None)
        wire = expected["request"]
        if (root["public_task"] != {"query": task.query, "current_context": "", "facts": []}
                or wire != row["actor_request"] or expected["view"] != row["view"]
                or expected["view"]["original_memory_texts"]
                or sha(wire) != row["actor_request_sha256"]):
            raise ValueError(f"Unverified task-only wire for {uid}")
        matches = [rec for rec in receipts[uid, sha(wire)] if rec["response"]["answer"] == row["answer"]]
        if not matches or uid in reply:
            raise ValueError(f"Unverified or duplicate no-memory answer for {uid}")
        reply[uid] = {"answer": row["answer"], "sha256": sha(wire), "receipt": matches[0]}
    return reply


def generate(panel, drafts, dispatch):
    """Use the same generation and edit compiler as RPEval on the supplied drafts."""
    roots = {row["uid"]: row for row in panel}
    roster, data, jobs = {}, {}, []
    for uid, item in drafts.items():
        root = roots[uid]
        blocks = {"D1": {"kind": "CONTENT", "lines": [item["answer"]], "anchor": root["public_task"]["query"]}}
        roster[uid] = {"draft_origin": item["sha256"]}
        data[uid] = {"blocks": blocks, "positions": 0, "labels": "", "native": {}}
        jobs.extend((
            (uid, core.method.STRUCTURAL, core.method.request(root, blocks)),
            (uid, core.method.ORDINARY, core.method.linked.request(root, blocks, core.method.ORDINARY)),
        ))

    def stage(name, work):
        received = transfer.checked_dispatch(dispatch, {(uid, arm, name): wire for uid, arm, wire in work})
        return {(uid, arm): (record, record.get("answer")) for (uid, arm, _), record in received.items()}

    generated = core.generate(({"roster": roster}, jobs, data, roots, None, None), stage)
    answers = []
    for uid, row in generated.items():
        for arm in core.method.MODES:
            physical = core.method.STRUCTURAL if arm == core.method.SCOPED else arm
            state = row["attempts"][physical]
            answers.append({"uid": uid, "method": arm, "actor_status": state["status"], "score": None,
                            "answer": row["outputs"].get(arm), "actor_sha256": state["request_sha256"],
                            "draft_sha256": row["draft_origin"]})
    return answers, generated


def verify(benchmark):
    cases, protocol, _ = transfer.context(benchmark)
    panel = transfer.development_roots(benchmark)
    archived = transfer.archived_answers(benchmark, cases)
    if benchmark == "PersistBench":
        drafts = persist_drafts(panel, archived)
        real_reuse = len(drafts)
    else:
        expected = {sha(wire) for wire in transfer.draft_wires(panel).values()}
        saved = {sha(row["actor_request"]) for row in archived
                 if row["actor_status"] == "OK" and row.get("actor_request")}
        if expected & saved:
            raise ValueError("A newly available exact BenchPreS draft requires separate receipt verification")
        drafts = {r["uid"]: {"answer": r["answer"], "sha256": r["actor_request_sha256"]}
                  for r in archived if r["method"] == transfer.RP and r["actor_status"] == "OK"}
        real_reuse = 0  # RP answers with history are grading fixtures only.
    old_grades, ambiguous = transfer.matching_grading_receipts(benchmark, cases, protocol, archived)

    def fixture(jobs):
        replies = {}
        for (uid, arm, stage), wire in jobs.items():
            packet = json.loads(wire["messages"][1]["content"])
            root = roots[uid]
            if (stage != core.STAGE or set(packet) != {"task", "source_evidence", "draft"}
                    or packet["task"] != root["public_task"]
                    or packet["source_evidence"] != root["original_sources"]
                    or packet["draft"]["D1"]["lines"] != [drafts[uid]["answer"]]):
                raise ValueError("Transfer generation includes an unexpected input")
            raw = (json.dumps({"answer": drafts[uid]["answer"]}, ensure_ascii=False) if arm == core.method.ORDINARY
                   else '{"effects":[],"edits":[]}')
            replies[uid, arm, stage] = {"status": "OK", "request_sha256": sha(wire), "answer": raw}
        return replies

    def reject_new_grade(jobs):
        return {key: {"status": "NO_EXACT_ARCHIVED_GRADE", "request_sha256": sha(wire), "answer": None}
                for key, wire in jobs.items()}

    roots = {r["uid"]: r for r in panel}
    answers, traces = generate(panel, drafts, fixture)
    if any(row["answer"] != drafts[row["uid"]]["answer"] for row in answers):
        raise ValueError("Empty edits changed a fixture draft")
    counts = Counter()
    replayed = transfer.grade(benchmark, answers, cases, protocol,
                              lambda jobs: transfer.cached_dispatch(reject_new_grade, jobs, old_grades, ambiguous, counts))
    return {"exposed_cases": len(roots), "verified_no_memory_drafts": real_reuse,
            "missing_for_original_panel": len(roots) - real_reuse,
            "fixture_compiled_answers": len(answers), "fixture_requests": len(traces) * 2,
            "archived_request_hashes_available": len(old_grades),
            "old_value_replays": Counter(row["method"] for row in replayed if row["score"] is not None),
            "real_draft_uids": sorted(drafts) if real_reuse else [],
            "new_model_requests": 0, "new_method_scores": 0}


if __name__ == "__main__":
    print(json.dumps({name: verify(name) for name in transfer.PANELS}, ensure_ascii=False, indent=2))
