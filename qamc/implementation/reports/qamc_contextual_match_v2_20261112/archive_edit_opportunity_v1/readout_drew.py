"""Report the frozen DREW comparison from saved scores without model calls."""
import json
from collections import Counter
from pathlib import Path

from summarize_reassembly import aligned, measure

HERE = Path(__file__).resolve().parent
ARMS = ("BASE", "ORDINARY", "DREW")


def main():
    plan = json.loads((HERE / "FROZEN.json").read_text())
    result = json.loads((HERE / "RESULTS.json").read_text())
    outputs = {(row["uid"], row["method"]): row for row in result["rows"]}
    report = {}
    pairs = {}
    for benchmark in sorted({row["benchmark"] for row in plan["rows"]}):
        rows = [row for row in plan["rows"] if row["benchmark"] == benchmark]
        totals = Counter()
        wins = Counter()
        for row in rows:
            uid, stratum = row["uid"], row["stratum"]
            cells = {"BASE": measure(benchmark, stratum, row["base_score"])}
            for arm in ARMS[1:]:
                cells[arm] = measure(benchmark, stratum, outputs[uid, arm]["score"])
            pairs[uid] = cells
            for comparison in (ARMS, ("DREW", "ORDINARY"), ("DREW", "BASE")):
                group = "/".join(comparison)
                if not aligned(cells, comparison):
                    continue
                totals[group, "all", "tasks"] += 1
                totals[group, stratum, "tasks"] += 1
                for arm in comparison:
                    for key, value in cells[arm].items():
                        totals[group, "all", f"{arm}.{key}"] += value
                        totals[group, stratum, f"{arm}.{key}"] += value
                for arm in comparison:
                    delta = cells["DREW"]["primary"] - cells[arm]["primary"]
                    wins[group, arm, ("win" if delta > 0 else "loss" if delta < 0 else "tie")] += 1
        report[benchmark] = {
            "planned": len(rows),
            "metrics": {" / ".join(k): v for k, v in sorted(totals.items())},
            "drew_primary_pairs": {" / ".join(k): v for k, v in sorted(wins.items())},
        }
    print(json.dumps({
        "metrics": report,
        "cases": pairs,
        "issues": result["issues"],
        "calls": result["calls"],
        "statuses": result["statuses"],
        "reported_tokens": result["tokens"],
        "usage_unknown": sum("total_tokens" not in (item["usage"] or {}) for item in result["ledger"]),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
