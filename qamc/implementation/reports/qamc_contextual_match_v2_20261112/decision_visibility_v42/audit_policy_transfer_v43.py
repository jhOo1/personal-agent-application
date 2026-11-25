"""Bound V43's score transfer at corrected positions without inventing judge labels."""
from collections import Counter
import json

from label_bounds import TRANSITIONS, TRANSITION_BITS
import run_policy_override_v43 as study


def corrected_match_range(labels, corrected, fields, condition_on_bias):
    """Enumerate attainable correct counts restricted to edited, author-matching positions."""
    total = fields["match"]["matched"]
    present = absent = 0
    if condition_on_bias:
        for name, bit in TRANSITION_BITS.items():
            if name in fields:
                if fields[name] > 0:
                    present |= bit
                else:
                    absent |= bit
    states = {(0, 0, 0)}
    for index, label in enumerate(labels):
        next_states = set()
        for hits, edited_hits, seen in states:
            if hits < total:
                next_states.add((hits + 1, edited_hits + (index in corrected), seen))
            for prediction in "ABC":
                if prediction != label:
                    flag = TRANSITION_BITS[TRANSITIONS[label + prediction]] if condition_on_bias else 0
                    if not flag & absent:
                        next_states.add((hits, edited_hits, seen | flag))
        states = next_states
    values = [edited_hits for hits, edited_hits, seen in states if hits == total and seen & present == present]
    return (min(values), max(values)) if values else None


def audit():
    plan, origins = study.prepare()
    if study.read(study.OUT / "FROZEN.json") != plan:
        raise ValueError("Frozen V43 inputs changed")
    saved = study.read(study.OUT / "COMPLETED.json")
    totals, coverage, groups = {}, Counter(), {}
    for intervention, row in zip(plan["roots"], saved["rows"], strict=True):
        if intervention != row["trace"]:
            raise ValueError("Row does not match the V43 frozen edit")
        if not intervention["edits"]:
            continue
        origin = origins[row["uid"]]
        sources = origin["archived_policy"]
        labels = row["labels"]
        if len(sources) != len(labels) or [p["memory_id"] for p in sources] != [
            s["memory_id"] for s in origin["original_sources"]
        ]:
            raise ValueError("Cannot reconcile positional label identities")
        positions = {p["memory_id"]: index for index, p in enumerate(sources)}
        corrected = {positions[mid] for mid, new in intervention["edits"].items() if labels[positions[mid]] == new}
        coverage.update(edited_roots=1, author_labels_corrected=len(corrected))
        before, after = [row["native"][method]["fields"] for method in (study.prior.RP, study.METHOD)]
        if not corrected or not all(f.get("match") for f in (before, after)):
            continue
        if any(f["match"]["positions"] != len(labels) for f in (before, after)):
            raise ValueError("Native score denominator drift")
        for lens in ("match_only", "bias_conditioned"):
            left, right = [corrected_match_range(labels, corrected, fields, lens == "bias_conditioned")
                           for fields in (before, after)]
            if left is None or right is None:
                coverage.update(bias_incompatible_roots=1)
                continue
            tags = ("all", "all_A" if set(labels) == {"A"} else "contains_BC")
            for tag in tags:
                key = f"{lens}.{tag}"
                groups.setdefault(key, set()).add(row["group"])
                totals.setdefault(key, Counter()).update(
                    roots=1, corrected_positions=len(corrected), before_min=left[0], before_max=left[1],
                    after_min=right[0], after_max=right[1],
                    recoveries_min=max(0, right[0] - left[1]), recoveries_max=min(len(corrected) - left[0], right[1]),
                    net_min=right[0] - left[1], net_max=right[1] - left[0],
                    aggregate_match_delta=after["match"]["matched"] - before["match"]["matched"])
    if coverage["author_labels_corrected"] != 99:
        raise ValueError("Unexpected V43 correct-edit denominator")
    return {
        "model_calls": 0, "coverage": coverage,
        "results": {key: {**score, "source_groups": len(groups[key])} for key, score in totals.items()},
        "interpretation": ("These are bounds for the corrected input-policy positions under aggregate "
                           "native scores. The Judge does not return authoritative per-position labels. "
                           "Bias-conditioned intervals require consistent rubric transitions and exclude incompatible "
                           "cells, which remain in the original scores and Match-only intervals."),
    }


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
