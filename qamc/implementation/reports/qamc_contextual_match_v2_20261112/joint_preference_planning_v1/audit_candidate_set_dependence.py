"""Audit RP policy changes for byte-identical task/source pairs in different memory sets."""
from collections import Counter, defaultdict
from itertools import combinations
import json

from qamc.common import sha

import run_joint_planning as run


def source_slots():
    directory = run.prior.formal.OUT
    formal = run.read(directory / "PLAN.json")
    audit_path = directory / "RPR_RANK_FUSION_AUDIT_300.json"
    replay = run.read(audit_path)
    by_uid = {row["uid"]: row for row in replay["rows"]}
    groups = defaultdict(list)
    verified = set()
    policy = "PAPER_FUSION"
    for index in range(len(formal["waves"])):
        path = directory / "waves" / f"{index:02}.json"
        for row in run.read(path)["rows"]:
            uid = row["uid"]
            if row["method"] != "RPR_PAPER_FULL" or uid not in by_uid:
                continue
            archive = by_uid[uid]
            request = row["actor_request"]
            request_hash = sha(request)
            if (uid in verified or request_hash != row["actor_request_sha256"]
                    or request_hash != archive["policies"][policy]["actor_request_sha256"]):
                raise ValueError("Duplicate root or mismatched RP Actor request")
            verified.add(uid)
            packet = json.loads(request["messages"][1]["content"])
            order = packet.pop("preference_use_policy")
            sources = packet.pop("source_evidence")
            if set(packet) != {"query", "current_context", "facts"}:
                raise ValueError("Unexpected public task fields")
            candidates = [item["text"] for item in sources]
            ordered = [item["memory_id"] for item in sources]
            if (ordered != [p["memory_id"] for p in order] or len(set(ordered)) != len(ordered)
                    or "".join(item["policy"] for item in order) != archive["policies"][policy]["policy"]):
                raise ValueError("RP policy differs from the archived Actor input")
            candidate_set = sha(sorted(candidates))
            task = sha(packet)
            for i, (text, label, ranks) in enumerate(zip(candidates, archive["author_labels"], row["aggregation"],
                                                         strict=True)):
                entry = {"uid": uid, "index": i, "source_group": archive["source_group"],
                         "co_candidates_sha256": candidate_set, "position_count": len(candidates),
                         "author_label": label, "fusion": ranks["policy"], "mle": ranks["mle_order"][0],
                         "ipe": ranks["ipe_order"][0]}
                if ranks["memory_id"] != ordered[i] or ranks["policy"] != order[i]["policy"]:
                    raise ValueError("Archived ranks and exact source order disagree")
                groups[(task, sha(text))].append(entry)
    if (verified != by_uid.keys() or len(verified) != replay["verified_roots"]
            or sum(map(len, groups.values())) != replay["summaries"][policy]["positions"]):
        raise ValueError("Incomplete source-position census")
    return groups, len(verified), sha(audit_path.read_bytes())


def audit():
    groups, verified, audit_sha = source_slots()
    counts, flips_by_label, witnesses = Counter(), Counter(), {}
    flip_groups = defaultdict(set)
    for (task, memory), entries in groups.items():
        alternate = [(a, b) for a, b in combinations(entries, 2)
                     if a["uid"] != b["uid"] and a["co_candidates_sha256"] != b["co_candidates_sha256"]]
        if not alternate:
            continue
        labels = {entry["author_label"] for entry in entries}
        counts["same_task_source_with_changed_set"] += 1
        counts["same_task_source_with_inconsistent_gold"] += len(labels) != 1
        if len(labels) != 1:
            continue
        counts["same_index_comparisons"] += any(a["index"] == b["index"] for a, b in alternate)
        flips = [field for field in ("fusion", "mle", "ipe") if any(a[field] != b[field] for a, b in alternate)]
        for field in flips:
            counts[f"{field}_flip"] += 1
            flip_groups[field].update(entry["source_group"] for entry in entries)
        if "fusion" not in flips:
            continue
        same_index_flips = any(a["index"] == b["index"] and a["fusion"] != b["fusion"] for a, b in alternate)
        binary_flips = any((a["fusion"] == "A") != (b["fusion"] == "A") for a, b in alternate)
        counts["fusion_flip_same_index"] += same_index_flips
        counts["fusion_admission_flip"] += binary_flips
        counts["fusion_flip_same_index_and_length"] += any(
            a["index"] == b["index"] and a["position_count"] == b["position_count"] and a["fusion"] != b["fusion"]
            for a, b in alternate
        )
        flips_by_label[next(iter(labels))] += 1
        witnesses[sha([task, memory])] = {
            "task_sha256": task, "memory_sha256": memory, "estimators_with_flip": flips,
            "has_same_index_fusion_flip": same_index_flips, "entries": entries,
        }
    return {"verified_RP_roots": verified, "exact_task_memory_pairs": len(groups),
            "archive_sha256": audit_sha, "counts": counts, "fusion_flips_by_author_label": flips_by_label,
            "source_groups_with_flips": {key: len(value) for key, value in flip_groups.items()},
            "new_model_calls": 0, "witnesses": witnesses}


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
