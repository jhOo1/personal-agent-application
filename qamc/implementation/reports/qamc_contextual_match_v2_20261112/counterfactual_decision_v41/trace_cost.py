"""Audit comparative review cost and self-reported decision traces on settled waves."""
from collections import Counter, defaultdict
import json
from statistics import median

from audit_completed import audited_rows
from run_v41 import ARMS, FINAL, OUT, read

DELTA, REVIEW = ARMS
USAGE = ("prompt_tokens", "completion_tokens", "total_tokens")


def samples():
    plan = read(OUT / "FROZEN.json")
    settled = [row for rows, _ in audited_rows(plan) for row in rows]
    shown = {row["uid"] for row in settled}
    receipts = []
    for index, uids in enumerate(plan["waves"]):
        if not set(uids) <= shown:
            break
        receipts.extend(read(OUT / f"wave_{index:02d}" / "COMPLETED.json")["ledger"])
    return plan, settled, receipts


def paired_stat(values):
    if not values:
        return {"paired": 0}
    left, right = zip(*values, strict=True)
    return {"paired": len(values), "review_median": median(left), "delta_median": median(right),
            "paired_median_delta": median(b - a for a, b in values),
            "review_sum": sum(left), "delta_sum": sum(right)}


def describe():
    plan, rows, receipts = samples()
    final_receipts = {r["request_sha256"]: r for r in receipts if r["stage"] == FINAL}
    physical = defaultdict(Counter)
    for row in receipts:
        key = row["stage"] + "/" + row["unit"]["method"]
        usage = row["usage"] or {}
        physical[key].update(requests=1, successes=row["status"] == "OK", unknown_usage=not usage)
        physical[key].update({field: usage.get(field, 0) for field in USAGE})

    coverage = Counter()
    trace = {arm: Counter() for arm in ARMS}
    series = defaultdict(list)
    for row in rows:
        by_arm = row["answers"]
        if any(by_arm[arm]["status"] != "OK" for arm in ARMS):
            continue
        left, right = (by_arm[m] for m in (REVIEW, DELTA))
        coverage["paired_answers"] += 1
        coverage["exactly_equal_answers"] += left["answer"] == right["answer"]
        if set(row["labels"]) == {"A"}:
            coverage["all_A"] += 1
        series["answer_characters"].append(tuple(len(cell["answer"]) for cell in (left, right)))
        series["change_records"].append(tuple(len(cell["changes"]) for cell in (left, right)))
        ids = {}
        for arm in ARMS:
            pairs = {(key, change["disposition"]) for change in by_arm[arm]["changes"]
                     for key in change["source_ids"]}
            ids[arm] = pairs
            trace[arm].update(change["disposition"] for change in by_arm[arm]["changes"])
            trace[arm]["rows_with_nonempty_trace"] += bool(by_arm[arm]["changes"])
        coverage["equal_source_disposition_sets"] += ids[REVIEW] == ids[DELTA]
        coverage["both_trace_no_sources"] += not (ids[REVIEW] or ids[DELTA])
        coverage["same_final_but_different_source_dispositions"] += (
            left["answer"] == right["answer"] and ids[REVIEW] != ids[DELTA]
        )
        wires = row["trace"]["review_sha256"]
        recorded = tuple(final_receipts[wires[method]] for method in (REVIEW, DELTA))
        for field in USAGE:
            both = [(cell["usage"] or {}).get(field) for cell in recorded]
            if all(type(value) is int for value in both):
                series[field].append(both)
        for field in ("elapsed_seconds", "reported_completion_minus_reasoning_tokens"):
            both = [cell.get(field) for cell in recorded]
            if all(type(value) in (int, float) for value in both):
                series[field].append(both)
        for arm, record in zip((REVIEW, DELTA), recorded, strict=True):
            trace[arm]["provider_completion_above_requested_limit"] += (
                record.get("reported_completion_over_requested") is True
            )
    return {"complete": len(rows) == len(plan["roots"]), "completed_roots": len(rows),
            "coverage": coverage, "review_trace": trace, "paired": {k: paired_stat(v) for k, v in series.items()},
            "physical": physical, "new_model_requests": 0,
            "caveats": ("Logical costs attribute one matched request to each row using its wire hash; the physical "
                        "ledger counts each dispatched request once. Completion usage is the provider report, "
                        "and may include internal tokens. Self-reported decisions are not inferred behavior.")}


if __name__ == "__main__":
    print(json.dumps(describe(), ensure_ascii=False, indent=2))
