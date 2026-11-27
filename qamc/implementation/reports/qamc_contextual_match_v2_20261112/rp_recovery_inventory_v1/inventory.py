"""Offline census of same-task RP alternatives to frozen IPE-C, before any new inference."""
from collections import Counter
from pathlib import Path
import argparse
import json

GUARDS = ("OPB", "UPB", "FM")


def valid(score, n):
    grade = (score or {}).get("grade") or {}
    m = grade.get("match") or {}
    return (m.get("positions") == n and type(m.get("matched")) is int and 0 <= m["matched"] <= n
            and all(type(grade.get(k)) is int for k in GUARDS))


def summarize(rows):
    counts = Counter(assigned=len(rows))
    roots = set()
    useful = set()
    for r in rows:
        base, rp = (r["scores"].get(k) for k in ("IPE_C", "RPR_PAPER_FULL"))
        n = len(r["labels"] or "")
        if not all(valid(s, n) for s in (base, rp)):
            counts["missing"] += 1
            continue
        roots.add(r["source_group"])
        b, p = base["grade"], rp["grade"]
        v, w = b["match"]["matched"], p["match"]["matched"]
        same = base["answer_sha256"] == rp["answer_sha256"]
        if same and (w != v or any(b[k] != p[k] for k in GUARDS)):
            raise ValueError("Same answer has nonidentical scores")
        counts.update(common=1, positions=n, base=v, rp=w, identical_answer=int(same))
        counts["rp_win" if w > v else "rp_loss" if w < v else "tie"] += 1
        counts["oracle_extra"] += max(0, w-v)
        if w > v and all(p[k] <= b[k] for k in GUARDS):
            counts.update(protected_win=1, protected_extra=w-v)
            useful.add(r["source_group"])
            if not (base.get("flags") or rp.get("flags")):
                counts.update(unflagged_protected_win=1, unflagged_protected_extra=w-v)
    return {**counts, "common_roots": len(roots), "protected_win_roots": len(useful)}


def main(path):
    rows = json.loads(path.read_text())["rows"]
    assert len(rows) == len({r["uid"] for r in rows}) == 300
    subsets = {"all": rows, "all_A": [r for r in rows if set(r["labels"] or "") == {"A"}],
               "B_without_C": [r for r in rows if "B" in (r["labels"] or "") and "C" not in (r["labels"] or "")],
               "contains_C": [r for r in rows if "C" in (r["labels"] or "")]}
    subsets["unknown_labels"] = [r for r in rows if not r["labels"]]
    assert sum(map(len, list(subsets.values())[1:])) == len(rows)
    return {k: summarize(v) for k, v in subsets.items()}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("previous_results", type=Path)
    print(json.dumps(main(p.parse_args().previous_results), indent=2))
