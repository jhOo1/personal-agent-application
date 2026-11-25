"""Use the same focal intervention with exposed native transfer scorers."""
from collections import Counter

from qamc.common import sha

from audit_archived_policy_edits import policy_only_request
import focal_memory as focal
from run_focal_memory import ACTOR, PLAN, parse_selection
from transfer_edit import RP, archived_answers, cached_dispatch, context, matching_grading_receipts
from transfer_execution import bench_pair, development_roots, grade, persist_pair


def evaluate(benchmark, dispatch):
    roots = development_roots(benchmark)
    roster = {root["uid"]: root for root in roots}
    counts = Counter()
    # Transfer roots have no analysis-group field. Exact public task identity can
    # identify repeats for allocation without using scorer labels or profile metadata.
    foci, pairs = focal.choose_foci([{**root, "group": sha(root["public_task"])} for root in roots])
    packets = {(uid, method, PLAN): focal.packet(root, foci[uid], method)
               for uid, root in roster.items() for method in focal.METHODS}
    jobs = {key: focal.request(payload) for key, payload in packets.items()}
    receipts = cached_dispatch(dispatch, jobs, {}, (), counts)
    policies, wires = {}, {}
    for (uid, method, stage), receipt in receipts.items():
        key = uid, method, stage
        trace = parse_selection(receipt, receipt.get("answer"), packets[key], sha(jobs[key]))
        policies[uid, method] = trace
        if trace["status"] == "OK":
            root = roster[uid]
            mid = root["original_sources"][foci[uid]]["memory_id"]
            wires[uid, method, ACTOR] = policy_only_request(root, {mid: trace["decision"]["policy"]})

    archived = archived_answers(benchmark, roster)
    raw_actors = {sha(row["actor_request"]): row["answer"] for row in archived
                  if row.get("actor_request") and row["actor_status"] == "OK" and row["method"] == RP}
    returned = cached_dispatch(dispatch, wires, raw_actors, (), counts)
    rows = []
    for (uid, method), trace in policies.items():
        actor = returned.get((uid, method, ACTOR), {"status": "NO_VALID_SELECTOR"})
        rows.append({"uid": uid, "method": method, "selector": trace, "score": None,
                     "actor_status": actor["status"], "answer": actor.get("answer"),
                     "actor_sha256": actor.get("request_sha256")})

    cases, protocol, controls = context(benchmark)
    if cases.keys() != roster.keys():
        raise ValueError("Native transfer scoring and public development rosters disagree")
    cache, conflicts = matching_grading_receipts(benchmark, cases, protocol, archived)
    scored = grade(benchmark, rows, cases, protocol,
                   lambda allocated: cached_dispatch(dispatch, allocated, cache, conflicts, counts))
    cells = {(row["uid"], row["method"]): row["score"] for row in (*scored, *controls) if row["score"] is not None}
    pair = bench_pair if benchmark == "BenchPreS" else persist_pair
    return {"assigned": len(roots), "grading_model": protocol["model"],
            "natural_pairs": pairs, "focus_index": foci, "rows": scored,
            "valid_scores": Counter(row["method"] for row in scored if row["score"] is not None),
            "comparisons": {m: pair(m, focal.ISOLATED, cases, cells)
                            for m in (focal.CONTEXTUAL, *sorted({r["method"] for r in controls}))},
            "request_positions": counts}
