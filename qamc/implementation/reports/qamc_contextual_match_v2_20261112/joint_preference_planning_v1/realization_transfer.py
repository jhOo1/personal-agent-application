"""Exercise the same realization interface with the two exposed transfer scorers."""
from collections import Counter

from qamc.common import sha

import decision_realization as method
import run_decision_realization as run
from transfer_edit import archived_answers, cached_dispatch, context, matching_grading_receipts
from transfer_execution import bench_pair, development_roots, grade, persist_pair


def evaluate(benchmark, dispatch):
    roots = development_roots(benchmark)
    roster = {root["uid"] for root in roots}
    counts = Counter()
    selectors = {(root["uid"], "SHARED_USES", run.PLAN): method.selector(root) for root in roots}
    received = cached_dispatch(dispatch, selectors, {}, (), counts)
    prediction = {(uid, name): (rec, rec.get("answer")) for (uid, name, _), rec in received.items()}
    predicted_hashes = {uid: sha(wire) for (uid, _, _), wire in selectors.items()}
    traces, actor_jobs = run.actor_jobs(roots, prediction, {"selector_wires": predicted_hashes})
    actors = cached_dispatch(dispatch, {(uid, arm, run.ACTOR): wire for uid, arm, wire in actor_jobs},
                             {}, (), counts)
    answers = []
    for root in roots:
        uid, trace = root["uid"], traces[root["uid"]]
        for arm in method.METHODS:
            rec = actors.get((uid, arm, run.ACTOR), {"status": "NO_VALID_SELECTOR"})
            row = {"uid": uid, "method": arm, "selector": trace, "actor_status": rec["status"],
                   "actor_sha256": rec.get("request_sha256"), "score": None}
            if rec["status"] == "OK":
                try:
                    shape = arm if trace["route"] == "SEGMENTED" else method.DIRECT
                    answer, added, rejected = method.compile_answer(rec["answer"], trace["uses"], shape)
                    row.update(answer=answer, appended_sources=added, rejected_adjustments=rejected)
                except (KeyError, TypeError, ValueError) as error:
                    row.update(actor_status="INVALID_ACTOR_CONTRACT", error=str(error))
            answers.append(row)

    cases, protocol, controls = context(benchmark)
    if cases.keys() != roster:
        raise ValueError("Transfer scorer and exposed task roster disagree")
    raw, conflicts = matching_grading_receipts(benchmark, cases, protocol, archived_answers(benchmark, roster))
    scored = grade(benchmark, answers, cases, protocol,
                   lambda jobs: cached_dispatch(dispatch, jobs, raw, conflicts, counts))
    cells = {(row["uid"], row["method"]): row["score"] for row in (*scored, *controls) if row["score"] is not None}
    pair = bench_pair if benchmark == "BenchPreS" else persist_pair
    return {"assigned": len(roots), "grading_model": protocol["model"], "rows": scored,
            "valid_scores": Counter(row["method"] for row in scored if row["score"] is not None),
            "comparisons": {baseline: pair(baseline, method.SEGMENTED, cases, cells)
                            for baseline in (method.DIRECT, *sorted({row["method"] for row in controls}))},
            "request_positions": counts}
