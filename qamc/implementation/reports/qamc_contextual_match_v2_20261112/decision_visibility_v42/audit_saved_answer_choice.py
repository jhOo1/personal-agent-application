"""Measure the saved two-answer headroom and a policy-only selection control."""
from collections import Counter, defaultdict
import json

from qamc.common import sha

import run_policy_override_v43 as study
from score_task_only import OUT as TASK_ONLY, saved_drafts

ZERO = "TASK_ONLY"
NO_C = "TASK_ONLY_IF_RP_HAS_NO_C"


def analyze():
    plan, origins = study.prepare()
    if study.read(study.OUT / "FROZEN.json") != plan:
        raise ValueError("Frozen V43 inputs changed")
    archive = study.read(study.prior.OUT / "FROZEN.json")
    drafts = saved_drafts(archive)
    control = study.read(TASK_ONLY / "RESULTS.json")
    root_controls = {row["uid"]: row for row in control["roots"]}
    if control["state"]["state"] != "COMPLETE" or root_controls.keys() != origins.keys():
        raise ValueError("Task-only reference does not match the frozen panel")
    settled = study.read(study.OUT / "COMPLETED.json")
    paired_rows, potential = defaultdict(list), defaultdict(Counter)
    for row, entry in zip(settled["rows"], plan["roots"], strict=True):
        uid, labels = row["uid"], row["labels"]
        root, task_only = origins[uid], root_controls[uid]
        no_history = task_only["task_only"]
        rp = row["native"][study.prior.RP]
        wire = sha(study.prior.task_only_request(root))
        if (row["trace"] != entry or wire != root["task_wire_sha256"]
                or task_only["labels"] != labels or task_only["group"] != row["group"]):
            raise ValueError("Saved alternatives are not on the same input root")
        before, after = rp["fields"].get("match"), no_history["fields"].get("match")
        if before is None or after is None:
            continue
        if not drafts[wire]["answer"] or before["positions"] != after["positions"] or len(labels) != before["positions"]:
            raise ValueError("Task-only answer or score cannot be matched")
        has_constraint = any(item["policy"] == "C" for item in root["archived_policy"])
        cell = {**row, "native": {study.prior.RP: rp, ZERO: no_history, NO_C: rp if has_constraint else no_history}}
        for tag in ("all", "all_A" if set(labels) == {"A"} else "contains_BC"):
            paired_rows[tag].append(cell)
            potential[tag].update(
                switches=not has_constraint,
                max_existing_match=max(before["matched"], after["matched"]))
    return {
        "frozen_roots": len(plan["roots"]),
        "new_model_calls": 0,
        "strata": {
            tag: {
                "compare": {arm: {
                    "match": study.v42.paired(rows, study.prior.RP, arm),
                    "severity": study.v42.metric_pairs(rows, study.prior.RP, arm),
                } for arm in (ZERO, NO_C)},
                "diagnostic": potential[tag],
            } for tag, rows in paired_rows.items()
        },
        "interpretation": ("Retrospective replay of two real, already scored answers per case, excluding missing pairs. "
                           "The C-based rule uses only RP policy predictions. Author labels are used for strata only. "
                           "Per-case max uses native grades and is a non-deployable, score-based upper bound for these "
                           "two answers. This is not a fresh run or independent evidence."),
    }


if __name__ == "__main__":
    print(json.dumps(analyze(), ensure_ascii=False, indent=2))
