"""Apply the preregistered V42 numeric screen to complete paired RPEval results."""
import json

import run_visibility_v42 as runner


CONTROL = "DIRECT_MASKED__SCOPED_MASKED"
VISIBILITY = "SCOPED_FULL__SCOPED_MASKED"
RP = runner.prior.RP + "__SCOPED_MASKED"
GATE = runner.prior.GATE + "__SCOPED_MASKED"


def lower_bound(result):
    interval = result.get("95pct_source_bootstrap")
    return interval[0] if interval is not None else None


def meets_superiority(result):
    difference, lower = result.get("match_delta"), lower_bound(result)
    return difference is not None and lower is not None and difference >= 0.03 and lower > 0


def numeric_screen(report, terminal):
    done = terminal and report["completed"] == report["planned"] == 233
    output = {"state": "PENDING_FULL_PANEL", "completed": report["completed"], "planned": report["planned"]}
    if not done:
        return output
    all_rows = report["paired"]["all"]
    mixed = report["paired"]["BC"][CONTROL]
    gate_delta = all_rows[GATE].get("match_delta")
    mixed_lower = lower_bound(mixed)
    upb = mixed["metric_pairs"].get("UPB", {}).get("delta")
    fm = mixed["metric_pairs"].get("FM", {}).get("delta")
    checks = {
        "superior_to_same_budget_direct": meets_superiority(all_rows[CONTROL]),
        "superior_to_archived_RP": meets_superiority(all_rows[RP]),
        "point_above_archived_gate": gate_delta is not None and gate_delta > 0,
        "mixed_match_lower_bound_at_least_minus_3pp": mixed_lower is not None and mixed_lower >= -0.03,
        "mixed_underuse_increase_at_most_0_1": upb is not None and upb <= 0.1,
        "mixed_feasibility_increase_at_most_0_1": fm is not None and fm <= 0.1,
    }
    strength = all_rows[VISIBILITY].get("match_delta")
    visibility_lower = lower_bound(all_rows[VISIBILITY])
    return {**output, "state": "PASSED_NUMERIC_REQUIRES_BEHAVIOR_AUDIT" if all(checks.values()) else "NUMERIC_GATE_FAILED",
            "checks": checks, "visibility_match_delta": strength,
            "visibility_direction_confirmed": strength is not None and visibility_lower is not None
            and strength > 0 and visibility_lower > 0,
            "legitimate_BC_and_task_quality_independently_verified": False}


def assess():
    frozen = runner.read(runner.OUT / "FROZEN.json")
    status = runner.read(runner.OUT / "RUN_STATE.json")
    return numeric_screen(runner.report(frozen), status["state"] == "COMPLETE")


if __name__ == "__main__":
    print(json.dumps(assess(), ensure_ascii=False, indent=2))
