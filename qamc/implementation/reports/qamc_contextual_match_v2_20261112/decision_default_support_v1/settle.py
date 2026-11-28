"""Validate the saved intervention and count only common valid RPEval scores."""
from collections import Counter
import json

from run_trial import ARMS, PRIVATE, RUN, archive, prepare, sha
from summarize_reassembly import measure


def summarize():
    pin, cards, jobs = prepare()
    if pin != archive.read(PRIVATE / "FROZEN.json"):
        raise ValueError("Frozen comparison drift")
    data = archive.read(PRIVATE / "RESULTS.json")
    indexed = {(r["uid"], r["method"]): r for r in data["rows"]}
    if set(indexed) != set(jobs) or len(indexed) != len(data["rows"]):
        raise ValueError("Missing or duplicate outputs")
    receipts = [archive.read(p) for p in RUN.glob("*/visible/*/record.json")]
    ledger = data["ledger"]
    def receipt_key(r):
        return r["unit"]["stage"], r["request_sha256"], r["status"]

    if Counter(map(receipt_key, receipts)) != Counter(map(receipt_key, ledger)):
        raise ValueError("Ledger mismatch")
    rows, excluded = [], []
    totals = {arm: Counter() for arm in ("ARCHIVE", *ARMS)}
    direction = {arm: Counter() for arm in ("ARCHIVE", "DIRECT")}
    for uid, card in cards.items():
        stratum = card["stratum"]
        metrics = {"ARCHIVE": measure("RPEval", stratum, card["base_score"])}
        flags = {}
        for arm in ARMS:
            rec = indexed[uid, arm]
            metrics[arm] = measure("RPEval", stratum, rec["score"])
            flags[arm] = rec.get("score_flags", [])
        short = "/".join(uid.split("/")[-2:])
        if any(m is None for m in metrics.values()):
            excluded.append(short)
        else:
            if len({m["positions"] for m in metrics.values()}) != 1:
                raise ValueError("Denominator mismatch")
            for arm, summary in metrics.items():
                totals[arm].update(summary)
            for comparison in direction:
                delta = metrics["SUPPORTED_DEFAULT"]["primary"] - metrics[comparison]["primary"]
                direction[comparison]["win" if delta > 0 else "loss" if delta < 0 else "tie"] += 1
        rows.append({"case": short, "metrics": metrics, "new_flags": flags})
    return {"assigned": len(cards), "common": len(cards) - len(excluded),
            "excluded": excluded, "totals": totals, "paired": direction, "rows": rows,
            "physical_calls": len(ledger), "statuses": Counter(r["status"] for r in ledger),
            "tokens": sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger),
            "usage_unknown": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
            "automatic_retries": sum(r["automatic_retries"] for r in ledger), "exact_reuse": data["exact_reuse"]}


if __name__ == "__main__":
    print(json.dumps(summarize(), sort_keys=True, indent=2))
