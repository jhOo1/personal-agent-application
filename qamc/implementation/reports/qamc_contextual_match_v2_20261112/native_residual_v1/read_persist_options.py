"""Summarize the option experiment without exposing source or answer text."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path


def summarize(result):
    paired = defaultdict(dict)
    for row in result["rows"]:
        arms = paired[row["uid"]]
        if row["method"] in arms:
            raise ValueError("Duplicate method receipt")
        arms[row["method"]] = row
    scores = defaultdict(Counter)
    statuses = Counter()
    for arms in paired.values():
        direct, locked = (arms[name] for name in ("direct", "locked"))
        if (direct["stratum"], direct["base_score"]) != (locked["stratum"], locked["base_score"]):
            raise ValueError("Baseline differs within pair")
        for row in (direct, locked):
            statuses[f'{row["method"]}/{row["actor_status"]}'] += 1
            if row["fallback"]:
                statuses[f'{row["method"]}/fallback'] += 1
        grades = [direct["base_score"], direct["score"], locked["score"]]
        if any(not grade or type(grade.get("failure_release")) is not bool for grade in grades):
            scores[direct["stratum"]]["missing"] += 1
            continue
        base, ordinary, constrained = (not grade["failure_release"] for grade in grades)
        count = scores[direct["stratum"]]
        count.update({
            "common": 1, "base_pass": base, "direct_pass": ordinary, "locked_pass": constrained,
            "locked_win": constrained and not ordinary, "locked_loss": ordinary and not constrained,
        })
    ledger = result["ledger"]
    usage = [(row.get("usage") or {}).get("total_tokens") for row in ledger]
    return {
        "roots": len(paired), "option_plans": len(result["options"]),
        "scores": scores, "actor_status": statuses, "ledger_entries": len(ledger),
        "reported_tokens": sum(n for n in usage if isinstance(n, int)),
        "missing_usage_entries": sum(n is None for n in usage),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    args = parser.parse_args()
    print(json.dumps(summarize(json.loads(args.results.read_text())), indent=2, sort_keys=True))
