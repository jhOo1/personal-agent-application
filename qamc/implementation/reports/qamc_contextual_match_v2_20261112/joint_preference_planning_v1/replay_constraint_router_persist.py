"""Replay RPEval's predicted-hard-constraint baseline on archived PersistBench answers."""
from collections import Counter
import json

from qamc.common import sha

from effect_scope_transfer import persist_drafts
from transfer_edit import archived_answers, context, matching_grading_receipts, persist
from transfer_execution import development_roots, grading_jobs, persist_pair


ROUTED, RP, ZERO = "RP_IF_PREDICTED_HARD_CONSTRAINT", "RPR_PAPER_FULL", "PB_NO_MEMORY"


def replay():
    benchmark = "PersistBench"
    roots = development_roots(benchmark)
    cases, protocol, controls = context(benchmark)
    archived = archived_answers(benchmark, cases)
    zero_drafts = persist_drafts(roots, archived)
    receipts, conflicts = matching_grading_receipts(benchmark, cases, protocol, archived)
    cached_controls = {(row["uid"], row["method"]): row["score"]
                       for row in controls if row["score"] is not None}

    selected, probes, hashes = [], [], {}
    for root in roots:
        uid = root["uid"]
        policy = root["archived_policy"]
        if ([entry["memory_id"] for entry in policy] != [source["memory_id"] for source in root["original_sources"]]
                or any(entry["policy"] not in ("A", "B", "C") for entry in policy)):
            raise ValueError(f"Invalid archived predictor output for {uid}")
        method = RP if any(entry["policy"] == "C" for entry in policy) else ZERO
        if uid in zero_drafts:
            probes.append({"uid": uid, "method": ZERO, "actor_status": "OK", "answer": zero_drafts[uid]["answer"]})
        hashes[uid] = sha(policy)
        selected.append({"uid": uid, "category": cases[uid]["category"], "choice": method,
                         "predicted_hard": method == RP})

    jobs, _ = grading_jobs(benchmark, probes, cases, protocol)
    verified_zero = {uid for (uid, method, stage), wire in jobs.items() if method == ZERO and stage == persist.STAGE
                     and sha(wire) in receipts and sha(wire) not in conflicts}
    cells = dict(cached_controls)
    for row in selected:
        uid, chosen = row["uid"], row["choice"]
        if chosen == ZERO and uid not in verified_zero:
            row["state"] = "NO_VERIFIED_DRAFT_OR_NATIVE_RECEIPT"
        elif (uid, chosen) not in cells:
            row["state"] = "NO_VALID_NATIVE_GRADE"
        else:
            row["state"] = "OK"
            cells[uid, ROUTED] = cells[uid, chosen]
    comparator_names = (RP, ZERO, "PB_GEPA", "PB_RUBRIC", "GEPA_SELECTED_BOUNDS")
    jointly_valid = {uid: case for uid, case in cases.items() if all((uid, m) in cells
                     for m in (RP, ZERO, ROUTED)) and uid in verified_zero}
    by_category = {}
    for row in selected:
        by_category.setdefault(row["category"], Counter())[row["choice"] + "/" + row["state"]] += 1
    return {"assigned": len(roots), "grade_model": protocol["model"], "physical_requests": 0,
            "verified_author_draft": len(zero_drafts), "exact_native_draft_wires": len(verified_zero),
            "all_three_valid": len(jointly_valid), "control_category_counts": Counter(
                case["category"] for case in jointly_valid.values()),
            "availability": Counter(row["state"] for row in selected), "by_category": by_category,
            "paired": {name: persist_pair(name, ROUTED, cases, cells) for name in comparator_names},
            "strict_three_way": {name: persist_pair(name, ROUTED, jointly_valid, cells) for name in (RP, ZERO)},
            "policy_sha256": hashes, "rows": selected}


if __name__ == "__main__":
    print(json.dumps(replay(), ensure_ascii=False, indent=2))
