"""Count eligible exposed groups for development-only source supervision."""
from collections import Counter, defaultdict
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    census = json.loads((HERE.parent / "strong_actor_boundary_audit_v1" / "CENSUS.json").read_text())
    tested = json.loads((HERE / "incremental_pair_v1" / "RESULTS.json").read_text())
    used = {row["uid"] for row in tested["rows"]}
    excluded = {row["group"] for row in census["RPEval"]["roots"] if row["uid"] in used}
    counts, groups = Counter(), defaultdict(set)
    for root in census["RPEval"]["roots"]:
        subset = "prior_reentry_group" if root["group"] in excluded else "other_exposed_group"
        for position in root["positions"]:
            if position["author_label"] != "B":
                continue
            state = position["state"]
            counts[subset, state] += 1
            groups[subset, state].add(root["group"])
    print(json.dumps({"/".join(key): {"positions": count, "groups": len(groups[key])}
                      for key, count in sorted(counts.items())}, indent=2))


if __name__ == "__main__":
    main()
