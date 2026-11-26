"""Compute the frozen evidence checks without publishing matrices or task text."""
from collections import Counter
import json

from run_needs import RUN, read

ARMS = ("base", "independent", "cover")


def main():
    v = read(RUN / "RESULTS.json")
    usable = [r for r in v["rows"] if r["status"] == "OK"]
    if any(len(r[arm]) != len(r["base"]) for r in usable for arm in ARMS):
        raise ValueError("Unequal exposure budget")
    cases = {}
    for row in usable:
        uid = row["uid"]
        if uid not in v["criteria"]:
            continue
        criterion = v["criteria"][uid]
        required = set(criterion["positions"])
        cases[uid.split("/")[-1][:8]] = {
            "purpose": criterion["kind"], "required_count": len(required), "budget": len(row["base"]),
            "intersection": {arm: len(required.intersection(row[arm])) for arm in ARMS},
        }
    candidates = {
        arm: [case for case, r in cases.items() if r["purpose"] == "BU" and
              r["intersection"]["base"] < r["required_count"] == r["intersection"][arm]]
        for arm in ARMS[1:]
    }
    risk = {
        arm: [case for case, r in cases.items() if r["purpose"] == "RISK" and
              r["intersection"][arm] > r["intersection"]["base"]]
        for arm in ARMS[1:]
    }
    ledger = v["ledger"]
    print(json.dumps({"cases": cases,
                      "complete_recovery": candidates,
                      "risk_reexposure": risk,
                      "roster": len(v["rows"]),
                      "statuses": Counter(row["status"] for row in v["rows"]),
                      "need_counts": Counter(len(row["needs"]) for row in usable),
                      "changed_selection": {arm: sum(r[arm] != r["base"] for r in usable) for arm in ARMS[1:]},
                      "different_selection": sum(r["independent"] != r["cover"] for r in usable),
                      "physical_requests": len(ledger),
                      "reported_tokens": sum((r.get("usage") or {}).get("total_tokens", 0) or 0 for r in ledger),
                      "unknown_usage": sum((r.get("usage") or {}).get("total_tokens") is None for r in ledger),
                      "retries": sum(r.get("automatic_retries", 0) for r in ledger)},
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
