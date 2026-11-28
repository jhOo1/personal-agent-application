"""Aggregate archived answer scores, preserving failed decisions and unmatched scores."""
from collections import Counter, defaultdict
import json

from run_trial import ARMS, PRIVATE, RUN, archive, prepare, sha

BASELINE, ZERO = "IPE_C", "TASK_ONLY"
METHODS = (BASELINE, ZERO, *ARMS)


def summary():
    pin, tasks, jobs = prepare()
    if archive.read(PRIVATE / "FROZEN.json") != pin:
        raise ValueError("Frozen manifest drift")
    result = archive.read(PRIVATE / "RESULTS.json")
    entries = {(r["uid"], r["arm"]): r for r in result["rows"]}
    if len(entries) != len(result["rows"]) or set(entries) != set(jobs):
        raise ValueError("Duplicate or missing route")
    states = {}
    for (uid, arm), rec in entries.items():
        if rec["reply"]["request_sha256"] != sha(jobs[uid, arm]):
            raise ValueError("Route request hash changed")
        states[uid, arm] = rec["status"]
    receipts = []
    for p in RUN.glob("*/visible/*/record.json"):
        receipt = archive.read(p)
        if sha(archive.read(p.with_name("request.json"))) != receipt["request_sha256"]:
            raise ValueError("Stored receipt hash changed")
        receipts.append(receipt)

    def key(receipt):
        return receipt["unit"]["stage"], receipt["request_sha256"], receipt["status"]

    ledger = result["ledger"]
    if Counter(map(key, ledger)) != Counter(map(key, receipts)):
        raise ValueError("Unreconciled receipts")
    scores = defaultdict(lambda: {method: Counter() for method in METHODS})
    pair = Counter()
    choices = defaultdict(Counter)
    details = []
    for uid, task in tasks.items():
        row, stratum = task["row"], task["stratum"]
        selections = {arm: ZERO if entries[uid, arm]["route"] == ZERO else BASELINE for arm in ARMS}
        names = {BASELINE: BASELINE, ZERO: ZERO} | selections
        cells = {method: row["scores"][selected] for method, selected in names.items()}
        complete = all(c and c["grade"] and c["grade"].get("match") for c in cells.values())
        clean = complete and not any(c["flags"] for c in cells.values())
        metrics = {}
        for arm in ARMS:
            choices[arm][selections[arm]] += 1
        if complete:
            positions = len(row["labels"])
            for name, c in cells.items():
                g = c["grade"]
                if g["match"]["positions"] != positions:
                    raise ValueError("Endpoint Match denominator changed")
                metrics[name] = {"match": g["match"]["matched"], "positions": positions,
                                 **{metric: g[metric] for metric in ("OPB", "UPB", "FM")}}
                for cohort in ["all", stratum, *(["unflagged"] if clean else [])]:
                    scores[cohort][name].update(metrics[name])
                    scores[cohort][name]["tasks"] += 1
            for comparator in (BASELINE, "DIRECT"):
                delta = metrics["RESIDUAL"]["match"] - metrics[comparator]["match"]
                direction = "win" if delta > 0 else "loss" if delta < 0 else "tie"
                pair[f"{comparator}/{direction}"] += 1
        details.append({"case": "/".join(uid.split("/")[-2:]), "stratum": stratum,
                        "routes": selections, "statuses": {arm: states[uid, arm] for arm in ARMS},
                        "common_valid": complete, "unflagged": clean, "scores": metrics})
    return {"rows": details, "totals": scores, "pairwise": pair, "choices": choices,
            "router_status": Counter(states.values()), "calls": len(ledger), "archive": result["archive"],
            "tokens": sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger),
            "transport_status": Counter(r["status"] for r in ledger),
            "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
            "retries": sum(r["automatic_retries"] for r in ledger)}


if __name__ == "__main__":
    print(json.dumps(summary(), sort_keys=True, indent=2))
