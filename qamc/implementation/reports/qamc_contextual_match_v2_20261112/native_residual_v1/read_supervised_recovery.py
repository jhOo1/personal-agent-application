"""Join selected source labels after dispatch and summarize paired outcomes."""
from collections import Counter
import json

from freeze_recovery_challenge import HERE
from read_option_pair import summarize
from run_supervised_recovery import OUT, prepare, read


def report(result, roots, panel, cards):
    labels = {root["uid"]: {p["id"]: p["author_label"] for p in root["positions"]}
              for root in roots.values()}
    roles = {row["uid"]: row["role"] for row in panel}
    if {(row["uid"], row["method"]) for row in result["rows"]} != {
        (uid, arm) for uid in roles for arm in ("ordinary", "incremental")
    }:
        raise ValueError("Incomplete challenge assignment")
    selected, rows = Counter(), []
    for row in result["rows"]:
        uid, method = row["uid"], row["method"]
        source = row["selected"]
        state = labels[uid][source] if source else row["origin"]
        selected[roles[uid], method, state] += 1
        rows.append({**row, "benchmark": "RPEval", "stratum": roles[uid],
                     "base_score": cards[uid]["base"]["grade"]})
    stats = summarize({**result, "rows": rows}, ("ordinary", "incremental"))
    stats["selected"] = {"/".join(key): count for key, count in sorted(selected.items())}
    return stats


def main():
    census = read(HERE.parent / "strong_actor_boundary_audit_v1" / "CENSUS.json")
    roots = {row["uid"]: row for row in census["RPEval"]["roots"]}
    print(json.dumps(report(read(OUT / "RESULTS.json"), roots,
                            read(HERE / "RECOVERY_CHALLENGE.json"), prepare(include_archive=True)), indent=2))


if __name__ == "__main__":
    main()
