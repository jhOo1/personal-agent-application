"""Separate what RPEval's aggregate native scores can imply about A, B and C."""
from collections import Counter
from functools import lru_cache
import json

from qamc_rpeval_rubric_consistency_audit import TRANSITION_BITS

from audit_completed import EDGES, audited_rows
from run_v41 import OUT, read

# Pairs are in author-label, judged-label order. Diagonal choices count as Match.
TRANSITIONS = dict(zip(("AC", "BC", "BA", "CA", "AB", "CB"),
                       ("OPB", "OPB", "UPB", "UPB", "RII", "RII"), strict=True))
EVENTS = ("A_misuse", "B_omitted", "B_overstated", "C_omitted", "C_weakened")
EVENT_BY_TRANSITION = {"AB": 0, "AC": 0, "BA": 1, "BC": 2, "CA": 3, "CB": 4}
PROTECTED_LABEL = ("A", "B", "B", "C", "C")


@lru_cache(maxsize=None)
def feasible(labels, match, present=0, absent=0):
    """Enumerate attainable error-event counts and flags without attributing individual positions."""
    errors = len(labels) - match
    states = {(0, 0, 0, 0, 0, 0)}
    for gold in labels:
        next_states = states.copy()
        for state in states:
            if sum(state[:-1]) >= errors:
                continue
            for inferred in "ABC":
                if gold == inferred:
                    continue
                transition = gold + inferred
                flag = TRANSITION_BITS[TRANSITIONS[transition]]
                if flag & absent:
                    continue
                event = EVENT_BY_TRANSITION[transition]
                counts = list(state[:-1])
                counts[event] += 1
                next_states.add((*counts, state[-1] | flag))
        states = next_states
    valid = [state[:-1] for state in states if sum(state[:-1]) == errors and state[-1] & present == present]
    return (tuple((min(col), max(col)) for col in zip(*valid, strict=True)) if valid else None)


def cell_bounds(labels, fields):
    match = fields.get("match")
    if match is None:
        return None
    if match["positions"] != len(labels) or not 0 <= match["matched"] <= len(labels):
        raise ValueError("Native Match denominator changed")
    present = sum(flag for name, flag in TRANSITION_BITS.items()
                  if name in fields and fields[name] > 0)
    absent = sum(flag for name, flag in TRANSITION_BITS.items()
                 if name in fields and fields[name] == 0)
    return {
        "match_only": feasible(labels, match["matched"]),
        "bias_conditioned": feasible(labels, match["matched"], present, absent),
    }


def add_pair(totals, left, right, labels, identity):
    totals["roots"] += 1
    amount = Counter(labels)
    for i, (name, label) in enumerate(zip(EVENTS, PROTECTED_LABEL, strict=True)):
        lo_left, hi_left = left[i]
        lo_right, hi_right = right[i]
        totals[f"{name}.positions"] += amount[label]
        totals[f"{name}.left_lo"] += lo_left
        totals[f"{name}.left_hi"] += hi_left
        totals[f"{name}.right_lo"] += lo_right
        totals[f"{name}.right_hi"] += hi_right
        totals[f"{name}.delta_lo"] += 0 if identity else lo_right - hi_left
        totals[f"{name}.delta_hi"] += 0 if identity else hi_right - lo_left


def audit_label_bounds():
    plan = read(OUT / "FROZEN.json")
    roots = {root["uid"]: root for root in plan["roots"]}
    buckets = ("all", "all_A", "contains_BC")
    lenses = ("match_only", "bias_conditioned")
    pairs = {f"{left}__{right}": {bucket: {lens: Counter() for lens in lenses} for bucket in buckets}
             for left, right in EDGES}
    complete = 0
    incompatible = Counter()
    for rows, _ in audited_rows(plan):
        for row in rows:
            complete += 1
            labels = row["labels"]
            fields = {method: cell["fields"] for method, cell in row["native"].items()}
            bounds = {method: cell_bounds(labels, value) for method, value in fields.items()}
            answers = {method: cell["answer"] for method, cell in
                       {**roots[row["uid"]]["archived"], **row["answers"]}.items()}
            for method, value in bounds.items():
                if value and value["bias_conditioned"] is None:
                    incompatible[method] += 1
            for left, right in EDGES:
                if bounds[left] is None or bounds[right] is None:
                    continue
                scope = pairs[f"{left}__{right}"]
                identity = (answers[left] == answers[right]
                            and row["native"][left]["raw"] == row["native"][right]["raw"])
                for lens in lenses:
                    lvalue, rvalue = bounds[left][lens], bounds[right][lens]
                    if lvalue is None or rvalue is None:
                        continue
                    for tag in ("all", "all_A" if set(labels) == {"A"} else "contains_BC"):
                        add_pair(scope[tag][lens], lvalue, rvalue, labels, identity)
    return {"planned_roots": len(plan["roots"]), "completed_roots": complete,
            "complete": complete == len(plan["roots"]), "incompatible_native_cells": incompatible,
            "pairs": pairs, "new_model_requests": 0,
            "interpretation": ("Bounds conditional on native Match and optionally bias-presence signals. "
                               "They are neither observed per-memory labels nor behavior verdicts. "
                               "Incompatible cells stay in the Match-only lens and original scores.")}


if __name__ == "__main__":
    print(json.dumps(audit_label_bounds(), ensure_ascii=False, indent=2))
