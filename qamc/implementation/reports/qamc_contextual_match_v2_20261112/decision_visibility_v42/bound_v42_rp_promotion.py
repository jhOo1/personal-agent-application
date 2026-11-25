"""Bound the frozen V42 point-difference gate using already recorded RP scores."""
from argparse import ArgumentParser
from fractions import Fraction
import json

import run_visibility_v42 as stage


def bound(expected):
    plan = stage.read(stage.OUT / "FROZEN.json")
    checkpoint = stage.read(stage.OUT / f"CHECKPOINT_{expected:03d}.json")
    if plan != stage.prepare() or checkpoint["completed_roots"] != expected:
        raise ValueError("Unexpected frozen cohort")
    wave_records = checkpoint["wave_proofs"]
    if sum(item["roots"] for item in wave_records) != expected:
        raise ValueError("Checkpoint wave counts do not match the evaluation prefix")
    for index, item in enumerate(wave_records):
        path = stage.OUT / f"wave_{index:02d}" / "COMPLETED.json"
        if (item["wave"] != index or item["roots"] != len(plan["waves"][index])
                or item["sha256"] != stage.sha(path.read_bytes())):
            raise ValueError("Checkpoint no longer corresponds to immutable recorded waves")
    baseline, treatment = stage.prior.RP, "SCOPED_MASKED"
    counts = checkpoint["scores"]["paired"]["all"][f"{baseline}__{treatment}"]["scores"]
    recorded_positions = counts[baseline]["positions"]
    if counts[treatment]["positions"] != recorded_positions:
        raise ValueError("Mismatched paired denominators")
    difference = counts[treatment]["matched"] - counts[baseline]["matched"]
    roots = {r["uid"]: r for r in stage.read(stage.prior.OUT / "FROZEN.json")["roots"]}
    remaining = [uid for batch in plan["waves"][len(wave_records):] for uid in batch]
    saved = [roots[uid]["archived"][baseline]["fields"].get("match") for uid in remaining]
    options = [(m["positions"] - m["matched"], m["positions"]) for m in saved if m is not None]
    margin = Fraction(3, 100)
    slack = difference - margin * recorded_positions + sum(
        max(0, gain - margin * positions) for gain, positions in options
    )
    numerator, denominator = difference, recorded_positions
    maximum = Fraction(numerator, denominator)
    for gain, positions in sorted(options, key=lambda t: Fraction(*t), reverse=True):
        numerator += gain
        denominator += positions
        maximum = max(maximum, Fraction(numerator, denominator))
    return {"settled_roots": expected, "paired_recorded_positions": recorded_positions,
            "observed_match_difference_count": difference, "remaining_roots": len(remaining),
            "remaining_valid_RP_grades": len(options), "remaining_potential_paired_positions": sum(
                positions for _, positions in options),
            "required_point_difference": float(margin), "best_possible_point_difference": float(maximum),
            "best_possible_ratio_fraction": str(maximum), "best_margin_slack_in_match_positions": float(slack),
            "required_point_difference_is_reachable_under_frozen_raw_scores": slack >= 0,
            "new_model_calls": 0,
            "assumption": ("Keep all settled scores and archived RP grades fixed. Allow every remaining "
                           "jointly graded candidate to receive full Match and every other candidate to be "
                           "missing. This is an upper bound, not a terminal result or a score correction.")}


if __name__ == "__main__":
    args = ArgumentParser(description=__doc__)
    args.add_argument("--expected", type=int, required=True)
    print(json.dumps(bound(args.parse_args().expected), ensure_ascii=False, indent=2))
