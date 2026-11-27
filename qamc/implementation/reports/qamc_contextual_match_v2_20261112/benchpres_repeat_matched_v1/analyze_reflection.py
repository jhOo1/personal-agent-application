"""Analyze independent reflection votes while retaining all missing positions."""

import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path

from freeze_reflection import PRIVATE, RATERS
from qamc_benchpres_matched_fieldwise_audit import BOLD, delta_bounds
from trace_misuse import CATEGORIES, run


def load_votes(path, key):
    votes = {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["id", "reflection", "evidence"]:
            raise ValueError("Expected the frozen vote columns")
        for row in reader:
            row_id = row["id"]
            if row_id not in key:
                raise ValueError(f"Unknown review identifier in {path.name}")
            slot = tuple(key[row_id])
            if slot in votes or row["reflection"] not in ("", "yes", "no", "uncertain"):
                raise ValueError(f"Duplicate or invalid review vote in {path.name}")
            votes[slot] = row["reflection"]
    return votes


def agreement(pairs):
    valid = [(a, b) for a, b in pairs if a is not None and b is not None]
    n = len(valid)
    if not n:
        return {"paired_binary_votes": 0, "excluded": len(pairs), "agreement": None, "kappa": None}
    matches = sum(a == b for a, b in valid)
    a_yes, b_yes = (sum(pair[i] for pair in valid) for i in (0, 1))
    expected = (a_yes * b_yes + (n - a_yes) * (n - b_yes)) / (n * n)
    observed = matches / n
    return {
        "paired_binary_votes": n, "excluded": len(pairs) - n, "agreement": observed,
        "kappa": (observed - expected) / (1 - expected) if expected != 1 else None,
        "left_yes_right_no": sum(a == 1 and b == 0 for a, b in valid),
        "left_no_right_yes": sum(a == 0 and b == 1 for a, b in valid),
    }


def archive_references():
    plan = run.read(run.RUN / "PLAN_PRIVATE.json")
    run.valid(plan)
    if run.sha(plan) != run.read(run.OUT / "PREFLIGHT.json")["plan_sha256"]:
        raise ValueError("Unexpected source plan")
    references = {}
    for case in plan["cases"]:
        ref = run.read(run.ROOT / case["evaluation_path"])
        if case["independent_confirmation"] or run.digest(ref) != case["evaluation_hash"]:
            raise ValueError("Unexpected source reference")
        references[case["uid"]] = list(zip(ref["preference_attribute"], ref["preference_label"], strict=True))
    return references


def analyze(index, votes, references):
    compare = defaultdict(list)
    metrics = defaultdict(list)
    left, right = run.METHODS
    draws = {(row["uid"], row["draw"], row["method"]): row for row in index["draws"]}
    for uid, draw in sorted({(uid, draw) for uid, draw, _ in draws}):
        items = [draws[uid, draw, method] for method in run.METHODS]
        known = {item["method"]: item.get("attributes") for item in items}
        refs = references[uid]
        for attrs in known.values():
            if attrs and [(a["attribute"], a["appropriate"]) for a in attrs] != refs:
                raise ValueError("Paired records differ in author attribute allocation")
        for i, (attr, allowed) in enumerate(refs):
            category = next((key for key, pattern in CATEGORIES if pattern.search(attr)), "other")
            if BOLD.search(attr):
                category = "bold"
            names = ("AAR", "bold_AAR" if category == "bold" else "nonbold_AAR") if allowed else (
                "MR", "nickname_MR" if category == "nickname" else "non_nickname_MR")
            values = defaultdict(dict)
            for method in run.METHODS:
                slot = uid, method, draw, i
                a, b = ({"yes": 1, "no": 0}.get(votes[rater].get(slot)) for rater in RATERS)
                consensus = a if a is not None and a == b else None
                old = known[method][i]["follow"] if known[method] else None
                tags = {"all", category, "appropriate" if allowed else "inappropriate"}
                for tag in tags:
                    compare[("rater_A_vs_B", tag)].append((a, b))
                    compare[(f"{method}_Qwen_vs_consensus", tag)].append((old, consensus))
                    if all(item["old_strict_score"] for item in items):
                        compare[(f"{method}_Qwen_vs_consensus_original_common", tag)].append((old, consensus))
                for track, value in zip(("A", "B", "consensus"), (a, b, consensus), strict=True):
                    values[track][method] = value
            for track, pair in values.items():
                for name in names:
                    metrics[track, name].append(((uid, draw, i), pair))
    return {
        "evaluator_agreement": {f"{comparison}/{tag}": agreement(pairs)
                                for (comparison, tag), pairs in compare.items()},
        "bounds_by_evaluator": {f"{track}/{name}": delta_bounds(slots, left, right, 0, 1)
                                for (track, name), slots in metrics.items()},
        "recorded_vote_statuses": {rater: Counter(value or "blank" for value in votes[rater].values()) for rater in RATERS},
        "original_scores_replaced": 0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for rater in RATERS:
        parser.add_argument(f"--votes-{rater.lower()}", type=Path, required=True)
    args = parser.parse_args()
    index = run.read(PRIVATE / "CUSTODIAN_ONLY.json")
    votes = {rater: load_votes(getattr(args, f"votes_{rater.lower()}"), index["rater_ids"][rater])
             for rater in RATERS}
    print(json.dumps(analyze(index, votes, archive_references()), indent=2, sort_keys=True))
