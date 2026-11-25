"""Verify draft/edit/score wiring on both exposed transfer panels without API access."""
from collections import Counter
import json

from qamc.common import sha

import transfer_edit as t
from transfer_grading import analyze as verify_archived_grades


def verify(benchmark):
    cases, protocol, _ = t.context(benchmark)
    panel = t.development_roots(benchmark)
    archived = t.archived_answers(benchmark, cases)
    originals = {r["uid"]: r["answer"] for r in archived if r["method"] == t.RP and r["actor_status"] == "OK"}
    if originals.keys() != cases.keys():
        raise ValueError("Every paired transfer fixture needs a verified archived RP answer")
    grades, ambiguous = t.matching_grading_receipts(benchmark, cases, protocol, archived)
    observed = {sha(r["actor_request"]) for r in archived if r.get("actor_request") and r["actor_status"] == "OK"}
    planned = {sha(wire) for wire in t.draft_wires(panel).values()}
    simulated = Counter()

    def replay(jobs):
        replies = {}
        for key, wire in jobs.items():
            uid, method, stage = key
            simulated[stage] += 1
            if stage == t.DRAFT:
                if json.loads(wire["messages"][1]["content"])["source_evidence"]:
                    raise ValueError("Draft has historical evidence")
                text = originals[uid]
            elif stage == t.EDIT:
                packet = json.loads(wire["messages"][1]["content"])
                if packet["original_answer"] != originals[uid]:
                    raise ValueError("The editor did not receive its exact saved draft fixture")
                text = '{"edits":[]}'
            else:
                if sha(wire) in grades:
                    raise ValueError("An exact archived grade was not reused")
                text = None
            replies[key] = {"status": "OK" if text is not None else "ARCHIVED_GRADE_UNAVAILABLE",
                            "request_sha256": sha(wire), "answer": text}
        return replies

    answers, result = t.evaluate(benchmark, replay)
    valid_reference = {"BenchPreS": 46, "PersistBench": 57}[benchmark]
    if result["valid_new_native_rows"] != dict.fromkeys((*t.edit.METHODS, t.TASK_ONLY), valid_reference):
        raise ValueError("Empty-edit replay did not recover the three exact archived grade paths")
    if len(answers) != 3 * len(panel) or any(r["answer"] != originals[r["uid"]] for r in answers):
        raise ValueError("An empty edit changed the visible answer")
    return {
        "frozen_exposed_roots": len(panel), "exact_existing_drafts_found": len(planned & observed),
        "distinct_drafts_needed_by_a_new_run": len(planned - observed),
        "verified_unique_old_grading_wires": len(grades), "conflicting_old_wires": len(ambiguous),
        "offline_compiled_answer_fixtures": len(answers),
        "old_valid_rp_grade_replays_per_method": valid_reference,
        "fixture_archived_grade_reuse": result["request_positions"]["archived_grade_reuse"],
        "simulated_noncache_positions": simulated, "new_model_requests": 0, "new_method_scores": 0,
    }


if __name__ == "__main__":
    old = verify_archived_grades()
    assert old["new_model_calls"] == 0 and old["unseen_sources_read"] == 0
    print(json.dumps({name: verify(name) for name in t.PANELS}, ensure_ascii=False, indent=2))
