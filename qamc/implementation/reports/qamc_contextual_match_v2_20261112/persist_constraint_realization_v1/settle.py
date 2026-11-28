"""Verify frozen requests and summarize separate strict-use outcomes per scorer."""
from collections import Counter
import json
from pathlib import Path
from runpy import run_path

trial = run_path(str(Path(__file__).with_name("trial.py")))
PRIVATE, RUN, archive, prepare, sha = (trial[k] for k in ("PRIVATE", "RUN", "archive", "prepare", "sha"))


def settle():
    pin, old, jobs, _ = prepare()
    if pin != archive.read(PRIVATE / "FROZEN.json"):
        raise ValueError("Frozen manifest drift")
    data = archive.read(PRIVATE / "RESULTS.json")
    assigned = {(r["uid"], r["arm"]): r for r in data["rows"]}
    if set(assigned) != jobs.keys() or len(assigned) != len(data["rows"]):
        raise ValueError("Dropped assignment")
    for key, r in assigned.items():
        if r["actor"]["request_sha256"] != sha(jobs[key]):
            raise ValueError("Stored Actor request differs")
    receipts = []
    for record_file in RUN.glob("*/visible/*/record.json"):
        record = archive.read(record_file)
        if sha(archive.read(record_file.with_name("request.json"))) != record["request_sha256"]:
            raise ValueError("Physical request differs")
        receipts.append(record)

    def identity(row):
        return row["unit"]["stage"], row["request_sha256"], row["status"]

    ledger = data["ledger"]
    if Counter(map(identity, receipts)) != Counter(map(identity, ledger)):
        raise ValueError("Physical ledger mismatch")
    counts = {grader: {} for grader in ("GPT", "Qwen")}
    pairs = {grader: {} for grader in counts}
    arms = sorted({r["arm"] for r in assigned.values()})
    by_uid = {case["uid"]: case for case in pin["cases"]}
    rows = []
    for uid, card in by_uid.items():
        row = {"case": uid.rsplit("/", 1)[-1][:8], "added_sources": card["added"],
               "ratings": {arm: {} for arm in arms}}
        for grader in counts:
            for arm in arms:
                metric = assigned[uid, arm][grader]
                rating = metric["rating"]
                status = "unknown" if rating is None else "pass" if rating == 3 else "fail"
                counts[grader].setdefault(arm, Counter())[status] += 1
                row["ratings"][arm][grader] = metric
            for left, right in (("FRESH_DIRECT", "FRESH_CONDITIONAL"),
                                ("RESTORED_DIRECT", "RESTORED_CONDITIONAL"),
                                ("FRESH_DIRECT", "RESTORED_DIRECT"),
                                ("FRESH_CONDITIONAL", "RESTORED_CONDITIONAL")):
                a, b = (assigned[uid, arm][grader]["rating"] for arm in (left, right))
                delta = None if a is None or b is None else int(b == 3) - int(a == 3)
                result = "unknown" if delta is None else "win" if delta == 1 else "loss" if delta == -1 else "tie"
                pairs[grader].setdefault(left + "/" + right, Counter())[result] += 1
        row["reference"] = {arm: {g: old[uid, arm][g] for g in counts} for arm in ("SELECTED", "FULL", "RUBRIC")}
        rows.append(row)
    return {"source_groups": len(rows), "per_case": rows, "strict": counts, "pairs": pairs,
            "requests": len(ledger), "statuses": Counter(r["status"] for r in ledger),
            "stages": Counter(r["unit"]["stage"] for r in ledger), "archive": data["archive"],
            "tokens": sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger),
            "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
            "retries": sum(r["automatic_retries"] for r in ledger)}


if __name__ == "__main__":
    print(json.dumps(settle(), sort_keys=True, indent=2))
