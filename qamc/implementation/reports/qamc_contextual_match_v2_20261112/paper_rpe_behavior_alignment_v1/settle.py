"""Verify the private review against the freeze and aggregate endpoint differences."""

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path

from freeze import METHODS, freeze, matched

STATES = {"REALIZED", "CONFLICT", "OMITTED", "UNCLEAR"}


def settle(base, private):
    packet, mapping, frozen = freeze(base)
    if packet != (private / "PACKETS.json").read_bytes() or mapping != json.loads((private / "KEY.json").read_bytes()):
        raise ValueError("The private packet or key has changed")
    raw = (private / "REVIEW.json").read_bytes()
    review = json.loads(raw)
    if review.keys() != mapping.keys():
        raise ValueError("Out-of-roster or missing review")
    original = json.loads((base / "ipe_c_two_endpoint_completion_v1/RESULTS.json").read_bytes())
    rows = {r["uid"]: r for r in original["rows"]}
    scores = defaultdict(Counter)
    transitions = defaultdict(Counter)
    behavior_score_overlap = defaultdict(Counter)
    for case, assignments in mapping.items():
        row = rows[assignments["uid"]]
        n = row["labels"].count("C")
        item = review[case]
        if item.keys() != {"X", "Y", "witness"} or not item["witness"].strip():
            raise ValueError(f"Missing or malformed source witness in {case}")
        for letter in "XY":
            if len(item[letter]) != n or set(item[letter]) - STATES:
                raise ValueError(f"Preference review alignment error in {case}")
        outcomes = {arm: item[key] for key, arm in assignments["mapping"].items()}
        outcomes["IPE_C"] = outcomes[assignments["ipe_c_endpoint"]]
        for arm in METHODS:
            scores[arm].update(outcomes[arm])
            scores[arm].update(joint_C_realized=outcomes[arm] == ["REALIZED"] * n,
                               native_match=matched(row, arm))
        for arm in ("IPE_C", "RPR_PAPER_FULL"):
            comparator = "TASK_ONLY"
            transitions[arm].update(f"{a}->{b}" for a, b in zip(outcomes[comparator], outcomes[arm]))
            behavior_delta = outcomes[arm].count("REALIZED") - outcomes[comparator].count("REALIZED")
            score_delta = matched(row, arm) - matched(row, comparator)
            if behavior_delta > 0:
                bucket = "native_gain" if score_delta > 0 else "native_loss" if score_delta < 0 else "native_tie"
                behavior_score_overlap[arm][bucket] += 1
    return {**frozen, "review_sha256": sha256(raw).hexdigest(), "native_positions": sum(
        len(rows[v["uid"]]["labels"]) for v in mapping.values()), "scores": scores,
        "transitions_from_task_only": transitions, "native_on_behavior_improvements": behavior_score_overlap}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("research_report_root", type=Path)
    parser.add_argument("private_review_root", type=Path)
    args = parser.parse_args()
    print(json.dumps(settle(args.research_report_root, args.private_review_root), indent=2, sort_keys=True))
