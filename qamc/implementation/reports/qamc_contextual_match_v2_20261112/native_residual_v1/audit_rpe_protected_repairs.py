"""Locate retrospective, comparable RPEval answer pairs for behavior inspection."""
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "ipe_c_two_endpoint_completion_v1" / "RESULTS.json"
METHODS = ROOT / "rpeval_formal_multi_coverage_v1" / "RESULT_ROWS.json"
PROTECTION = ("OPB", "UPB", "FM")


def read(path):
    return json.loads(path.read_text())


def scan():
    base = {r["uid"]: r for r in read(BASE)["rows"]}
    counts = defaultdict(Counter)
    candidates = []
    for row in read(METHODS):
        record = base[row["uid"]]
        labels = record["labels"]
        if not labels or set(labels) == {"A"}:
            continue
        stratum = "contains_C" if "C" in labels else "only_B"
        key = stratum, row["method"]
        counter = counts[key]
        counter["allocated"] += 1
        reference = record["ipe_c"]
        old = reference.get("grade") or {}
        new = row.get("native_fields") or {}
        positions = len(labels)
        if any((score.get("match") or {}).get("positions") != positions for score in (old, new)):
            continue
        counter["paired"] += 1
        delta = new["match"]["matched"] - old["match"]["matched"]
        if delta <= 0:
            continue
        counter["match_gain"] += 1
        if not all(type(score.get(name)) is int for score in (old, new) for name in PROTECTION):
            continue
        if any(new[name] > old[name] for name in PROTECTION):
            continue
        counter["protected_gain"] += 1
        if reference.get("flags") or row.get("invalid_native_fields"):
            continue
        answer = row.get("answer")
        if not answer or sha256(answer.strip().encode()).hexdigest() == reference["answer_sha256"]:
            continue
        counter["unflagged_protected_gain"] += 1
        candidates.append({
            "uid": row["uid"], "group": record["source_group"], "method": row["method"],
            "stratum": stratum, "delta": delta, "old": old, "new": new,
        })
    return {
        "counts": {"/".join(key): dict(value) for key, value in sorted(counts.items())},
        "candidates": sorted(candidates, key=lambda r: (-r["delta"], r["uid"], r["method"])),
    }


if __name__ == "__main__":
    print(json.dumps(scan(), ensure_ascii=False, indent=2))
