"""Publish paired effect estimates and assignment bounds for the frozen Actor study."""
from collections import Counter, defaultdict
import json

from task_message_boundary import (
    ARMS, PRIVATE, metrics, prepare, read,
)
from summarize_reassembly import aligned

COMPARISONS = (
    ("TASK_LAST", "TASK_FIRST"),
    ("TASK_SEPARATE", "TASK_LAST"),
    ("TASK_SEPARATE", "SPECIALIST"),
)


def paired(cases, left, right):
    totals = {method: Counter() for method in (left, right)}
    outcomes, clean = Counter(), {method: Counter() for method in (left, right)}
    delta_limits = [0, 0]
    for values, flags in cases:
        cap = values["SPECIALIST"]["positions"]
        new, old = values[left], values[right]
        lo = (new["primary"] if new is not None else 0) - (old["primary"] if old is not None else cap)
        hi = (new["primary"] if new is not None else cap) - (old["primary"] if old is not None else 0)
        delta_limits[0] += lo
        delta_limits[1] += hi
        if not aligned(values, (left, right)):
            continue
        difference = new["primary"] - old["primary"]
        outcomes["wins" if difference > 0 else "losses" if difference < 0 else "ties"] += 1
        for arm in (left, right):
            totals[arm].update(values[arm])
        if flags[left] == flags[right] == []:
            for arm in (left, right):
                clean[arm].update(values[arm])
    return {"assigned": len(cases), "common": sum(outcomes.values()),
            "outcomes": outcomes, "totals": totals,
            "primary_delta_bounds_all_assigned": delta_limits,
            "pair_without_score_flags": clean}


def groups(cards, outcome):
    rows = {(r["uid"], r["method"]): r for r in outcome["rows"]}
    if len(rows) != len(cards) * len(ARMS) or len(rows) != len(outcome["rows"]):
        raise ValueError("Actor slots do not match frozen assignment")
    strata = defaultdict(list)
    for uid, card in cards.items():
        values = {method: metrics(card, rows[uid, method]["score"]) for method in ARMS}
        values["SPECIALIST"] = metrics(card, card["base_score"])
        if values["SPECIALIST"] is None:
            raise ValueError("Missing specialist denominator")
        flags = {method: rows[uid, method].get("score_flags") for method in ARMS}
        flags["SPECIALIST"] = card["base_flags"]
        strata[card["domain"]].append((values, flags))
        strata[card["domain"] + "/" + card["stratum"]].append((values, flags))
    return {label: {f"{x}_minus_{y}": paired(cases, x, y) for x, y in COMPARISONS}
            for label, cases in strata.items()}


def main():
    pin, cards, *_ = prepare()
    if pin != read(PRIVATE / "FROZEN.json"):
        raise ValueError("Frozen experimental roster no longer matches")
    result = read(PRIVATE / "RESULTS.json")
    print(json.dumps(groups(cards, result), indent=2))


if __name__ == "__main__":
    main()
