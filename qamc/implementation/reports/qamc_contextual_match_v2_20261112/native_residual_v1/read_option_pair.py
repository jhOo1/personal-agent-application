"""Aggregate option revision results on common benchmark denominators."""
from collections import Counter, defaultdict
import json

from run_option_pair import OUT
from summarize_reassembly import aligned, measure
from trial_reassembly import probe


def summarize(data, arms=("ordinary", "option")):
    groups = defaultdict(dict)
    statuses = Counter()
    for row in data["rows"]:
        benchmark, uid, method = row["benchmark"], row["uid"], row["method"]
        if method in groups[benchmark, uid]:
            raise ValueError("Duplicate arm")
        groups[benchmark, uid][method] = row
        statuses[benchmark, method, row["actor_status"], row["origin"]] += 1

    methods = (*arms, "base")
    totals = defaultdict(Counter)
    counts = Counter()
    for (benchmark, _), pair in groups.items():
        if set(pair) != set(methods[:2]):
            raise ValueError("Missing arm")
        first, second = (pair[method] for method in methods[:2])
        if first["base_score"] != second["base_score"] or first["stratum"] != second["stratum"]:
            raise ValueError("Baseline mismatch")
        stratum = first["stratum"]
        scores = {method: measure(benchmark, stratum, row["score"]) for method, row in pair.items()}
        scores["base"] = measure(benchmark, stratum, first["base_score"])
        for subset in (("all", stratum) if stratum != "all" else ("all",)):
            counts[benchmark, subset, "assigned"] += 1
            if aligned(scores, methods):
                counts[benchmark, subset, "common"] += 1
                for method, score in scores.items():
                    totals[benchmark, subset, method].update(score)
    flatten = lambda rows: {" / ".join(key): value for key, value in sorted(rows.items())}
    ledger = data["ledger"]
    return {"counts": flatten(counts), "totals": flatten(totals), "statuses": flatten(statuses),
            "requests": Counter(row["status"] for row in ledger),
            "reported_tokens": sum((row["usage"] or {}).get("total_tokens") or 0 for row in ledger),
            "unknown_usage": sum("total_tokens" not in (row["usage"] or {}) for row in ledger)}


if __name__ == "__main__":
    print(json.dumps(summarize(probe.read(OUT / "RESULTS.json")), indent=2))
