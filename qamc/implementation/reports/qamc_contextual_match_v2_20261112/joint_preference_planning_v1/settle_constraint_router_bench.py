"""Compute paired BenchPreS uncertainty and verified task-only routing examples."""
from collections import Counter
import json

from qamc.common import sha

from run_constraint_router_bench import BENCH, OUT, ROUTER, read
from settle_realization_transfer import bench_comparison
from transfer_edit import RP, TASK_ONLY, context


def decisions(score):
    cells = {row["preference"]: (row["appropriate"], row["label"]) for row in score["decisions"]}
    if len(cells) != len(score["decisions"]):
        raise ValueError("Duplicate BenchPreS preference text within a single score")
    return cells


def research_trace(uid, old, new):
    left, right = decisions(old), decisions(new)
    if left.keys() != right.keys() or any(cell[0] != right[pref][0] for pref, cell in left.items()):
        raise ValueError("The two native scores refer to different preference conditions")
    return {"uid": uid, "completeness_delta": new["task_completeness"] - old["task_completeness"],
            "differences": [{"preference": pref, "applicable": cell[0],
                             "RP": cell[1], "no_memory": right[pref][1]}
                            for pref, cell in left.items() if cell[1] != right[pref][1]]}


def settle():
    folder = OUT / BENCH
    terminal = read(folder / "RUN_STATE.json")
    path = folder / "SETTLED.json"
    if terminal["state"] != "COMPLETE":
        raise ValueError("Wait for BenchPreS dispatch and grade settlement")
    saved, frozen = read(path), read(folder / "FROZEN.json")
    cases, protocol, controls = context(BENCH)
    policy = frozen["panels"][BENCH]["policy"]
    if policy.keys() != cases.keys() or len(saved["ledger"]) != terminal["requests"]:
        raise ValueError("BenchPreS terminal roster or receipt count changed")
    score = {(row["uid"], row["method"]): row["score"] for row in (*controls, *saved["rows"])
             if row["score"] is not None}
    for uid, arm in policy.items():
        if (uid, arm) in score:
            score[uid, ROUTER] = score[uid, arm]
    summaries = {}
    for name, cohort in (("all_assigned", cases), ("task_only_branch", {
        uid: case for uid, case in cases.items() if policy[uid] == TASK_ONLY
    })):
        matched = {}
        for arm in sorted({r["method"] for r in controls}):
            pairs = [(case, score[uid, arm], score[uid, ROUTER]) for uid, case in cohort.items()
                     if (uid, arm) in score and (uid, ROUTER) in score]
            matched[arm] = bench_comparison(pairs)
        summaries[name] = {"assigned": len(cohort), "compared": matched}
    detail = []
    for row in saved["rows"]:
        uid = row["uid"]
        if (uid, TASK_ONLY) in score and (uid, RP) in score:
            detail.append(research_trace(uid, score[uid, RP], score[uid, TASK_ONLY]))
    flags = Counter((d["applicable"], d["RP"], d["no_memory"]) for trace in detail for d in trace["differences"])
    return {"settled_sha256": sha(path.read_bytes()), "scoring_model": protocol["model"],
            "requests": terminal["requests"], "new_requests_for_this_analysis": 0,
            "readiness": {"routed_scores": saved["routed_score_coverage"], "assigned": saved["assigned"]},
            "paired_group_uncertainty": summaries, "draft_case_traces": detail,
            "score_transition_counts": [{"applicable": key[0], "RP": key[1], "no_memory": key[2], "count": n}
                                        for key, n in sorted(flags.items())],
            "receipt_and_rating_status": {"draft": Counter(r["actor_status"] for r in saved["rows"]),
                                          "strict_scores_on_draft_branch": sum(r["score"] is not None for r in saved["rows"])},
            "usage": saved["usage"]}


if __name__ == "__main__":
    print(json.dumps(settle(), ensure_ascii=False, indent=2))
