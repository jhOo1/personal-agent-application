"""Read BenchPreS realization results by common denominators and profile."""
from collections import defaultdict
import argparse
import json

from read_option_pair import summarize
from run_bench_realization import OUT
from summarize_reassembly import aligned, measure
from trial_reassembly import probe


def readout(result):
    arms = ("direct", "content_first")
    profiles = defaultdict(list)
    for row in result["rows"]:
        profiles[row["group"]].append(row)
    pairs = defaultdict(dict)
    for row in result["rows"]:
        pairs[row["uid"]][row["method"]] = row
    deltas = {}
    for uid, pair in pairs.items():
        direct, planned = (pair[arm] for arm in arms)
        rows = {
            "base": direct["base_score"],
            "direct": direct["score"],
            "content_first": planned["score"],
        }
        scores = {name: measure("BenchPreS", direct["stratum"], score)
                  for name, score in rows.items()}
        if aligned(scores, ("base", *arms)):
            final = scores["content_first"]
            deltas[uid] = {
                reference: {field: final[field] - scores[reference][field]
                            for field in ("primary", "completeness", "MR", "nonbold")}
                for reference in ("base", "direct")
            }
    return {
        "paired_deltas": deltas,
        "overall": summarize(result, arms),
        "profiles": {
            group: summarize({"rows": rows, "ledger": []}, arms)
            for group, rows in sorted(profiles.items())
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--group-out", action="store_true")
    parser.add_argument("--published-controls", action="store_true")
    args = parser.parse_args()
    output = OUT
    if args.group_out:
        from run_bench_realization_group_out import OUT as output
    result = probe.read(output / "RESULTS.json")
    report = readout(result)
    if args.published_controls:
        from build_jobs import archive

        _, _, controls = archive.transfer.context("BenchPreS")
        for method in ("PAPER_SELECTIVITY", "RPR_PAPER_FULL"):
            scores = {row["uid"]: row["score"] for row in controls if row["method"] == method}
            comparable = {**result, "rows": [
                {**row, "base_score": scores.get(row["uid"])} for row in result["rows"]
            ]}
            report[method] = readout(comparable)
    print(json.dumps(report, indent=2))
