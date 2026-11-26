"""Summarize paired BenchPreS deltas across profiles and draw indices."""

import argparse
from collections import Counter, defaultdict
import json
from statistics import mean

import run_qamc_benchpres_three_draw as run
from qamc.common import sha
from report_qamc_benchpres_three_draw import METRICS, metric_values, replay


def pattern(rows):
    """Report sign counts without exporting profile identifiers."""
    groups = [row for row in rows if row["denominator"]]
    signs = Counter({
        "gate_higher": sum(g["delta"] > 0 for g in groups),
        "selectivity_higher": sum(g["delta"] < 0 for g in groups),
        "tie": sum(g["delta"] == 0 for g in groups),
    })
    if not groups:
        return {"profile_sign_counts": signs, "mean_profile_delta": None, "leave_one_profile_out_range": None}
    n = sum(g["delta"] for g in groups)
    d = sum(g["denominator"] for g in groups)
    loo = [(n - g["delta"]) / (d - g["denominator"]) for g in groups if d > g["denominator"]]
    return {"profile_sign_counts": signs,
            "mean_profile_delta": mean(g["delta"] / g["denominator"] for g in groups),
            "leave_one_profile_out_range": [min(loo), max(loo)] if loo else None}


def audit(plan, waves=None):
    settled = replay(plan, waves)
    cases = {case["uid"]: case for case in plan["cases"]}
    refs = {uid: run.read(run.ROOT / case["evaluation_path"]) for uid, case in cases.items()}
    all_scores = {}
    for wave in settled["settled_waves"]:
        for row in run.read(run.RUN / f"wave-{wave}/RESULTS.json"):
            if row["score"] is not None:
                key = row["uid"], row["method"], row["replicate"]
                all_scores[key] = metric_values(row["score"], refs[row["uid"]])
    counts = defaultdict(Counter)
    by_draw = defaultdict(Counter)
    paired_draws = 0
    for uid, case in cases.items():
        profile = case["analysis_group_id"]
        for draw in run.REPEATS:
            gate, selectivity = (all_scores.get((uid, m, draw)) for m in run.METHODS)
            if gate is None or selectivity is None:
                continue
            paired_draws += 1
            for metric in METRICS:
                left, denominator = gate[metric]
                right, right_denominator = selectivity[metric]
                if denominator != right_denominator:
                    raise ValueError("Pair uses incompatible denominators")
                for cell in (counts[metric, profile], by_draw[metric, draw]):
                    cell.update(delta=left - right, gate=left, selectivity=right, denominator=denominator)

    if paired_draws != settled["available_pairs"]["task_draw_pairs"]:
        raise ValueError("Profile audit and primary paired denominators differ")
    summary = {}
    for metric in METRICS:
        profiles = [value for (key, _), value in counts.items() if key == metric]
        original = settled["available_pairs"]["metrics"][metric]
        for key, expected in (("gate", original["gate_numerator"]),
                              ("selectivity", original["selectivity_numerator"]),
                              ("denominator", original["denominator"])):
            if sum(row[key] for row in profiles) != expected:
                raise ValueError("Profile audit and primary totals differ")
        summary[metric] = {**pattern(profiles), "draw_counts": [by_draw[metric, i] for i in run.REPEATS]}
    return {"frozen_plan_sha256": sha(plan), "settled_waves": settled["settled_waves"],
            "paired_task_draws": paired_draws, "metrics": summary, "new_requests": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wave", nargs="+", type=int, choices=range(6))
    args = parser.parse_args()
    print(json.dumps(audit(run.read(run.RUN / "PLAN_PRIVATE.json"), args.wave), indent=2, sort_keys=True))
