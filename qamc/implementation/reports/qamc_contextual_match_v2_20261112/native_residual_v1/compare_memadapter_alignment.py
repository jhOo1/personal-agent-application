"""Compare identical-cohort PersistBench grading with archived strong methods."""
from collections import Counter
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "persist_memadapter_alignment_v1"
SLICES = {
    "previously_enriched": "selected_gepa_expansion_v1",
    "expanded_protection": "persist_performance_v1",
}


def read(path):
    return json.loads(path.read_text())


def count_pairs(rows, reference):
    counts = {}
    for row in rows:
        uid, category = row["uid"], row["category"]
        if uid not in reference:
            continue
        other_category, other = reference[uid]
        if category != other_category:
            raise ValueError(f"Scoring category drift: {uid}")
        values = counts.setdefault(category, Counter())
        values["planned_common"] += 1
        if row["score"] is None or other is None:
            values["missing"] += 1
            continue
        flag = "failure_strict_utility" if category == "beneficial_memory_usage" else "failure_release"
        a, b = not row["score"][flag], not other[flag]
        values.update({"scored_common": 1, "memadapter_pass": a, "reference_pass": b,
                       "wins": a and not b, "losses": b and not a})
    return counts


def compare():
    data = read(RUN / "RESULTS.json")
    rows = data["rows"]
    if len(rows) != len({row["uid"] for row in rows}):
        raise ValueError("Duplicate MemAdapter case")
    report = {"PB_RUBRIC": count_pairs(rows, {
        row["uid"]: (row["category"], row["base_score"]) for row in rows
    })}
    for name, folder in SLICES.items():
        opponents = read(HERE / folder / "RESULTS.json")["rows"]
        for method in sorted({r["method"] for r in opponents}):
            reference = {row["uid"]: (row["category"], row["score"])
                         for row in opponents if row["method"] == method}
            report[f"{name}/{method}"] = count_pairs(rows, reference)
    ledger = data["ledger"]
    return {
        "paired": report, "actor_status": Counter(row["actor_status"] for row in rows),
        "score_status": Counter(r["status"] for r in ledger),
        "reported_tokens": sum((r["usage"] or {}).get("total_tokens", 0) for r in ledger),
        "unknown_usage": sum((r["usage"] or {}).get("total_tokens") is None for r in ledger),
    }


if __name__ == "__main__":
    print(json.dumps(compare(), indent=2, sort_keys=True))
