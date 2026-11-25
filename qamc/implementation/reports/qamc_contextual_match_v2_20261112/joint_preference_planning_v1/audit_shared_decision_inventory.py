"""Find memory-blind candidate sets shared by exposed exact-task history variants."""
from collections import Counter, defaultdict
import json

import recover_decision_repair_drafts as recovery
import run_decision_repair as parent


def observed_rank_changes():
    """Check exact-alternative retention and a first-choice change on saved outputs."""
    run = parent.read(recovery.OUT / "SETTLED.json")
    counters = Counter()
    for row in run["rows"]:
        trace = row["execution"]
        for slot, block in trace.get("blocks", {}).items():
            old = block["lines"]
            if block["kind"] != "CHOICE" or len(old) < 2:
                continue
            counters["plural_blocks"] += 1
            if slot not in trace.get("edits", {}):
                continue
            counters["edits_on_plural_blocks"] += 1
            check = trace.get("checks", {}).get(slot)
            if not check or check["strength"] != "SOFT":
                continue
            counters["soft_review_rows"] += 1
            new = trace["edits"][slot]["lines"]
            retains = set(old) <= set(new)
            counters["soft_edits_retain_exact_options"] += retains
            counters["soft_edits_retain_options_but_replace_first"] += retains and old[0] != new[0]
            counters["participant_soft_rows"] += check["binding"] == "PARTICIPANT_LIMIT"
    return counters


def evaluate():
    _, _, roots, roster, _, archive = parent.prior.prepare("pilot")
    _, _, _, _, _, normalized = recovery.prepare()
    drafts = parent.inherited(archive)[parent.DRAFT]
    drafts.update(parent.read(parent.OUT / f"{parent.DRAFT}_EXACT.json"))
    drafts.update(normalized)
    by_uid = {row["uid"]: row for row in roster}
    families = defaultdict(list)
    for root in roots.values():
        families[root["task_wire_sha256"]].append(root)

    counts, data = Counter(), []
    for task, variants in sorted(families.items()):
        exemplar = variants[0]
        groups = {by_uid[root["uid"]]["group"] for root in variants}
        wires = {parent.sha(parent.draft.draft_request(root)) for root in variants}
        if len(groups) != 1 or len(wires) != 1:
            raise ValueError("A task family does not share the public request")
        if any(root["public_task"] != exemplar["public_task"] for root in variants):
            raise ValueError("Query, context or facts differ within one task family")
        conditions = defaultdict(list)
        evidence_conditions = defaultdict(set)
        for root in variants:
            uid = root["uid"]
            labels = set(by_uid[uid]["labels"])
            history_hash = parent.sha(root["original_sources"])
            condition = "all_A" if labels == {"A"} else "contains_BC"
            conditions[condition].append(uid)
            evidence_conditions[history_hash].add(condition)
        if len(conditions) != 2:
            counts["one_history_condition_only"] += 1
            continue
        if any(len(value) != 1 for value in evidence_conditions.values()):
            raise ValueError("Identical history assigned opposing conditions")
        counts["paired_task"] += 1
        digest, = wires
        entry = drafts.get(digest)
        blocks = {}
        state = "NO_ARCHIVED_DRAFT"
        if entry is not None:
            rec, raw = entry
            if rec["request_sha256"] != digest:
                raise ValueError("Neutral draft has a different input")
            state = rec["status"]
            if state == "OK":
                try:
                    blocks = parent.draft.read_draft(exemplar, raw)
                except ValueError:
                    state = "INVALID_DRAFT"
                else:
                    counts["verified_neutral_draft"] += 1
        choice_vectors = {}
        for slot, block in blocks.items():
            if block["kind"] == "CHOICE" and len(block["lines"]) >= 2:
                choice_vectors[slot] = {"options": len(block["lines"]),
                                        "candidate_set_sha256": parent.sha(block["lines"])}
        counts["candidate_comparison_replayable"] += bool(choice_vectors)
        counts["verified_draft_without_plural_choice"] += bool(blocks and not choice_vectors)
        data.append({"task_sha256": task, "draft_wire_sha256": digest,
                     "source_group": next(iter(groups)), "history_variants": conditions,
                     "draft_status": state, "shared_candidate_sets": choice_vectors})

    return {
        "archived_tasks": len(families), "archived_variants": len(roots), "inventory": counts,
        "paired_source_groups": len({row["source_group"] for row in data}),
        "replayable_choice_source_groups": len({row["source_group"] for row in data
                                                 if row["shared_candidate_sets"]}),
        "v2_exact_text_choice_replay": observed_rank_changes(),
        "per_task": data, "new_model_requests": 0,
        "interpretation": ("The generated memory-blind draft is identical for all history variants. "
                           "A plural set permits an ordering contrast. No proof of candidate feasibility "
                           "or beneficiary preference is inferred from availability."),
    }


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
