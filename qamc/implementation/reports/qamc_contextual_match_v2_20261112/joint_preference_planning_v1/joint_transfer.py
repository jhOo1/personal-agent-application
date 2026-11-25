"""Reuse the exact joint planner and native judges on exposed transfer cases."""
from collections import Counter

from qamc.common import sha

import planning
from run_joint_planning import ACTOR, PLAN, construct_actor_jobs
from transfer_edit import archived_answers, cached_dispatch, context, matching_grading_receipts
from transfer_execution import bench_pair, development_roots, grade, persist_pair


def generate(roots, dispatch):
    packets = {root["uid"]: planning.packet(root) for root in roots}
    plan_jobs = {(uid, "SHARED_PLAN", PLAN): planning.planner_request(payload)
                 for uid, payload in packets.items()}
    allocated = dispatch(plan_jobs)
    planner = {(uid, method): (record, record.get("answer"))
               for (uid, method, _), record in allocated.items()}
    wires = {uid: sha(wire) for (uid, _, _), wire in plan_jobs.items()}
    traces, actor = construct_actor_jobs(packets, planner, wires)
    replies = dispatch({(uid, method, ACTOR): wire for uid, method, wire in actor})
    rows = []
    for uid, trace in traces.items():
        for method in planning.METHODS:
            reply = replies.get((uid, method, ACTOR))
            if reply is None:
                status = trace.get("actor_status", trace["status"])
                rows.append({"uid": uid, "method": method, "actor_status": status, "score": None})
            else:
                rows.append({"uid": uid, "method": method, "actor_status": reply["status"], "score": None,
                             "answer": reply.get("answer"), "actor_sha256": reply["request_sha256"]})
    return traces, rows


def evaluate(benchmark, dispatch):
    """Use the saved roster; evaluation references enter only the scoring stages."""
    roots = development_roots(benchmark)
    counts = Counter()

    def generate_once(jobs):
        return cached_dispatch(dispatch, jobs, {}, (), counts)

    traces, rows = generate(roots, generate_once)
    cases, protocol, controls = context(benchmark)
    authorized = {root["uid"] for root in roots}
    if cases.keys() != authorized:
        raise ValueError("Transfer evaluator must match the complete exposed roster")
    raw, conflicts = matching_grading_receipts(benchmark, cases, protocol, archived_answers(benchmark, authorized))
    scored = grade(benchmark, rows, cases, protocol,
                   lambda jobs: cached_dispatch(dispatch, jobs, raw, conflicts, counts))
    cells = {(row["uid"], row["method"]): row["score"] for row in (*scored, *controls)
             if row["score"] is not None}
    if benchmark == "BenchPreS":
        pair = bench_pair
    elif benchmark == "PersistBench":
        pair = persist_pair
    else:
        raise ValueError("Unsupported transfer benchmark")
    methods = [planning.MODEL, *sorted({row["method"] for row in controls})]
    return {"assigned": len(roots), "grading_model": protocol["model"],
            "independent_confirmation": False, "planning": traces, "rows": scored,
            "valid_scores": Counter(row["method"] for row in scored if row["score"] is not None),
            "comparisons": {m: pair(m, planning.SOLVED, cases, cells) for m in methods},
            "transport_reuse": counts}
