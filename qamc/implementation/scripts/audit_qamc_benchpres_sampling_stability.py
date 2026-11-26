"""Compare completed three-draw BenchPreS tasks to the exact same old T0 tasks."""

import argparse
from collections import Counter, defaultdict
import json

import report_qamc_benchpres_three_draw as report
import run_qamc_benchpres_three_draw as run
from qamc.common import sha
from qamc.pa.core import digest


def signature(case):
    return case["uid"], case["evaluation_hash"], case["analysis_group_id"]


def measured(refs, samples):
    values = [report.metric_values(score, refs[uid]) for uid, score in samples]
    return {metric: dict(zip(("numerator", "denominator"), report.sum_metric(values, metric)))
            for metric in report.METRICS}


def category(decision):
    if not decision["appropriate"]:
        return "inappropriate"
    return "appropriate_bold" if report.BOLD.search(decision["preference"]) else "appropriate_nonbold"


def audit(waves):
    plan = run.read(run.RUN / "PLAN_PRIVATE.json")
    run.valid(plan)
    if sha(plan) != run.read(run.OUT / "PREFLIGHT.json")["plan_sha256"]:
        raise ValueError("Private plan differs from committed preflight")
    old_plan = run.read(run.prior.OUT / "PLAN.json")
    if {signature(c) for c in old_plan["cases"]} != {signature(c) for c in plan["cases"]}:
        raise ValueError("Old and new evaluation case identity differs")
    case_index = {c["uid"]: c for c in plan["cases"]}
    old_paths = {run.GATE: run.prior.base.OUT, run.PAPER: run.prior.OUT}
    old = {}
    for arm, path in old_paths.items():
        eligible = [r for r in run.read(path / "RESULT_ROWS.json") if r["uid"] in case_index and r["method"] == arm]
        if len(eligible) != len(case_index) or len({r["uid"] for r in eligible}) != len(case_index):
            raise ValueError("Incomplete one-draw archive")
        old.update({(r["uid"], arm): r["score"] for r in eligible})
    new = {}
    for wave in waves:
        area = run.RUN / f"wave-{wave}"
        rows = run.read(area / "RESULTS.json")
        index = {(r["uid"], r["method"], r["replicate"]): r["score"] for r in rows}
        expected = {(uid, arm, rep) for uid in plan["waves"][wave] for arm in run.METHODS for rep in run.REPEATS}
        if set(index) != expected or len(rows) != len(index) or index.keys() & new.keys():
            raise ValueError("Repeat allocation drift")
        new.update(index)
    represented = {uid for uid, _, _ in new}
    common = [uid for uid in sorted(represented) if all(old[uid, arm] is not None
              and all(new[uid, arm, rep] is not None for rep in run.REPEATS) for arm in run.METHODS)]
    refs = {u: run.read(run.ROOT / case_index[u]["evaluation_path"]) for u in common}
    if any(digest(refs[u]) != case_index[u]["evaluation_hash"] for u in common):
        raise ValueError("Frozen evaluation labels changed")
    stats = {}
    for arm in run.METHODS:
        t0 = measured(refs, [(u, old[u, arm]) for u in common])
        t1 = [measured(refs, [(u, new[u, arm, rep]) for u in common]) for rep in run.REPEATS]
        rates = {key: sum(v[key]["numerator"] for v in t1) / (3 * t0[key]["denominator"])
                 if t0[key]["denominator"] else None for key in report.METRICS}
        attributes = defaultdict(Counter)
        for uid in common:
            previous = old[uid, arm]["decisions"]
            repeats = [new[uid, arm, rep]["decisions"] for rep in run.REPEATS]
            for i, decision in enumerate(previous):
                present = [values[i] for values in repeats]
                votes = sum(v["label"] == "follow" for v in present)
                bucket = attributes[category(decision)]
                bucket[f"T0_{decision['label']}_T1_follow_{votes}_of_3"] += 1
                if 0 < votes < 3:
                    bucket["T1_mixed"] += 1
        stats[arm] = {"historic_T0": t0, "current_T1_draws": t1, "current_T1_mean": rates,
                      "attribute_vote_distribution": attributes}
    return {"scored_waves": waves, "represented_tasks": len(represented), "common_complete_tasks": len(common),
            "common_profiles": len({case_index[u]["analysis_group_id"] for u in common}),
            "historical_vs_current_service_parity": plan["prior_service_reference_equal"],
            "interpretation": "descriptive cross-service comparison, not an identified temperature effect",
            "methods": stats}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wave", type=int, nargs="+", required=True, choices=range(6))
    args = parser.parse_args()
    print(json.dumps(audit(sorted(set(args.wave))), indent=2, sort_keys=True))
