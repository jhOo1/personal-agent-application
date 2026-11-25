"""Trace how both V41 reviews record actions on incorrect frozen RP policies."""
from collections import Counter, defaultdict
import json

from audit_completed import audited_rows
from run_v41 import ARMS, OUT, RP, read
from settle_terminal import common_scores
from analyze_policy import paired

DELTA, REVIEW = ARMS
STRATA = ("all_A_RP_policy_all_A", "all_A_RP_admits_history", "mixed_RP_has_omission",
          "mixed_RP_no_omission")
ERRORS = ("A_promoted", "B_ignored", "B_overweighted", "C_ignored", "C_weakened")
STATES = ("apply_only", "reject_only", "both", "unrecorded")
POLICY_ERROR = {
    ("A", "B"): "A_promoted", ("A", "C"): "A_promoted",
    ("B", "A"): "B_ignored", ("B", "C"): "B_overweighted",
    ("C", "A"): "C_ignored", ("C", "B"): "C_weakened",
}


def classify(dispositions):
    applied = bool(dispositions & {"KEEP", "RESTORE"})
    rejected = "REJECT" in dispositions
    return "both" if applied and rejected else "apply_only" if applied else "reject_only" if rejected else "unrecorded"


def collect_lineage():
    plan = read(OUT / "FROZEN.json")
    roots = {root["uid"]: root for root in plan["roots"]}
    coverage, state_pairs = Counter(), defaultdict(Counter)
    strata = {key: [] for key in STRATA}
    completed = 0
    for rows, _ in audited_rows(plan):
        completed += len(rows)
        for row in rows:
            root, labels = roots[row["uid"]], row["labels"]
            policy = root["archived_policy"]
            errors = {entry["memory_id"]: POLICY_ERROR[gold, entry["policy"]]
                      for gold, entry in zip(labels, policy, strict=True) if gold != entry["policy"]}
            coverage["any_policy_error_roots"] += bool(errors)
            coverage.update(errors.values())
            if set(labels) == {"A"}:
                subset = "all_A_RP_admits_history" if errors else "all_A_RP_policy_all_A"
            else:
                missed = any(label in errors.values() for label in ("B_ignored", "C_ignored"))
                subset = "mixed_RP_has_omission" if missed else "mixed_RP_no_omission"
            row["positions"] = len(labels)
            strata[subset].append(row)
            if not all(row["answers"][arm]["status"] == "OK" for arm in ARMS):
                continue
            observed = {arm: defaultdict(set) for arm in ARMS}
            for arm in ARMS:
                for entry in row["answers"][arm]["changes"]:
                    for memory_id in entry["source_ids"]:
                        observed[arm][memory_id].add(entry["disposition"])
            for memory_id, error in errors.items():
                left = classify(observed[REVIEW][memory_id])
                right = classify(observed[DELTA][memory_id])
                state_pairs[error][left, right] += 1
    scores = {}
    for label, rows in strata.items():
        pairs = {}
        for left, right in ((REVIEW, DELTA), (RP, DELTA), (RP, REVIEW)):
            result = paired(rows, left, right)
            pairs[f"{left}__{right}"] = {key: result[key] for key in (
                "valid_cases", "expected_cases", "n_source_groups", "scores", "match_delta",
                "95pct_source_bootstrap",
            ) if key in result}
        scores[label] = {"roots": len(rows), "four_way": common_scores(rows), "pairs": pairs}
    return {
        "completed_roots": completed, "planned_roots": len(roots),
        "complete": completed == len(roots), "frozen_RP_policy_error_counts": coverage,
        "review_disposition_pairs": {
            error: {f"{a}__{b}": state_pairs[error][a, b] for a in STATES for b in STATES}
            for error in ERRORS
        },
        "native_by_frozen_policy_stratum": scores,
        "new_model_requests": 0, "native_score_changes": 0,
        "interpretation": ("Author A/B/C compared with archived policy only in the evaluation layer. "
                           "Review disposition is a self-report and must not be read as observed usage. "
                           "A change can KEEP one use and REJECT another use of the same source. "
                           "Native scoring strata are observational and unchanged."),
    }


if __name__ == "__main__":
    print(json.dumps(collect_lineage(), ensure_ascii=False, indent=2))
