"""Recount unique scored answers in an exposed PersistBench BU archive."""
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
def main():
    roots = json.loads((BASE / "persist_cross_generation_frontier_v1/RESULTS.json").read_text())["roots"]
    totals = Counter()
    for uid, root in roots.items():
        if root["category"] != "beneficial_memory_usage":
            continue
        by_digest = defaultdict(set)
        for row in [root["reference"], *root.get("candidates", {}).values(), *root.get("new_candidates", {}).values()]:
            if not row or not row.get("score") or not row.get("answer"):
                continue
            digest = sha256(row["answer"].strip().encode()).hexdigest()
            if digest != row["answer_sha256"]:
                raise ValueError("Answer digest mismatch")
            by_digest[digest].add(row["score"]["rating"])
        hist = Counter(next(iter(v)) for v in by_digest.values() if len(v)==1)
        totals.update(hist)
        print(uid, dict(sorted(hist.items())), "conflicting texts",sum(len(v)>1 for v in by_digest.values()))
    print("Root-answer totals:",dict(sorted(totals.items())))
if __name__ == "__main__":
    main()
