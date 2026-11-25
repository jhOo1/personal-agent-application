"""Read search-only pilot results against fixed archived scores."""
from collections import Counter, defaultdict
import json

from build_jobs import prepare
from run_nro_pilot import OUT
from summarize_reassembly import aligned, measure
from trial_reassembly import probe


def main():
    _, baseline = prepare((), "search")
    results = probe.read(OUT / "RESULTS.json")
    totals = defaultdict(Counter)
    denominators = Counter()
    statuses = Counter()
    for row in results["rows"]:
        benchmark, stratum = row["benchmark"], row["stratum"]
        original = baseline[benchmark, row["uid"]]
        cells = {
            "base": measure(benchmark, stratum, original["base_score"]),
            "pilot": measure(benchmark, stratum, row["score"]),
        }
        statuses[(benchmark, row["actor_status"], cells["pilot"] is not None)] += 1
        if cells["base"] and cells["pilot"] and not aligned(cells, ("base", "pilot")):
            raise ValueError("Metric denominators changed")
        for tag in {stratum, "all"}:
            denominators[benchmark, tag, "assigned"] += 1
            if cells["pilot"] is None:
                continue
            denominators[benchmark, tag, "paired"] += 1
            for arm, values in cells.items():
                totals[benchmark, tag, arm].update(values)
    ledger = results["ledger"]
    print(json.dumps({
        "counts": {" / ".join(k): n for k, n in sorted(denominators.items())},
        "metrics": {" / ".join(k): v for k, v in sorted(totals.items())},
        "actor_status": {" / ".join(map(str, k)): v for k, v in sorted(statuses.items())},
        "request_status": Counter(r["status"] for r in ledger),
        "reported_tokens": sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger),
        "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
    }, indent=2))


if __name__ == "__main__":
    main()
