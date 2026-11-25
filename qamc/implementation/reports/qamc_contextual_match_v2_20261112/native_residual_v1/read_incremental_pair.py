"""Summarize incremental preference selection without sending requests."""
from collections import Counter
import json

from incremental_panel import LOCAL, prepare, read
from read_option_pair import summarize
from run_incremental_pair import OUT


def main():
    _, cards = prepare()
    result = read(OUT / "RESULTS.json")
    labels_by_uid = {row["uid"]: row["labels"]
                     for pair in read(LOCAL / "ELIGIBILITY.json")["pairs"]
                     for row in pair["endpoints"]}
    selection = Counter()
    rows = []
    for row in result["rows"]:
        card = cards[row["uid"]]
        labels = labels_by_uid[row["uid"]]
        if not labels or set(labels) - set("ABC"):
            raise ValueError("Unknown author labels")
        scope = "contains_C" if "C" in labels else "B_only" if "B" in labels else "all_A"
        selection[scope, row["method"], "selected" if row["selected"] else row["origin"]] += 1
        rows.append({**row, "benchmark": "RPEval", "stratum": scope,
                     "base_score": card["base"]["grade"]})
    stats = summarize({**result, "rows": rows}, ("ordinary", "incremental"))
    stats["selection"] = {" / ".join(k): v for k, v in sorted(selection.items())}
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
