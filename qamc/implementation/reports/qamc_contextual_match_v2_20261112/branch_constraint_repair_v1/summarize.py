"""Reconcile archived scores and physical receipts for the branch experiment."""
import json
from collections import Counter, defaultdict

from trial import ARMS, COUNTS, PRIVATE, RUN, archive, prepare
from summarize_reassembly import aligned, bounds, measure, paired


def readout():
    plan, panel, _ = prepare()
    if archive.read(PRIVATE / "FROZEN_HASHES.json") != plan:
        raise ValueError("Frozen identity drift")
    outcome = archive.read(PRIVATE / "RESULTS.json")
    rows = {(r["uid"], r["method"]): r for r in outcome["rows"]}
    parts = defaultdict(list)
    counts = {b: Counter() for b in COUNTS}
    for uid, card in panel.items():
        track, stratum = card["benchmark"], card["stratum"]
        evidence = outcome["witnesses"]
        disposition = "BYPASS" if evidence.get(uid) else "KEEP" if uid in evidence else "NO_WITNESS"
        counts[track][disposition] += 1
        observed = {arm: rows.get((uid, arm), {}) for arm in ARMS}
        metrics = {"BASE": measure(track, stratum, card["base_score"])}
        for arm, receipt in observed.items():
            score = receipt.get("score")
            metrics[arm] = measure(track, stratum, score)
            if receipt.get("answer"):
                counts[track][f"{arm}.delivered"] += 1
                counts[track][f"{arm}.changed"] += receipt["answer"] != card["base_answer"]
        if metrics["BASE"] is None:
            raise ValueError("Invalid matched archived reference")
        triple = card, observed, metrics
        parts[track].append(triple)
        parts[f"{track}/{stratum}"].append(triple)
    ledger = outcome["ledger"]
    records = [archive.read(path) for path in RUN.glob("*/visible/*/record.json")]
    key = lambda r: (r["unit"]["stage"], r["request_sha256"], r["status"])
    if Counter(map(key, records)) != Counter(map(key, ledger)):
        raise ValueError("Physical ledger mismatch")
    labels = ("BASE", *ARMS)
    result = {"gates": outcome["gates"], "audit_counts": counts, "comparisons": {},
              "physical_requests": len(ledger), "stages": Counter(r["unit"]["stage"] for r in ledger),
              "statuses": Counter(r["status"] for r in ledger),
              "automatic_retries": sum(r["automatic_retries"] for r in ledger),
              "known_tokens": sum((r["usage"] or {}).get("total_tokens", 0) for r in ledger),
              "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger)}
    for key, entries in parts.items():
        common = paired(entries, labels)
        support = Counter()
        for _, _, grades in entries:
            if aligned(grades, labels):
                for reference in labels[:-1]:
                    diff = grades["BRANCH_PATCH"]["primary"] - grades[reference]["primary"]
                    support[reference + ("_win" if diff > 0 else "_loss" if diff < 0 else "_tie")] += 1
        result["comparisons"][key] = {"assigned": len(entries), "common": common,
                                      "pair_directions": support,
                                      "assigned_primary_delta_bounds": {a: bounds(entries, "BRANCH_PATCH", a)
                                                                      for a in labels[:-1]}}
    return result


if __name__ == "__main__":
    print(json.dumps(readout(), ensure_ascii=False, indent=2))
