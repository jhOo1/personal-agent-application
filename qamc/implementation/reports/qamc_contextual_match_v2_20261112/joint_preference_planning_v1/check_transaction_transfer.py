"""Replay zero-change transaction replies through native transfer adapters."""
from collections import Counter
import json

from qamc.common import sha

from effect_scope_transfer import persist_drafts, transfer
import run_decision_transactions as run


def check(benchmark):
    panel = transfer.development_roots(benchmark)
    roots = {r["uid"]: r for r in panel}
    archive = transfer.archived_answers(benchmark, roots)
    if benchmark == "PersistBench":
        drafts = persist_drafts(panel, archive)
        draft_origin = "VERIFIED_NO_MEMORY"
    else:
        drafts = {r["uid"]: {"answer": r["answer"]} for r in archive
                  if r["method"] == transfer.RP and r["actor_status"] == "OK"}
        draft_origin = "RP_ANSWER_AS_OFFLINE_FIXTURE_ONLY"
    method = run.method
    data, jobs = {}, []
    for uid, item in drafts.items():
        root = roots[uid]
        blocks = {"D1": {"kind": "CONTENT", "lines": [item["answer"]], "anchor": root["public_task"]["query"]}}
        data[uid] = {"blocks": blocks, "positions": 0, "labels": "", "native": {}}
        wires = (method.request(root, blocks), method.linked.request(root, blocks, method.ORDINARY))
        assert wires[0]["messages"][1] == wires[1]["messages"][1]
        public = json.loads(wires[0]["messages"][1]["content"])
        assert public == {"task": root["public_task"], "source_evidence": root["original_sources"], "draft": blocks}
        jobs.extend(zip((uid, uid), (method.ATOMIC, method.ORDINARY), wires, strict=True))

    def fixture(_, work):
        return {(uid, arm): ({"status": "OK", "request_sha256": sha(wire)},
                             json.dumps({"answer": drafts[uid]["answer"]}, ensure_ascii=False)
                             if arm == method.ORDINARY else '{"decisions":[]}')
                for uid, arm, wire in work}

    generated = run.generate(({"roster": {uid: {} for uid in drafts}}, jobs, roots, data, None), fixture)
    answers = []
    for uid, row in generated.items():
        for arm, answer in row["outputs"].items():
            assert answer == drafts[uid]["answer"]
            answers.append({"uid": uid, "method": arm, "answer": answer, "actor_status": "OK", "score": None})
    assert len(answers) == len(drafts) * len(method.MODES)

    cases, protocol, _ = transfer.context(benchmark)
    old_grades, ambiguous = transfer.matching_grading_receipts(benchmark, cases, protocol, archive)
    counters = Counter()

    def fixture_grade(jobs):
        return {key: {"status": "NO_EXACT_ARCHIVED_GRADE", "request_sha256": sha(wire), "answer": None}
                for key, wire in jobs.items()}

    scored = transfer.grade(benchmark, answers, cases, protocol,
                            lambda jobs: transfer.cached_dispatch(fixture_grade, jobs, old_grades, ambiguous, counters))
    return {"exposed_roster": len(panel), "verified_inputs": len(drafts), "draft_origin": draft_origin,
            "compiled_unchanged": len(answers), "new_requests": 0, "new_method_scores": 0,
            "fixture_replayed_scores": Counter(row["method"] for row in scored if row["score"] is not None),
            "available_exact_grade_requests": len(old_grades), "judge_replay_paths": counters}


if __name__ == "__main__":
    print(json.dumps({benchmark: check(benchmark) for benchmark in transfer.PANELS}, ensure_ascii=False, indent=2))
