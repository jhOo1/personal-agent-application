"""Render public, numeric paired results from frozen private receipts."""
from collections import Counter, defaultdict
import json
from pathlib import Path
from runpy import run_path

HERE = Path(__file__).resolve().parent
experiment = run_path(str(HERE / "trial.py"))
prior = run_path(str(HERE.parent / "foil_anchored_decision_repair_v1/public_summary.py"))
ARMS = ("BASE", *experiment["ARMS"])


def main():
    cards, _, _, pin = experiment["prepare"]()
    read = experiment["read"]
    private = experiment["PRIVATE"]
    if pin != read(private / "FREEZE.json"):
        raise ValueError("Frozen request mismatch")
    saved = read(private / "SETTLED.json")
    ledger = saved["ledger"]
    actual = [read(path) for path in experiment["RUN"].glob("*/visible/*/record.json")]
    def ledger_key(row):
        return row["unit"]["stage"], row["request_sha256"], row["status"]
    if Counter(map(ledger_key, ledger)) != Counter(map(ledger_key, actual)):
        raise ValueError("Physical request reconciliation failed")

    pairs = defaultdict(dict)
    for row in saved["rows"]:
        uid, arm = row["uid"], row["method"]
        if uid not in cards or arm in pairs[uid]:
            raise ValueError("Unknown or duplicate assigned row")
        pairs[uid][arm] = row
    stats = defaultdict(lambda: defaultdict(Counter))
    plans = Counter()
    for uid, info in cards.items():
        bench, stratum = info["benchmark"], info["stratum"]
        track = f"{bench}/{stratum}" if bench == "PersistBench" else bench
        grouped = pairs[uid]
        if set(grouped) != set(ARMS[1:]):
            raise ValueError("Missing paired slot")
        grouped["BASE"] = {"score": info["base_score"], "score_flags": info["base_flags"]}
        current = {}
        stats[track]["coverage"]["assigned"] += 1
        for arm, row in grouped.items():
            formal = row["score"]
            if arm != "BASE":
                plans[f"{arm}/{row['disposition']}"] += 1
            stats[track]["coverage"][f"{arm}/scored"] += formal is not None
            if formal is None:
                continue
            portable = {"benchmark": bench, "stratum": stratum, "score": formal}
            if bench == "RPEval":
                portable["score"] = formal.get("match")
                portable["bias"] = {key: formal.get(key) for key in ("OPB", "UPB", "FM")}
            current[arm] = prior["numeric_score"](portable)
        if set(current) != set(ARMS) or any(not v for v in current.values()):
            continue
        stats[track]["coverage"]["common"] += 1
        clean = not any(row["score_flags"] for row in grouped.values())
        if clean:
            stats[track]["coverage"]["common_unflagged"] += 1
        for arm, metric in current.items():
            stats[track][arm].update(metric)
            if clean:
                stats[track][f"unflagged/{arm}"].update(metric)
    print(json.dumps({
        "results": stats, "plans": plans, "stages": Counter(row["unit"]["stage"] for row in ledger),
        "statuses": Counter(row["status"] for row in ledger),
        "tokens": sum((row["usage"] or {}).get("total_tokens", 0) for row in ledger),
        "unknown_usage": sum("total_tokens" not in (row["usage"] or {}) for row in ledger),
        "retries": sum(row["automatic_retries"] for row in ledger),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
