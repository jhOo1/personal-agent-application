"""Assemble the V41 terminal study without opening the model gateway."""
from argparse import ArgumentParser
from collections import Counter
import json

from analyze import run_report
from audit_completed import audit, audited_rows
from label_bounds import audit_label_bounds
from qamc.common import sha
from trace_cost import describe
from run_v41 import ARMS, GATE, OUT, RP, probe, read

DELTA, REVIEW = ARMS
METHODS = (RP, GATE, REVIEW, DELTA)


def common_scores(rows):
    common = [row for row in rows if all("match" in row["native"][method]["fields"]
                                        for method in METHODS)]
    return {"roots": len(common), "groups": len({row["group"] for row in common}),
            "positions": sum(len(row["labels"]) for row in common),
            "matches": {method: sum(row["native"][method]["fields"]["match"]["matched"] for row in common)
                        for method in METHODS}}


def numerical_rules(result):
    pairs = result["pairs"]["all_completed"]
    primary = pairs[f"{REVIEW}__{DELTA}"]
    against_rp = pairs[f"{RP}__{DELTA}"]
    metric_deltas = {name: primary["separate_metric_pairs"][name].get("delta")
                     for name in ("OPB", "UPB", "FM", "VG", "full_match")}
    ci = primary.get("95pct_source_bootstrap")
    gain = primary.get("match_delta")
    rp_gain = against_rp.get("match_delta")
    tol = 1e-12
    strong = {
        "target_gain_at_least_10pp": gain is not None and gain >= .10 - tol,
        "source_interval_above_zero": ci is not None and ci[0] > 0,
        "at_least_archived_RP": rp_gain is not None and rp_gain >= -tol,
    }
    common_protection = {
        "OPB_not_increased": metric_deltas["OPB"] is not None and metric_deltas["OPB"] <= tol,
        "UPB_not_increased": metric_deltas["UPB"] is not None and metric_deltas["UPB"] <= tol,
        "full_match_decline_at_most_2pp": metric_deltas["full_match"] is not None
        and metric_deltas["full_match"] >= -.02 - tol,
    }
    # Preserve the written language as well as the rubric-defined error orientation.
    fm_vg_literal = all(metric_deltas[key] is not None and metric_deltas[key] >= -.20 - tol
                        for key in ("FM", "VG"))
    fm_vg_error_margin = all(metric_deltas[key] is not None and metric_deltas[key] <= .20 + tol
                             for key in ("FM", "VG"))
    if not result["complete"]:
        status = "PENDING_FULL_PANEL"
    elif not all((*strong.values(), *common_protection.values())):
        status = "NUMERIC_GATE_FAILED"
    elif not (fm_vg_literal and fm_vg_error_margin):
        status = ("QUALITY_DIRECTION_AMBIGUITY" if fm_vg_literal != fm_vg_error_margin
                  else "NUMERIC_GATE_FAILED")
    else:
        status = "PENDING_BEHAVIORAL_QUALITY_CHECK"
    return {"status": status, "primary_match": strong, "quality": common_protection,
            "quality_deltas": metric_deltas, "FM_VG_literal_text_pass": fm_vg_literal,
            "FM_VG_rubric_error_margin_pass": fm_vg_error_margin,
            "FM_VG_directions_disagree": fm_vg_literal != fm_vg_error_margin,
            "semantic_non_regression_confirmed": False}


def settle():
    plan = read(OUT / "FROZEN.json")
    primary = run_report()
    completed = primary["completed"]
    rows = [row for wave, _ in audited_rows(plan) for row in wave]
    checks, cost, bounds = audit(), describe(), audit_label_bounds()
    observed = [len(rows), checks["counts"]["completed_roots"], cost["completed_roots"], bounds["completed_roots"]]
    if any(value != completed for value in observed):
        raise ValueError("A wave finished during a multi-view read. Re-run against one stable boundary.")
    waves = []
    covered = 0
    for index, expected in enumerate(plan["waves"]):
        path = OUT / f"wave_{index:02d}" / "COMPLETED.json"
        covered += len(expected)
        if covered > completed:
            break
        record = read(path)
        if [row["uid"] for row in record["rows"]] != expected:
            raise ValueError("Frozen wave membership changed")
        waves.append({"wave": index, "roots": len(expected), "sha256": sha(path.read_bytes())})
    tables = {
        "all": rows,
        "all_A": [row for row in rows if set(row["labels"]) == {"A"}],
        "contains_BC": [row for row in rows if set(row["labels"]) != {"A"}],
        "less_exposed": [row for row in rows if row["in_sensitivity"]],
        "additional_groups": [row for row in rows if not row["in_sensitivity"]],
    }
    statuses = Counter((method, cell["status"]) for row in rows for method, cell in row["answers"].items())
    return {"primary_panel": primary, "verified_wire_and_judge_checks": checks,
            "native_label_bounds": bounds, "cost_and_traces": cost,
            "common_four_arms": {name: common_scores(pool) for name, pool in tables.items()},
            "numeric_rules": numerical_rules(primary),
            "answer_status": [{"method": method, "status": status, "count": count}
                              for (method, status), count in sorted(statuses.items())],
            "frozen_sha256": sha((OUT / "FROZEN.json").read_bytes()), "waves": waves,
            "native_scores_modified": 0, "new_model_requests": 0}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("preview", "write"))
    phase = parser.parse_args().phase
    if phase == "write":
        state = read(OUT / "RUN_STATE.json")
        if (state["state"], state["phase"]) != ("COMPLETE", "run"):
            raise ValueError("Primary run is not terminal")
    result = settle()
    if phase == "write":
        if not result["primary_panel"]["complete"]:
            raise ValueError("Terminal state has incomplete results")
        probe.freeze(OUT / "TERMINAL.json", result)
    print(json.dumps({"completed": result["primary_panel"]["completed"],
                      "common_four_arms": result["common_four_arms"],
                      "numeric_rules": result["numeric_rules"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
