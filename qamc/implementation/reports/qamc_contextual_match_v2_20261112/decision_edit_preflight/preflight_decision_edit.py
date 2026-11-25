"""Verify exact draft reuse and grading wires without dispatching any request."""
from collections import Counter
import json

from qamc.common import canonical, sha, token_estimate

import decision_edit as edit
import run_decision_witness_v45 as witness
import score_task_only as task_only
from transfer_execution import bench_context, development_roots, grading_jobs, persist_context

prior = witness.stage.prior
NOOP = '{"edits":[]}'


def edit_wires(root, answer):
    payload = edit.packet(root, answer)
    edit.source_index(payload["source_evidence"])
    if edit.compile_answer(payload, NOOP)["answer"] != answer:
        raise ValueError("An empty edit changed the original")
    wires = [edit.request(payload, method) for method in edit.METHODS]
    left, right = wires
    if left["messages"][1] != right["messages"][1] or left["messages"][0] == right["messages"][0]:
        raise ValueError("Only the editing instructions may differ")
    tokens = max(token_estimate(canonical(wire["messages"])) for wire in wires)
    if tokens > 32768:
        raise ValueError("Editing prompt exceeds the tested input capacity")
    return payload, wires, tokens


def rpeval():
    original = witness.read(prior.formal.OUT / "PLAN.json")
    native_cases = prior.author_cases(original)
    plan = witness.read(prior.OUT / "FROZEN.json")
    scores = witness.read(task_only.OUT / "FROZEN.json")["ready"]
    responses = task_only.saved_drafts(plan)
    observed, unique, missing = [], set(), Counter()
    for root in plan["roots"]:
        uid = root["uid"]
        draft_hash = sha(prior.task_only_request(root))
        if draft_hash != root["task_wire_sha256"]:
            raise ValueError("Saved source answer used a different current-task message")
        saved = responses[draft_hash]
        if not saved["answer"]:
            missing[saved["record"]["status"] if saved["record"] else "NO_DRAFT_RECEIPT"] += 1
            continue
        answer = saved["answer"]
        payload, wires, tokens = edit_wires(root, answer)
        row = {"uid": uid, "method": prior.GATE, "actor_status": "OK", "answer": answer}
        exact, = prior.formal.grading_jobs(original, [native_cases[uid]], [row])
        if (sha(exact["request"]) != scores[uid]["graded_wire_sha256"]
                or sha(answer) != scores[uid]["answer_sha256"]):
            raise ValueError("Original grading request or answer differs from the archive")
        amended = answer + "\n\n[Offline grading request fixture]"
        changed, = prior.formal.grading_jobs(original, [native_cases[uid]], [{**row, "answer": amended}])
        if sha(changed["request"]) == sha(exact["request"]):
            raise ValueError("Native Judge input must include the realized answer")
        hashes = {method: sha(wire) for method, wire in zip(edit.METHODS, wires, strict=True)}
        unique.update(hashes.values())
        observed.append({"uid": uid, "group": root["group"], "base_answer_sha256": sha(answer),
                         "edit_wires_sha256": hashes, "native_unchanged_sha256": sha(exact["request"]),
                         "evidence_sources": len(payload["source_evidence"]), "max_estimated_input_tokens": tokens})
    return {
        "assigned": len(plan["roots"]), "saved_usable": len(observed),
        "source_groups": len({row["group"] for row in observed}), "missing": missing,
        "max_estimated_input_tokens": max(r["max_estimated_input_tokens"] for r in observed),
        "matched_unchanged_native_request_hashes": len(observed),
        "unique_physical_edit_upper_bound": len(unique),
        "new_native_grade_upper_bound": len(observed) * len(edit.METHODS),
        "new_base_draft_upper_bound": 0, "observed": observed,
    }


def transfer(name):
    roots = development_roots(name)
    cases, protocol, _ = bench_context() if name == "BenchPreS" else persist_context()
    ready = []
    for root in roots:
        body = root["archived_actor_request"]["messages"][1]
        facts = json.loads(body["content"])
        if facts.get("source_evidence") != root["original_sources"]:
            raise ValueError("Cross-benchmark original sources lost")
        # No compatible task-only answer exists on either transfer panel.
        # Never use a synthetic answer or the archived RP answer as a live base draft.
        fixture = "Offline fixture answer only. The current answer contract keeps this sentence intact."
        _, _, inputs = edit_wires(root, fixture)
        ready.append(({"uid": root["uid"], "method": edit.METHODS[0], "actor_status": "OK", "answer": fixture}, inputs))
    jobs, _ = grading_jobs(name, [row for row, _ in ready], cases, protocol)
    expected = 6 if name == "BenchPreS" else 1
    if len(jobs) != len(ready) * expected:
        raise ValueError("Transfer Judge jobs do not cover every ready fixture")
    return {"offline_input_contract_fixtures": len(ready), "offline_grading_contract_fixtures": len(jobs),
            "eligible_task_only_drafts": 0, "new_base_draft_upper_bound": len(ready),
            "max_estimated_fixture_input_tokens": max(tokens for _, tokens in ready)}


if __name__ == "__main__":
    print(json.dumps({"state": "OFFLINE_PREFLIGHT_ONLY", "new_model_calls": 0, "new_method_scores": 0,
                      "RPEval": rpeval(), "BenchPreS": transfer("BenchPreS"), "PersistBench": transfer("PersistBench")},
                     ensure_ascii=False, indent=2))
