"""Count prediction-conditioned history exposure in the existing multi roster."""
from collections import Counter, defaultdict
import json
from pathlib import Path

from qamc.common import sha

HERE = Path(__file__).resolve().parent.parent


def read(path):
    return json.loads((HERE / path).read_text())


def audit():
    endpoints = {r["uid"]: r for r in read("ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]}
    formal = "rpeval_formal_multi_coverage_v1"
    ranks = read(f"{formal}/RPR_RANK_FUSION_AUDIT_300.json")["rows"]
    history = {r["uid"]: r for r in read(f"{formal}/RESULT_ROWS.json") if r["method"] == "RPR_PAPER_FULL"}
    counts, visible_rp_policy = defaultdict(Counter), Counter()
    resolved = set()
    for row in ranks:
        uid = row["uid"]
        primary = endpoints[uid]
        route = primary["old_route"]
        if route == "ARCHIVED_ESTIMATE_OR_ACTOR_UNAVAILABLE":
            continue
        ipe = row["policies"]["IPE_ONLY"]["policy"]
        labels = row["author_labels"]
        on = route == "REUSE_RP"
        if not (labels == primary["labels"] and len(ipe) == len(labels) and on == ("C" in ipe)):
            raise ValueError("Archived IPE-C assignment differs from rank-front prediction")
        resolved.add(uid)
        exposure = "history" if on else "task_only"
        counts[exposure]["tasks"] += 1
        rp_policy = {}
        if on:
            answer = history[uid]
            wire = answer["actor_request"]
            if sha(wire) != answer["actor_request_sha256"] or sha(answer["answer"].strip()) != primary["ipe_c"]["answer_sha256"]:
                raise ValueError("History endpoint does not verify")
            packet = json.loads(wire["messages"][1]["content"])
            rp_policy = {c["memory_id"]: c["policy"] for c in packet["preference_use_policy"]}
            visible = {s["memory_id"] for s in packet["source_evidence"]}
            if visible != set(rp_policy) or visible != {f"M{i}" for i in range(len(labels))}:
                raise ValueError("Expected one matched source and policy per position")
        for i, (author, predicted) in enumerate(zip(labels, ipe, strict=True)):
            counts[exposure][f"author_{author}_ipe_{predicted}"] += 1
            if on and author == predicted == "B":
                visible_rp_policy[rp_policy[f"M{i}"]] += 1
    if len(endpoints) != 300 or len(resolved) != 295:
        raise ValueError("Exposure denominator drift")
    return {"allocated": len(endpoints), "verified_route": len(resolved),
            "route_unknown": len(endpoints) - len(resolved),
            "cross_tab": counts, "author_B_ipe_B_in_history_actual_rp_policy": visible_rp_policy,
            "new_requests": 0}


if __name__ == "__main__":
    print(json.dumps(audit(), sort_keys=True, indent=2))
