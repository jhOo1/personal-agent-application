"""Publish aggregate endpoint comparisons while keeping raw tasks private."""
from collections import Counter
import json

from run_bridge import EXTERNAL, RUN, ZERO, read

METHODS = ("IPE_C", ZERO, *EXTERNAL)


def compare(rows, method):
    valid = [r for r in rows if r["scores"]["IPE_C"] and r["scores"][method]]
    pairs = [(r["scores"]["IPE_C"], r["scores"][method]) for r in valid]
    wins = sum(a["matched"] > b["matched"] for a, b in pairs)
    losses = sum(a["matched"] < b["matched"] for a, b in pairs)
    return {"pairs": len(valid), "source_groups": len({r["source_group"] for r in valid}),
            "match": [sum(x[i]["matched"] for x in pairs) for i in range(2)],
            "win_loss_tie": [wins, losses, len(valid) - wins - losses],
            "severity": {m: [sum(x[i]["severity"][m] for x in pairs) for i in range(2)]
                         for m in ("OPB", "UPB", "FM")}}


def summarize(results):
    rows, ledger = results["rows"], results["ledger"]
    if len(rows) != 24 or len({r["uid"] for r in rows}) != len(rows):
        raise ValueError("Lost a frozen root")
    slices = {"overall": rows}
    for field in ("label", "track"):
        for value in sorted({r[field] for r in rows}):
            slices[value] = [r for r in rows if r[field] == value]
    table = {}
    for label, cohort in slices.items():
        table[label] = {
            "planned": len(cohort), "route": Counter(r["route"] for r in cohort),
            "valid_match": {m: [sum(r["scores"][m]["matched"] for r in cohort if r["scores"][m]),
                                sum(r["scores"][m] is not None for r in cohort)] for m in METHODS},
            "pairs_vs_ipe_c": {m: compare(cohort, m) for m in METHODS[1:]},
        }
    return {"table": table, "requests": len(ledger), "request_status": Counter(r["status"] for r in ledger),
            "physical_stages": Counter(r["unit"]["stage"] for r in ledger),
            "reported_tokens": sum((r.get("usage") or {}).get("total_tokens", 0) or 0 for r in ledger),
            "unknown_usage": sum((r.get("usage") or {}).get("total_tokens") is None for r in ledger),
            "retries": sum(r.get("automatic_retries", 0) for r in ledger),
            "task_only_status": Counter(r["task_only_status"] for r in rows),
            "actor_origins": Counter(r["actor"]["origin"] for r in rows)}


if __name__ == "__main__":
    print(json.dumps(summarize(read(RUN / "RESULTS.json")), indent=2, sort_keys=True))
