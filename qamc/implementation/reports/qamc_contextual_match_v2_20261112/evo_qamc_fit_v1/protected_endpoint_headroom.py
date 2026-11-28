"""Bound the existing exposure endpoints against the archived specialists."""
from collections import Counter
import json

# Load these in the same order as the settled exposure readout.
from exposure_summary import ARMS, collect
from summarize_reassembly import aligned

PROTECTIONS = {
    "RPEval": {"OPB": -1, "UPB": -1, "FM": -1},
    "BenchPreS": {"MR": -1, "completeness": 1, "nonbold": 1},
    "PersistBench": {},
}


def admissible(grade, reference, directions):
    return all(sign * (grade[key] - reference[key]) >= 0 for key, sign in directions.items())


def bound(items, reference, without_flags=False):
    summary = Counter()
    protected_groups = set()
    for card, receipts, grades in items:
        summary["assigned"] += 1
        if not aligned(grades, ("BASE", *ARMS)):
            continue
        if without_flags and (card["base_flags"] != [] or any(
                receipts[arm].get("score_flags") != [] for arm in ARMS)):
            continue
        summary["common"] += 1
        ref = grades[reference]
        summary["positions"] += ref["positions"]
        summary["reference_primary"] += ref["primary"]
        direction = PROTECTIONS[card["domain"]]
        candidates = [grades[arm] for arm in ARMS]
        maximum = max(grade["primary"] for grade in candidates)
        summary["unconstrained_maximum"] += maximum
        summary["reference_above_pool"] += ref["primary"] > maximum
        allowed = [grade for grade in candidates if admissible(grade, ref, direction)]
        if not allowed:
            summary["no_protected_endpoint"] += 1
            summary["no_protected_positions"] += ref["positions"]
            continue
        protected = max(grade["primary"] for grade in allowed)
        summary["protected_tasks"] += 1
        summary["protected_positions"] += ref["positions"]
        summary["protected_optimal_primary"] += protected
        summary["protected_subset_reference"] += ref["primary"]
        summary["protected_wins"] += protected > ref["primary"]
        if protected > ref["primary"]:
            protected_groups.add(card["group"])
        summary["protected_losses"] += protected < ref["primary"]
        # Hypothetical return of the independently archived reference is priced separately.
        summary["headroom_with_reference_available"] += max(0, protected - ref["primary"])
    summary["source_groups_with_protected_gain"] = len(protected_groups)
    return dict(summary)


def main():
    _, batches, groups, *_ = collect()
    if batches != [1, 2, 3]:
        raise ValueError("Exposure panel is not fully settled")
    output = {
        name: {
            "specialist": bound(rows, "BASE"),
            "selected": bound(rows, "SELECTED"),
            **({"specialist_unflagged": bound(rows, "BASE", without_flags=True)}
               if name.startswith("RPEval") else {}),
        }
        for name, rows in groups.items()
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
