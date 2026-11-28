"""Reconcile original BenchPreS grading with the task-only request contrast."""
from collections import Counter
import json
from pathlib import Path
from runpy import run_path

trial = run_path(str(Path(__file__).with_name("trial.py")))
PRIVATE, RUN, archive, prepare, sha = (trial[k] for k in ("PRIVATE", "RUN", "archive", "prepare", "sha"))
METHODS = ("base", "external", "FREE", "LOCKED")


def settle():
    pin, cards, _, _ = prepare()
    if pin != archive.read(PRIVATE / "FROZEN.json"):
        raise ValueError("Frozen roster mismatch")
    data = archive.read(PRIVATE / "RESULTS.json")
    answers = {(label, arm): text for label, arm, text in data["answers"]}
    if set(data["metrics"]) != set(cards):
        raise ValueError("Dropped allocation")
    for (label, arm), answer in answers.items():
        if arm == "LOCKED" and answer.count(data["proposed"][label]) != 1:
            raise ValueError("Action was not preserved exactly")
    ledger = data["ledger"]
    receipts = []
    for record in RUN.glob("*/visible/*/record.json"):
        entry = archive.read(record)
        if sha(archive.read(record.with_name("request.json"))) != entry["request_sha256"]:
            raise ValueError("Request/receipt mismatch")
        receipts.append(entry)

    def key(r):
        return r["unit"]["stage"], r["request_sha256"], r["status"]

    if Counter(map(key, receipts)) != Counter(map(key, ledger)):
        raise ValueError("Unreconciled physical call ledger")
    totals = {a: Counter() for a in METHODS}
    sizes = {}
    for label, scores in data["metrics"].items():
        sizes[label] = {a: len(answers[label, a].split()) for a in trial["ARMS"] if (label, a) in answers}
        if not all(scores[a] for a in METHODS):
            continue
        for a, m in scores.items():
            cell = totals[a]
            cell.update(tasks=1, completeness=m["completeness"])
            for field in ("aar", "nonbold", "mr"):
                cell.update({field: m[field][0], field + "_n": m[field][1]})
    return {"results": data["metrics"], "totals": totals, "words": sizes, "failures": data["failures"],
            "physical": len(ledger), "stages": Counter(r["unit"]["stage"] for r in ledger),
            "statuses": Counter(r["status"] for r in ledger), "archive_reuse": data["reuse"],
            "tokens": sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger),
            "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
            "retries": sum(r["automatic_retries"] for r in ledger)}


if __name__ == "__main__":
    print(json.dumps(settle(), sort_keys=True, indent=2))
