"""Compare all-A and applicable-history variants of exactly the same public task."""
from collections import Counter, defaultdict
import json

from audit_completed import audited_rows
from qamc.common import sha
from qamc.pa.core import digest
from run_v41 import ARMS, GATE, OUT, RP, author_cases, formal, read
from settle_terminal import common_scores
from analyze_policy import group_stability

DELTA, REVIEW = ARMS
EDGE = ((REVIEW, DELTA), (RP, DELTA), (RP, REVIEW), (GATE, DELTA))


def task_condition(labels):
    return "all_A" if set(labels) == {"A"} else "contains_BC"


def audit_pairs():
    plan = read(OUT / "FROZEN.json")
    refs = author_cases(read(formal.OUT / "PLAN.json"))
    indexed = {root["uid"]: root for root in plan["roots"]}
    task_groups, task_variants, shared_history_labels = {}, defaultdict(Counter), defaultdict(set)
    for uid, root in indexed.items():
        ref = refs[uid]
        reference = read(formal.ROOT / ref["evaluation_path"])
        labels = reference["intent_type"]
        if digest(reference) != ref["evaluation_hash"] or set(labels) - set("ABC"):
            raise ValueError("Frozen author reference changed")
        condition = task_condition(labels)
        task = root["task_wire_sha256"]
        group = task_groups.setdefault(task, root["group"])
        if group != root["group"]:
            raise ValueError("Same public task wire split across source clusters")
        task_variants[task][condition] += 1
        shared_history_labels[task, sha(root["original_sources"])].add(condition)
    ambiguous = {task for (task, _), kinds in shared_history_labels.items() if len(kinds) != 1}
    qualifying = {task for task, variants in task_variants.items() if len(variants) == 2 and task not in ambiguous}

    settled, boxes = 0, defaultdict(lambda: defaultdict(list))
    for rows, _ in audited_rows(plan):
        settled += len(rows)
        for row in rows:
            task = indexed[row["uid"]]["task_wire_sha256"]
            if task in qualifying and all("match" in row["native"][arm]["fields"]
                                           for arm in (REVIEW, DELTA, RP, GATE)):
                boxes[task][task_condition(row["labels"])].append(row)

    paired = {task: {condition: common_scores(rows) for condition, rows in cells.items()}
              for task, cells in boxes.items() if len(cells) == 2}
    scope = {}
    for left, right in EDGE:
        totals = {condition: Counter() for condition in ("all_A", "contains_BC")}
        group_contrasts = defaultdict(lambda: [0, 0])
        per_task = []
        for task, cells in sorted(paired.items()):
            delta = {}
            for condition, tab in cells.items():
                n = tab["positions"]
                a, b = tab["matches"][left], tab["matches"][right]
                totals[condition].update(roots=tab["roots"], positions=n, left_matched=a, right_matched=b)
                delta[condition] = (b - a) / n
            contribution = delta["contains_BC"] - delta["all_A"]
            group = task_groups[task]
            group_contrasts[group][0] += contribution
            group_contrasts[group][1] += 1
            per_task.append({"task_sha256": task, "source_group": group, "by_history_condition": delta})
        if per_task:
            center = sum(d for d, _ in group_contrasts.values()) / len(per_task)
        else:
            center = None
        scope[f"{left}__{right}"] = {
            "same_task_controls": totals, "equal_task_weighted_BC_minus_all_A_delta": center,
            "source_groups": len(group_contrasts), "task_deltas": per_task, **group_stability(group_contrasts),
        }
    return {
        "completed_roots": settled, "complete": settled == len(indexed),
        "planned_public_tasks": len(task_variants), "planned_history_condition_pairs": len(qualifying),
        "planned_variants_in_those_tasks": {condition: sum(task_variants[t][condition] for t in qualifying)
                                            for condition in ("all_A", "contains_BC")},
        "exact_history_with_conflicting_task_conditions": len(ambiguous),
        "scored_same_task_families": len(paired), "pairs": scope,
        "new_model_requests": 0, "behavior_verdicts": 0,
        "interpretation": ("These are different archived memory variants of an identical task-only wire. "
                           "Mixed variants can still contain author A positions. Contrast differences are "
                           "descriptive and retain original native Judge scores."),
    }


if __name__ == "__main__":
    print(json.dumps(audit_pairs(), ensure_ascii=False, indent=2))
