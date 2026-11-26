"""Audit matched-cap receipt lineage and report de-identified infrastructure counts."""
import argparse
from collections import Counter
import json
from pathlib import Path

RUN = Path("runs/qamc_contextual_match_v2_20261112") / Path(__file__).parent.name
STAGES = ("Route", "Select", "Actor", "Judge")


def account(pin, checkpoint, wave):
    expected = {(uid, arm) for uid in pin["tracks"] for arm in pin["arms"]}
    rows = {(r["uid"], r["arm"]): r for r in checkpoint["rows"]}
    if len(rows) != len(checkpoint["rows"]) or rows.keys() != expected:
        raise ValueError("Incomplete or duplicate wave coordinates")
    if any(r["wave"] != wave or r["category"] != pin["tracks"][r["uid"]] for r in rows.values()):
        raise ValueError("Wave coordinates changed")
    ledger = checkpoint["ledger"]
    if len(ledger) > pin["cap"] // len(pin["orders"]):
        raise ValueError("Wave exceeded its frozen allocation")

    receipts, stages = {}, {}
    for stage in STAGES:
        prefix = f"Wave{wave}_{stage}"
        calls = [c for c in ledger if c["unit"]["stage"] == prefix]
        stages[stage] = {
            "physical_calls": len(calls),
            "statuses": Counter(c["status"] for c in calls),
            "reported_tokens": sum((c.get("usage") or {}).get("total_tokens", 0) for c in calls),
            "requests_without_usage": sum("total_tokens" not in (c.get("usage") or {}) for c in calls),
        }
        for c in calls:
            unit = c["unit"]
            if ((unit["root_id"], unit["method"]) not in expected
                    or c["automatic_retries"] != 0
                    or (stage in ("Route", "Select") and unit["method"] != "ROUTED")
                    or (stage == "Actor" and c.get("requested_max_tokens") != 8192)):
                raise ValueError("Receipt violates the allocation or Actor cap")
            key = (stage, unit["root_id"], c["request_sha256"])
            if key in receipts:
                raise ValueError("Same request physically dispatched twice")
            receipts[key] = c
    if len(receipts) != len(ledger):
        raise ValueError("Unknown stage in receipt ledger")
    referred = set()
    for (uid, _), row in rows.items():
        references = (("Actor", row["actor_sha256"], bool(row["answer"])),
                      ("Judge", row["judge"].get("request_sha256"), row["judge"].get("status") == "OK"))
        for stage, digest, delivered in references:
            if digest is None:
                if delivered:
                    raise ValueError("Missing ancestry for delivered result")
                continue
            key = (stage, uid, digest)
            if (receipts[key]["status"] == "OK") != delivered:
                raise ValueError("Result disagrees with physical receipt")
            referred.add(key)
    if referred != {k for k in receipts if k[0] in ("Actor", "Judge")}:
        raise ValueError("Unreferenced Actor or Judge dispatch")

    exposures = {}
    for track in set(pin["tracks"].values()):
        counts = Counter()
        for uid, category in pin["tracks"].items():
            if category != track:
                continue
            r = rows[uid, "ROUTED"]
            h = r["actor_sha256"]
            state = "no_actor"
            if h is not None:
                state = next((arm.lower() for arm in ("EMPTY", "FULL")
                              if h == rows[uid, arm]["actor_sha256"]), "proper_subset")
                if (state == "empty") != (r["selected_count"] == 0):
                    raise ValueError("Zero-history allocation and wire sharing differ")
            counts[state] += 1
        exposures[track] = counts
    return {"stages": stages, "routed_actor_allocations": exposures}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("waves", type=int, nargs="+", choices=(1, 2))
    args = parser.parse_args()
    load = lambda filename: json.loads((RUN / filename).read_text())
    pin = load("FROZEN.json")
    identity = load("EXECUTION.json")
    summary = {}
    for wave in sorted(set(args.waves)):
        saved = load(f"WAVE{wave}.json")
        if saved["identity"] != identity:
            raise ValueError("Wave identity does not match executed frozen configuration")
        summary[wave] = account(pin, saved, wave)
    print(json.dumps(summary, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
