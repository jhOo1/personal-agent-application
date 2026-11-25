"""Summarize paired PersistBench outcomes without exposing answers or history."""
import argparse
from collections import Counter
import json
from pathlib import Path


def summarize(rows):
    metrics = {}
    for category in sorted({row["category"] for row in rows}):
        counts = Counter(dict.fromkeys(("planned", "paired", "baseline_pass",
                                       "candidate_pass", "wins", "losses"), 0))
        missing = Counter()
        flag = "failure_strict_utility" if category == "beneficial_memory_usage" else "failure_release"
        for row in rows:
            if row["category"] != category:
                continue
            counts["planned"] += 1
            if row["score"] is None:
                status = row["actor_status"]
                if status == "OK":
                    status = "/".join(sorted(row.get("judge_statuses", {}).values())) or "NO_GRADE"
                    if status == "OK":
                        status = "INVALID_GRADE"
                missing[status] += 1
                continue
            before = not row["base_score"][flag]
            after = not row["score"][flag]
            counts.update({"paired": 1, "baseline_pass": before, "candidate_pass": after,
                           "wins": after and not before, "losses": before and not after})
        metrics[category] = {**counts, "missing": dict(missing)}
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    args = parser.parse_args()
    print(json.dumps(summarize(json.loads(args.results.read_text())["rows"]), indent=2))
