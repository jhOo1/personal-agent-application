"""Report source-mask topology and archived draft controls without dispatch."""
from collections import Counter
import json

from qamc.common import sha

import run_active_source_ids as trial


TASK_ONLY = "ARCHIVED_TASK_ONLY_DRAFT"
FALLBACK = "NEW_WITH_EMPTY_DRAFT"


def compare(rows, left, right):
    native = trial.replay.paired(rows, left, right)
    valid = set(native["valid_uids"])
    common = [row for row in rows if row["uid"] in valid]
    return {"match": native,
            **{metric: trial.scorer.comparisons.grade_pair(common, left, right, metric)
               for metric in trial.METRICS}}


def audit():
    if trial.read(trial.OUT / "RUN_STATE.json")["state"] != "COMPLETE":
        raise ValueError("Wait for the frozen comparison to settle")
    saved = trial.read(trial.OUT / "SETTLED.json")
    spec, _, roots, masks, _, cache = trial.prepare()
    _, _, _, history, (_, official, cases), _ = trial.outcome.prepare()
    compare_slices = {name: [] for name in ("same", "subset", "superset", "mixed", "empty_new")}
    changes = []
    for row in saved["rows"]:
        uid = row["uid"]
        scores = row["native"]
        scores[FALLBACK] = scores[trial.NEW]
        if uid not in masks:
            continue
        old, new = (set(masks[uid][arm]) for arm in trial.ARMS)
        if old == new:
            relation = "same"
        elif new < old:
            relation = "subset"
        elif old < new:
            relation = "superset"
        else:
            relation = "mixed"
        compare_slices[relation].append(row)
        if not new:
            compare_slices["empty_new"].append(row)
            grade = trial.scorer.grade_request(official, cases[uid], history[uid]["draft"])
            receipt, raw = cache[trial.JUDGE][sha(grade)]
            scores[TASK_ONLY] = trial.scorer.parse_grade(receipt, raw, row["positions"])
            scores[FALLBACK] = scores[TASK_ONLY]
        labels = dict(zip((source["memory_id"] for source in roots[uid]["original_sources"]),
                          row["labels"], strict=True))
        changes.append({"uid": uid, "group": row["group"], "relation": relation,
                        "mask_sizes": {trial.OLD: len(old), trial.NEW: len(new)},
                        "dropped": {mid: labels[mid] for mid in sorted(old - new)},
                        "added": {mid: labels[mid] for mid in sorted(new - old)},
                        "answer_changed": len(row["outputs"]) == 2
                        and row["outputs"][trial.OLD] != row["outputs"][trial.NEW]})
    exact_v42_matches = Counter()
    for row in changes:
        if row["relation"] == "same":
            continue
        same = spec["alignment"][row["uid"]]["matches"]
        for left, right in (("DIRECT", "SCOPED"), ("SCOPED", "DIRECT")):
            exact_v42_matches[f"{left}/{right}"] += (
                left in same[trial.OLD] and right in same[trial.NEW])
    if any(row["answer_changed"] for row in changes if row["relation"] == "same"):
        raise ValueError("Identical active-ID requests gave different replayed answers")
    panels = {"assigned": saved["rows"]}
    for name, applicable in {
        "all_A": lambda labels: set(labels) == {"A"},
        "B_only": lambda labels: "B" in labels and "C" not in labels,
        "contains_C": lambda labels: "C" in labels,
    }.items():
        panels[name] = [row for row in saved["rows"] if applicable(row["labels"])]
    return {"physical_requests_added": 0, "exact_v42_matches_changed_histories": exact_v42_matches,
            "admissions_per_arm": {arm: sum(row["mask_sizes"][arm] for row in changes) for arm in trial.ARMS},
            "relations": {name: len(rows) for name, rows in compare_slices.items()},
            "by_history": changes,
            "by_relation": {name: compare(rows, trial.OLD, trial.NEW) for name, rows in compare_slices.items()},
            "empty_new_vs_archived_task_only": compare(compare_slices["empty_new"], TASK_ONLY, trial.NEW),
            "posthoc_empty_fallback": {
                name: trial.score_matrix(rows, (*trial.ARMS, FALLBACK, trial.outcome.GATE, trial.outcome.RP))
                for name, rows in panels.items()}}


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
