"""Read matched search and validation metrics from the private run directory."""
import argparse
from collections import Counter, defaultdict
import json

from build_jobs import prepare
from run_nro_comparison import HERE
from summarize_reassembly import aligned, measure
from trial_reassembly import probe


def summarize(result, baseline):
    if len(result["rows"]) != len(baseline):
        raise ValueError("Unexpected result coverage")
    output = defaultdict(lambda: {"assigned": 0, "paired": 0,
                                  "base": Counter(), "candidate": Counter()})
    keys = set()
    for row in result["rows"]:
        benchmark, uid, stratum = (row[k] for k in ("benchmark", "uid", "stratum"))
        key = benchmark, uid
        if key in keys:
            raise ValueError("Duplicate task")
        keys.add(key)
        original = baseline[key]
        cells = {"base": measure(benchmark, stratum, original["base_score"]),
                 "candidate": measure(benchmark, stratum, row["score"])}
        if cells["base"] is None:
            raise ValueError("Frozen baseline is missing a valid score")
        paired = aligned(cells, ("base", "candidate"))
        for name in (benchmark, f"{benchmark}/{stratum}"):
            bucket = output[name]
            bucket["assigned"] += 1
            if paired:
                bucket["paired"] += 1
                for arm, score in cells.items():
                    bucket[arm].update(score)
    ledger = result["ledger"]
    return {"rules": result["rules"], "metrics": output,
            "receipts_by_status": Counter(item["status"] for item in ledger),
            "reported_tokens": sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger),
            "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--feedback", action="store_true",
                        help="read the saved, search-only feedback pair")
    feedback = parser.parse_args().feedback
    root = (HERE / "feedback_proposals_v1" if feedback else HERE) / "comparison_v1"
    output = {}
    baselines = {}
    for path in sorted(root.glob("*/RESULTS.json")):
        split = "confirmation" if "_confirmation_" in path.parent.name else "search"
        if split not in baselines:
            _, baselines[split] = prepare((), split)
        output[path.parent.name] = summarize(probe.read(path), baselines[split])
    verdict = (root.parent / "SEARCH_ELIGIBILITY.json") if feedback else (root / "WINNERS.json")
    name = "search_eligibility" if feedback else "winners"
    print(json.dumps({"completed": output,
                      name: probe.read(verdict) if verdict.is_file() else None},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
