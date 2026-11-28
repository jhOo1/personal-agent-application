"""Report observed score deltas and independently reconcile physical requests."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "transactional_reassembly_v1"))

from trial import ARMS, PRIVATE, RUN, archive, freeze, sha
from summarize_reassembly import aligned, bounds, measure, paired


def settlement():
    info, cards, _ = freeze()
    if archive.read(PRIVATE / "FROZEN_HASHES.json") != info:
        raise ValueError("Frozen roster changed")
    result = archive.read(PRIVATE / "RESULTS.json")
    output = {(r["uid"], r["method"]): r for r in result["rows"]}
    changed = set(result["changed_requests"])
    compare, delivered, audits = defaultdict(list), defaultdict(Counter), defaultdict(Counter)
    for uid, card in cards.items():
        domain, stratum = card["benchmark"], card["stratum"]
        record = result["audits"].get(uid)
        audits[domain]["assigned"] += 1
        if record is not None:
            audits[domain]["valid_review"] += 1
            audits[domain]["invalid_open_default_spans"] += record["invalid_witnesses"]
            audits[domain]["changed_request"] += uid in changed
            audits[domain]["removed_sources"] += len(set(record["kept"][ARMS[0]]) - set(record["kept"][ARMS[1]]))
        scores = {"BASE": measure(domain, stratum, card["base_score"])}
        for arm in ARMS:
            row = output.get((uid, arm), {})
            scores[arm] = measure(domain, stratum, row.get("score"))
            delivered[domain][arm + ".answers"] += bool(row.get("answer"))
            delivered[domain][arm + ".scores"] += scores[arm] is not None
        if scores["BASE"] is None:
            raise ValueError("Missing valid enrollment score")
        entry = card, {arm: output.get((uid, arm), {}) for arm in ARMS}, scores
        compare[domain].append(entry)
        compare[f"{domain}/{stratum}"].append(entry)
        if uid in changed:
            compare[f"{domain}/changed"].append(entry)
    comparisons = {}
    for name, rows in compare.items():
        counts = Counter()
        for _, _, grades in rows:
            if aligned(grades, ARMS):
                delta = grades[ARMS[1]]["primary"] - grades[ARMS[0]]["primary"]
                counts["win" if delta > 0 else "loss" if delta < 0 else "tie"] += 1
        scopes = [("matched_arms", ARMS), ("incl_archived", ("BASE", *ARMS))]
        comparisons[name] = {"assigned": len(rows), "directions": counts,
                **{label: paired(rows, scope) for label, scope in scopes},
                "assigned_delta_bound": bounds(rows, ARMS[1], ARMS[0])}
    ledger = result["ledger"]
    receipts = []
    for file in RUN.glob("*/visible/*/record.json"):
        record = archive.read(file)
        if sha(archive.read(file.with_name("request.json"))) != record["request_sha256"]:
            raise ValueError("Archived physical request identity mismatch")
        receipts.append(record)
    tag = lambda r: (r["unit"]["stage"], r["request_sha256"], r["status"])
    if Counter(map(tag, receipts)) != Counter(map(tag, ledger)):
        raise ValueError("Receipt ledger mismatch")
    return {"qualified": result["qualified"], "audits": audits, "delivered": delivered,
            "exact_reuse": result["exact_reuse"],
            "comparisons": comparisons, "physical_calls": len(ledger),
            "stages": Counter(r["unit"]["stage"] for r in ledger),
            "statuses": Counter(r["status"] for r in ledger),
            "reported_tokens": sum((r["usage"] or {}).get("total_tokens", 0) for r in ledger),
            "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
            "automatic_retries": sum(r["automatic_retries"] for r in ledger)}


if __name__ == "__main__":
    print(json.dumps(settlement(), ensure_ascii=False, indent=2))
