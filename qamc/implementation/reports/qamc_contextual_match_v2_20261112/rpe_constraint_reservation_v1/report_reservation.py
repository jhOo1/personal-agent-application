"""Summarize the frozen conditional reservation comparison from saved receipts."""
from collections import Counter, defaultdict
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE.parents[2] / "runs" / HERE.parent.name / HERE.name
ARMS = ("GATE_BASE", "RESERVED", "TOP_NEXT")
CONTROLS = ("IPE_C", "RPR_PAPER_FULL")
METRICS = ("OPB", "UPB", "FM")


def read(path):
    return json.loads(path.read_text())


def grade(row, method):
    if method in ARMS:
        return row["arms"][method]["score"]
    return row["controls"][method]


def match(score, positions):
    met = (score or {}).get("grade", {}).get("match")
    if met is None:
        return None
    if met["positions"] != positions or not 0 <= met["matched"] <= positions:
        raise ValueError("Outcome does not match the assigned positions")
    return met["matched"]


def compare(rows, first, other):
    pairs, clean, changed = Counter(), Counter(), Counter()
    severity, group_changes = defaultdict(Counter), Counter()
    low = high = 0
    missing = Counter()
    for row in rows:
        n = len(row["labels"])
        a, b = grade(row, first), grade(row, other)
        x, y = match(a, n), match(b, n)
        low += (0 if x is None else x) - (n if y is None else y)
        high += (n if x is None else x) - (0 if y is None else y)
        missing.update(first=x is None, second=y is None, both=x is None and y is None)
        if x is None or y is None:
            continue
        outcome = {"tasks": 1, "positions": n, "first": x, "second": y,
                   "win": x > y, "loss": x < y, "tie": x == y}
        pairs.update(outcome)
        group_changes[row["group_id"]] += x - y
        if a["flags"] == b["flags"] == []:
            clean.update(outcome)
        if first in ARMS and other in ARMS:
            if row["arms"][first]["request_sha256"] != row["arms"][other]["request_sha256"]:
                changed.update(outcome)
            elif a != b:
                raise ValueError("Same wire scored twice")
        for metric in METRICS:
            if metric in a["grade"] and metric in b["grade"]:
                severity[metric].update(first=a["grade"][metric], second=b["grade"][metric], tasks=1)
    return {"match": pairs, "severity": severity, "flags_excluded": clean, "distinct_wires": changed,
            "bound_of_match_difference": [low, high], "missing": missing,
            "group_counts": {"win": sum(v > 0 for v in group_changes.values()),
                             "loss": sum(v < 0 for v in group_changes.values()),
                             "tie": sum(v == 0 for v in group_changes.values())},
            "allocation": {"tasks": len(rows), "positions": sum(len(r["labels"]) for r in rows)}}


def report(results, plan):
    rows, ledger = results["rows"], results["ledger"]
    if len(rows) != 34 or {r["uid"] for r in rows} != plan["rows"].keys():
        raise ValueError("Incomplete reservation allocation")
    if sum(r["previous_trial"] for r in rows) != 5 or len({r["group_id"] for r in rows}) != 21:
        raise ValueError("Task and source-group accounting changed")
    split = {
        "all": rows,
        "other_exposed": [r for r in rows if not r["previous_trial"]],
        "previous_trial": [r for r in rows if r["previous_trial"]],
        "ALL_A": [r for r in rows if set(r["labels"]) == {"A"}],
        "ONLY_B": [r for r in rows if "B" in r["labels"] and "C" not in r["labels"]],
        "CONTAINS_C": [r for r in rows if "C" in r["labels"]],
    }
    comparators = (("RESERVED", "TOP_NEXT"), ("RESERVED", "GATE_BASE"), ("TOP_NEXT", "GATE_BASE"),
                   *(("RESERVED", baseline) for baseline in CONTROLS))
    statuses, lengths = defaultdict(Counter), defaultdict(Counter)
    for row in rows:
        base, reserved, top = (set(row["arms"][arm]["ids"]) for arm in ARMS)
        if (
            not base < reserved or not base < top or len(reserved) != len(top) or len(top) != len(base) + 1
            or row["group_id"] != plan["rows"][row["uid"]]["group_id"]
        ):
            raise ValueError("Arms do not use exactly one added slot")
        for arm in ARMS:
            part = row["arms"][arm]
            statuses[arm][part["status"]] += 1
            lengths[arm].update(characters=part["original_characters"], sources=len(part["ids"]))
    return {"comparisons": {f"{a}/{b}": {name: compare(s, a, b) for name, s in split.items()}
                            for a, b in comparators},
            "statuses": statuses, "input_original_source_length": lengths,
            "physical_requests": Counter(r["unit"]["stage"] for r in ledger),
            "request_statuses": Counter(r["status"] for r in ledger),
            "reported_tokens": sum((r.get("usage") or {}).get("total_tokens") or 0 for r in ledger),
            "unknown_usage": sum("total_tokens" not in (r.get("usage") or {}) for r in ledger)}


if __name__ == "__main__":
    print(json.dumps(report(read(RUN / "RESULTS.json"), read(RUN / "ANSWER_PRIVATE.json")),
                     indent=2, sort_keys=True))
