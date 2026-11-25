"""Compute label-flip sensitivity on the saved, common BenchPreS comparator panel."""

from fractions import Fraction
import json
from pathlib import Path


REPORTS = Path(__file__).resolve().parents[1] / "reports"


def compare(candidate, baseline):
    ca, a = candidate["AAR_count"]
    ba, baseline_a = baseline["AAR_count"]
    cm, m = candidate["MR_count"]
    bm, baseline_m = baseline["MR_count"]
    assert (a, m) == (baseline_a, baseline_m)
    delta = Fraction(ca - ba, a) + Fraction(bm - cm, m)
    # Each adverse flip either removes a candidate advantage or creates a baseline advantage.
    available = [Fraction(1, a)] * (ca + a - ba) + [Fraction(1, m)] * (m - cm + bm)
    remainder = delta
    for flips, effect in enumerate(sorted(available, reverse=True), start=1):
        remainder -= effect
        if remainder <= 0:
            break
    else:
        raise ValueError("No adverse-flip bound on the paired panel")
    return {
        "candidate_gap_pp": float(100 * (Fraction(ca, a) - Fraction(cm, m))),
        "baseline_gap_pp": float(100 * (Fraction(ba, a) - Fraction(bm, m))),
        "paired_gap_delta_pp": float(100 * delta),
        "min_adverse_label_flips_to_tie_or_reverse_gap": flips if delta > 0 else 0,
        "min_adverse_label_flips_to_tie_or_reverse_aar": max(ca - ba, 0),
        "min_adverse_label_flips_to_tie_or_reverse_mr": max(bm - cm, 0),
    }


def main():
    archived = REPORTS / "qamc_benchpres_mitigation" / "ALL_METHODS_COMMON_VALID.json"
    panel = json.loads(archived.read_text())
    methods = panel["methods"]
    assert len(set(panel["uids"])) == panel["common_valid"] == 15
    assert all(row["valid"] == panel["common_valid"] for row in methods.values())
    result = {
        "common_roots": panel["common_valid"],
        "comparison": {key: compare(methods[key], methods["BM1"]) for key in ("CF1", "P0")},
        "new_model_calls": 0,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
