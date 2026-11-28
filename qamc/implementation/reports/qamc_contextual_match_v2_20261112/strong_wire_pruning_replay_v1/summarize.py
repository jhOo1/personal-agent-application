"""Publish only metrics and abbreviated task identifiers from exact-request replay."""
from collections import Counter
import json

from pathlib import Path
from runpy import run_path

runner = run_path(str(Path(__file__).with_name("run.py")))
PRIVATE, RUN, archive, prepare, sha, verify_frozen = (
    runner[k] for k in ("PRIVATE", "RUN", "archive", "prepare", "sha", "verify_frozen")
)
from summarize_reassembly import measure


def summarize():
    pin, cards, _ = prepare()
    verify_frozen(pin, archive.read(PRIVATE / "FROZEN.json"))
    data = archive.read(PRIVATE / "RESULTS.json")
    ledger = data["ledger"]
    receipts = []
    for file in RUN.glob("*/visible/*/record.json"):
        record = archive.read(file)
        if sha(archive.read(file.with_name("request.json"))) != record["request_sha256"]:
            raise ValueError("Receipt request mismatch")
        receipts.append(record)
    def key(record):
        return record["unit"]["stage"], record["request_sha256"], record["status"]

    if Counter(map(key, ledger)) != Counter(map(key, receipts)):
        raise ValueError("Unreconciled call ledger")
    if set(cards) != {r["uid"] for r in data["rows"]}:
        raise ValueError("Missing assignment in settlement")
    totals = {"BASE": Counter(), "PRUNED": Counter()}
    directions, roots = Counter(), []
    for row in data["rows"]:
        uid = row["uid"]
        base = measure("RPEval", row["stratum"], cards[uid]["base_score"])
        edited = measure("RPEval", row["stratum"], row["score"])
        if base and edited and base["positions"] != edited["positions"]:
            raise ValueError("Different denominators")
        if base and edited:
            delta = edited["primary"] - base["primary"]
            directions["win" if delta > 0 else "loss" if delta < 0 else "tie"] += 1
            for arm, metrics in (("BASE", base), ("PRUNED", edited)):
                totals[arm].update(metrics)
        roots.append({"case": "/".join(uid.split("/")[-2:]), "stratum": row["stratum"],
                      "baseline": base, "pruned": edited, "actor_status": row["actor_status"],
                      "score_flags": row.get("score_flags", [])})
    return {"assigned": len(cards), "paired": dict(directions), "totals": totals,
            "roots": roots, "calls": len(ledger), "statuses": Counter(r["status"] for r in ledger),
            "stages": Counter(r["unit"]["stage"] for r in ledger),
            "tokens": sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger),
            "usage_unknown": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
            "automatic_retries": sum(r["automatic_retries"] for r in ledger), "exact_reuse": data["exact_reuse"]}


if __name__ == "__main__":
    print(json.dumps(summarize(), indent=2, sort_keys=True))
