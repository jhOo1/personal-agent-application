"""Read the frozen RPEval scope comparison without dispatching requests."""
from collections import Counter, defaultdict
import json

from run_gate_scope import ARMS, HERE, OUT
from summarize_reassembly import aligned, measure
from trial_reassembly import probe


def summarize(result, panel):
    assigned = {row["uid"]: row for row in panel["rows"]}
    methods = (*ARMS, "gate")
    cells = defaultdict(dict)
    for row in result["rows"]:
        uid, method = row["uid"], row["method"]
        if uid not in assigned or method not in ARMS or method in cells[uid]:
            raise ValueError("Unexpected result assignment")
        cells[uid][method] = row
    if set(cells) != set(assigned) or set(result["gate_scores"]) != set(assigned):
        raise ValueError("Incomplete result assignment")

    coverage, statuses, comparisons = Counter(), Counter(), Counter()
    totals = defaultdict(Counter)
    for uid, rows in cells.items():
        if set(rows) != set(ARMS):
            raise ValueError("Incomplete arm assignment")
        stratum = assigned[uid]["stratum"]
        exposed = bool(result["plans"].get(uid, {}).get("preferences"))
        scores = {method: row["score"] for method, row in rows.items()}
        scores["gate"] = result["gate_scores"][uid]
        metrics = {method: measure("RPEval", stratum, scores[method]) for method in methods}
        for method, row in rows.items():
            statuses[method, row["actor_status"], "scored" if row["score"] else "unscored"] += 1
        for subset in ("all", stratum, "binding" if exposed else "no_binding"):
            coverage[subset, "assigned"] += 1
            for reference in ("unbound", "gate"):
                pair = ("scoped", reference)
                if not aligned(metrics, pair):
                    continue
                coverage[subset, f"paired_{reference}"] += 1
                for method in pair:
                    totals[subset, reference, method].update(metrics[method])
                delta = metrics["scoped"]["primary"] - metrics[reference]["primary"]
                comparisons[subset, reference, "win" if delta > 0 else "loss" if delta < 0 else "tie"] += 1
            if aligned(metrics, methods):
                coverage[subset, "common_three"] += 1
                for method in methods:
                    totals[subset, "common_three", method].update(metrics[method])
    return {
        "coverage": {" / ".join(key): n for key, n in sorted(coverage.items())},
        "metrics": {" / ".join(key): n for key, n in sorted(totals.items())},
        "scoped_match_outcomes": {" / ".join(key): n for key, n in sorted(comparisons.items())},
        "actor_status": {" / ".join(key): n for key, n in sorted(statuses.items())},
        "plan_rejections": Counter(result["rejected_plans"].values()),
        "requests": Counter(row["status"] for row in result["ledger"]),
        "tokens": sum((row["usage"] or {}).get("total_tokens") or 0 for row in result["ledger"]),
        "usage_unknown": sum("total_tokens" not in (row["usage"] or {}) for row in result["ledger"]),
    }


if __name__ == "__main__":
    print(json.dumps(summarize(probe.read(OUT / "RESULTS.json"),
                               probe.read(HERE / "GATE_PANEL.json")), indent=2))
