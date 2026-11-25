"""Report same-case PersistBench results without dispatching requests."""
import json

from read_option_pair import summarize
from run_persist_criteria import OUT
from trial_reassembly import probe


def readout(result):
    arms = ("direct", "criteria_first")
    report = summarize(result, arms)
    report["paired_release_flips"] = {}
    by_uid = {}
    for row in result["rows"]:
        by_uid.setdefault(row["uid"], {})[row["method"]] = row
    for uid, pair in by_uid.items():
        direct, criteria = (pair[method] for method in arms)
        before = direct["base_score"]
        if not all(isinstance(score, dict) and type(score.get("failure_release")) is bool
                   for score in (before, direct["score"], criteria["score"])):
            continue
        outcomes = [score["failure_release"] for score in (before, direct["score"], criteria["score"])]
        if len(set(outcomes)) > 1:
            report["paired_release_flips"][uid] = dict(zip(("base", *arms), outcomes))
    return report


if __name__ == "__main__":
    print(json.dumps(readout(probe.read(OUT / "RESULTS.json")), indent=2))
