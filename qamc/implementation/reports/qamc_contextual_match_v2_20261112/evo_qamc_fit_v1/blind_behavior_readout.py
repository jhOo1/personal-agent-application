"""Validate blind review receipts and publish only paired aggregate counts."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from blind_behavior_packet import OUTPUT, RP, read, sha

DIMENSIONS = ("risk_safe", "applicable_use", "hard_requirements", "delivery")
ENDPOINTS = (("IPE_C", RP), ("IPE_C", "TASK_ONLY"), (RP, "TASK_ONLY"),
             ("SELECTED", "FULL"), ("SELECTED", "GROUP"), ("GROUP", "FULL"),
             ("SELECTED", "EMPTY"))
RANK = {"VIOLATED": 0, "MET": 1}


def validate(criteria, receipt, cards, answers):
    if not receipt["reviewer"] or receipt["reviewer"] != criteria["reviewer"]:
        raise ValueError("Reviewer must match both phases")
    if (criteria["cards_sha256"], receipt["criteria_sha256"], receipt["answers_sha256"]) != (
        sha(cards), sha(criteria), sha(answers)
    ):
        raise ValueError("Review receipt does not bind the frozen inputs")
    if criteria["packets"].keys() != cards.keys() or receipt["packets"].keys() != answers.keys():
        raise ValueError("Review roster differs from frozen roster")
    checked = {}
    for packet, reviews in receipt["packets"].items():
        anchors = criteria["packets"][packet]
        if set(anchors) != set(DIMENSIONS) or not anchors["delivery"]:
            raise ValueError("Freeze the criteria for all dimensions, including delivery")
        if any(v is not None and (not isinstance(v, str) or not v.strip()) for v in anchors.values()):
            raise ValueError("Each dimension requires criteria text or null")
        if reviews.keys() != answers[packet].keys():
            raise ValueError("Review must explicitly address all available answers")
        checked[packet] = {}
        for answer_id, fields in reviews.items():
            if set(fields) != set(DIMENSIONS):
                raise ValueError("Unexpected judgment dimensions")
            checked[packet][answer_id] = {}
            for name, decision in fields.items():
                status, excerpt = decision["status"], decision.get("excerpt")
                allowed = ("NA",) if anchors[name] is None else ("MET", "VIOLATED", "UNKNOWN")
                if status not in allowed:
                    raise ValueError("Judgment contradicts the registered applicability")
                if excerpt is not None and (not excerpt or excerpt not in answers[packet][answer_id]):
                    raise ValueError("Excerpt must be verbatim")
                checked[packet][answer_id][name] = status
    return checked


def collapse(values):
    if "VIOLATED" in values:
        return "VIOLATED"
    if "UNKNOWN" in values or not values:
        return "UNKNOWN"
    if len(set(values)) != 1:
        raise ValueError("One reviewer changed dimension applicability within a task")
    return values[0]


def direction(left, right):
    if left == right == "NA":
        return "not_applicable"
    if left not in RANK or right not in RANK:
        return "unknown"
    return "win" if RANK[left] > RANK[right] else "loss" if RANK[left] < RANK[right] else "tie"


def review_source(positions, answers, conclusions):
    by_arm = defaultdict(list)
    for row in positions:
        answer_id = row["answer_id"]
        if answer_id and sha(answers[answer_id]) != row["answer_sha256"]:
            raise ValueError("Unblind key does not match the exact answer")
        by_arm[row["arm"]].append(conclusions[answer_id] if answer_id else {})
    for left, right in ENDPOINTS:
        if left not in by_arm or right not in by_arm:
            continue
        directional = {
            axis: direction(*(collapse([cell.get(axis, "UNKNOWN") for cell in by_arm[arm]])
                              for arm in (left, right)))
            for axis in DIMENSIONS
        }
        directions = set(directional.values())
        if "unknown" in directions:
            protected = "unknown"
        elif {"loss", "win"} <= directions:
            protected = "tradeoff"
        elif "loss" in directions:
            protected = "loss"
        elif "win" in directions:
            protected = "win"
        else:
            protected = "tie"
        yield left + "_vs_" + right, {**directional, "protected": protected}


def summarize(key, cards, answers, first, second):
    if key.keys() != cards.keys():
        raise ValueError("Unblind key is incomplete")
    groups = set()
    counts = defaultdict(Counter)
    for packet, entry in key.items():
        group = cards[packet]["benchmark"], entry["group"]
        if group in groups:
            raise ValueError("Expected one review packet per source group")
        groups.add(group)
        comparisons = [dict(review_source(entry["positions"], answers[packet], review[packet]))
                       for review in (first, second)]
        for pair in comparisons[0]:
            for dimension, one in comparisons[0][pair].items():
                two = comparisons[1][pair][dimension]
                base = "/".join((group[0], entry["stratum"], pair, dimension))
                counts[base + "/reviewer_1"][one] += 1
                counts[base + "/reviewer_2"][two] += 1
                counts[base + "/consensus"][one if one == two else "disagreement"] += 1
    return dict(sorted(counts.items()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("criteria_1", "reviews_1", "criteria_2", "reviews_2"):
        parser.add_argument(field, type=Path)
    args = parser.parse_args()
    cards, answers, key = [read(OUTPUT / name) for name in
                           ("01_TASK_CARDS.json", "02_ANONYMOUS_ANSWERS.json", "UNBLIND_KEY.json")]
    criteria_1, criteria_2 = read(args.criteria_1), read(args.criteria_2)
    if criteria_1["reviewer"] == criteria_2["reviewer"]:
        raise ValueError("Two distinct reviewers are required")
    first = validate(criteria_1, read(args.reviews_1), cards, answers)
    second = validate(criteria_2, read(args.reviews_2), cards, answers)
    result = summarize(key, cards, answers, first, second)
    print(json.dumps({"model_calls": 0, "source_groups": len(key), "counts": result}, indent=2))


if __name__ == "__main__":
    main()
