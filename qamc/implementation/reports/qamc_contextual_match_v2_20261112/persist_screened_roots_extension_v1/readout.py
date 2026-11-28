"""Validate the extension's scoreboard and physical-request ledger offline."""
from collections import Counter
import json

from first_draw import POLICIES, PRIVATE, RUN, read, summarize
from verify_screened import prepare


def verify():
    pin, _, _, _, _ = prepare()
    if read(RUN / "FROZEN_PREFLIGHT.json") != pin:
        raise ValueError("Prior screening roster mismatch")
    result = read(PRIVATE / "RESULTS.json")
    ledger, rows = result["ledger"], result["rows"]
    expected = pin["rows"]
    if len(rows) != len(expected) or {r["uid"] for r in rows} != set(expected):
        raise ValueError("An assigned root is missing or duplicated")
    for row in rows:
        if row["track"] != expected[row["uid"]]["track"]:
            raise ValueError("Scoring track changed")
        if set(row["ratings"]) != set(POLICIES) or set(row["actor_status"]) != set(POLICIES):
            raise ValueError("An allocated answer path is missing")
        if not all(r is None or (type(r) is int and 1 <= r <= 5) for r in row["ratings"].values()):
            raise ValueError("Rating outside the protocol")
        count = row["subsets"]
        if count is not None:
            endpoint = "FULL" if count else "EMPTY"
            if (row["ratings"]["GROUP"], row["actor_status"]["GROUP"]) != (
                    row["ratings"][endpoint], row["actor_status"][endpoint]):
                raise ValueError("Grouped switch does not reproduce its fixed endpoint")
    reconstructed = summarize(rows)
    if json.loads(json.dumps(reconstructed)) != result["summary"]:
        raise ValueError("Paired scoreboard differs from the assigned scores")
    receipts = [read(p) for p in RUN.glob("*/visible/*/record.json")]
    signature = lambda r: (r["unit"]["stage"], r["request_sha256"], r["status"])
    if Counter(map(signature, ledger)) != Counter(map(signature, receipts)):
        raise ValueError("Physical ledger differs from the saved receipts")
    return {"assigned": pin["tracks"], "scoreboard": reconstructed, "cache": result["cache"],
            "requests": len(ledger), "stages": Counter(x["unit"]["stage"] for x in ledger),
            "statuses": Counter(x["status"] for x in ledger),
            "reported_tokens": sum((x["usage"] or {}).get("total_tokens", 0) for x in ledger),
            "unknown_usage": sum("total_tokens" not in (x["usage"] or {}) for x in ledger),
            "automatic_retries": sum(x["automatic_retries"] for x in ledger)}


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
