"""Report AMP common denominators and missing-data bounds without raw traces."""
from collections import Counter, defaultdict
from itertools import combinations
import json

from run_amp import ARMS, RUN, probe
from summarize_pilot import aggregate, archived_comparators, archived_rpe_flags, metrics

METHODS = ("BASE", *ARMS)
PRIMARY = {"RPEval": "match", "BenchPreS": "aar", "PersistBench": "pass"}


def performance(benchmark, score, stratum):
    values = metrics(benchmark, score, stratum)
    if values is not None and benchmark == "PersistBench":
        values["release_pass"] = (int(not score["failure_release"]), 1)
    return values


def summarize(results):
    panels = defaultdict(dict)
    statuses = defaultdict(Counter)
    view_sizes = defaultdict(Counter)
    flag_uids = set()
    base_flags = archived_rpe_flags()
    for record in results["rows"]:
        b, uid, arm = (record[k] for k in ("benchmark", "uid", "method"))
        s = record["stratum"]
        item = panels[b].setdefault(uid, {"group": record["group"], "stratum": s,
                                        "scores": {"BASE": performance(b, record["base_score"], s)}})
        if arm in item["scores"]:
            raise ValueError("Duplicate projected outcome")
        item["scores"][arm] = performance(b, record["score"], s)
        if item["scores"]["BASE"] is None:
            raise ValueError("Missing frozen primary comparator")
        if b == "RPEval" and (record.get("score_flags") or base_flags.get(uid)):
            flag_uids.add(uid)
        statuses[b][arm + "/" + record["actor_status"]] += 1
        statuses[b][arm + "/valid_score"] += item["scores"][arm] is not None

    reports = {}
    references = archived_comparators(panels)
    for b, bank in panels.items():
        key = PRIMARY[b]
        external, scores = references[b]
        for uid, item in bank.items():
            item["scores"][external] = scores.get(uid)
        slices = {"all": list(bank.values())}
        for s in sorted({r["stratum"] for r in bank.values()}):
            slices[s] = [r for r in bank.values() if r["stratum"] == s]
        if b == "RPEval":
            slices["unflagged"] = [r for uid, r in bank.items() if uid not in flag_uids]
        for uid, item in bank.items():
            view = results["view_counts"].get(uid)
            if view is not None:
                view_sizes[b]["validated_joint_projection"] += 1
                view_sizes[b].update(view)
        reports[b] = {
            "strata": {s: {"common": aggregate(rows, METHODS, key),
                          "paired": {f"{left}/{right}": aggregate(rows, (left, right), key)
                                     for left, right in combinations(METHODS, 2)}}
                       for s, rows in slices.items()},
            "secondary_archive_comparison": {m: aggregate(slices["all"], (external, m), key) for m in ARMS},
            "exposure": dict(view_sizes[b]),
            "availability": dict(statuses[b]),
        }
    return {"benchmark": reports, **{k: results[k] for k in ("calls", "statuses", "tokens", "unknown_usage")}}


if __name__ == "__main__":
    result = probe.read(RUN / "RESULTS.json")
    print(json.dumps(summarize(result), indent=2, sort_keys=True))
