"""Summarize assignment, paired scores, and actual scope annotation exposure."""
from collections import Counter, defaultdict
import json

from build_jobs import prepare
from run_scope_pilot import ARMS, OUT
from summarize_reassembly import aligned, measure
from trial_reassembly import probe


def main():
    result = probe.read(OUT / "RESULTS.json")
    _, base = prepare((), "search")
    rows = defaultdict(dict)
    for row in result["rows"]:
        key = row["uid"]
        if row["method"] in rows[key]:
            raise ValueError("Duplicate scoped result")
        rows[key][row["method"]] = measure("RPEval", row["stratum"], row["score"])
    if len(rows) != 6 or any(set(cells) != set(ARMS) for cells in rows.values()):
        raise ValueError("Coverage differs from frozen assignment")
    counts = Counter()
    totals = defaultdict(Counter)
    for uid, cells in rows.items():
        card = base["RPEval", uid]
        binding = bool(result["plans"].get(uid, {}).get("preferences"))
        cells["baseline"] = measure("RPEval", card["stratum"], card["base_score"])
        for subset in ("all", card["stratum"], "binding" if binding else "no_binding"):
            counts[subset, "assigned"] += 1
            if not aligned(cells, (*ARMS, "baseline")):
                continue
            counts[subset, "paired"] += 1
            for method, metrics in cells.items():
                totals[subset, method].update(metrics)
    print(json.dumps({
        "coverage": {" / ".join(key): n for key, n in sorted(counts.items())},
        "metrics": {" / ".join(key): v for key, v in sorted(totals.items())},
        "plan_rejections": Counter(result["rejected_plans"].values()),
        "requests": Counter(r["status"] for r in result["ledger"]),
        "tokens": sum((r["usage"] or {}).get("total_tokens") or 0 for r in result["ledger"]),
        "usage_unknown": sum("total_tokens" not in (r["usage"] or {}) for r in result["ledger"]),
    }, indent=2))


if __name__ == "__main__":
    main()
