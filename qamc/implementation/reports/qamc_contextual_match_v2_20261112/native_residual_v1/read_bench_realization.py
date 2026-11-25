"""Read BenchPreS realization results by common denominators and profile."""
from collections import defaultdict
import json

from read_option_pair import summarize
from run_bench_realization import OUT
from trial_reassembly import probe


def readout(result):
    arms = ("direct", "content_first")
    profiles = defaultdict(list)
    for row in result["rows"]:
        profiles[row["group"]].append(row)
    return {
        "overall": summarize(result, arms),
        "profiles": {
            group: summarize({"rows": rows, "ledger": []}, arms)
            for group, rows in sorted(profiles.items())
        },
    }


if __name__ == "__main__":
    print(json.dumps(readout(probe.read(OUT / "RESULTS.json")), indent=2))
