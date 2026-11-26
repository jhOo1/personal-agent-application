"""Reconcile and export the frozen BenchPreS repeat study without model calls."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from audit_qamc_benchpres_repeat_costs import audit as costs
from audit_qamc_benchpres_repeat_profiles import audit as profiles
from audit_qamc_benchpres_sampling_stability import audit as stability
from report_qamc_benchpres_three_draw import replay
from trace_misuse import audit as misuse, run
from trace_nonbold_delivery import audit as delivery
from trace_partial_grades import audit as fieldwise
from trace_repeat_identity import audit as identity


def reconcile(bundle, preflight):
    report = bundle["REPLAY"]
    receipts = report["receipts_in_terminal_waves"]
    as_reported = receipts["physical_requests"]
    roster = bundle["IDENTITY"]
    if as_reported != roster["physical_calls"] or as_reported > preflight["cloud_cap"]:
        raise ValueError("Physical calls differ from verified ledger or exceed the frozen cap")
    if roster["recorded_max_overlap"] > 8:
        raise ValueError("Recorded request overlap exceeds the frozen cap")
    totals = (stage for method in bundle["COSTS"]["methods"].values() for stage in method.values())
    calls, tokens, unknown = 0, 0, 0
    statuses = Counter()
    for row in totals:
        calls += row["calls"]
        tokens += row["usage"]["total_tokens"]["known"]
        unknown += row["usage"]["total_tokens"]["unknown"]
        statuses.update(row["statuses"])
        if row["automatic_retries"]:
            raise ValueError("Unexpected automatic retry")
    if (calls, tokens, unknown, statuses) != (as_reported, receipts["reported_tokens"],
                                             receipts["unknown_usage"], receipts["request_statuses"]):
        raise ValueError("Ledger totals differ from the primary replay")
    pairs = report["available_pairs"]
    if pairs["task_draw_pairs"] != bundle["MISUSE_TRACE"]["paired_task_draws"]:
        raise ValueError("Misuse and primary pair counts differ")
    checked = {}
    for name, metric in pairs["metrics"].items():
        fields = bundle["FIELDWISE"]["fieldwise_diagnostic_only"][name]
        if fields["common_observed"] < metric["denominator"]:
            raise ValueError("Fieldwise replay dropped a strict pair")
        checked[name] = fields["common_observed"]
    cohort = bundle["DELIVERY_TRACE"]["paired_positions_by_gate_delivery"]
    if sum(c["paired_positions"] for c in cohort.values()) != pairs["metrics"]["nonbold_AAR"]["denominator"]:
        raise ValueError("Delivery trace does not cover the strict non-bold denominator")
    if report["full_allocation_terminal"]:
        allocated = report["allocated_task_draw_pairs"] * len(run.METHODS)
        if allocated != preflight["allocated_actor_positions"]:
            raise ValueError("Terminal allocation does not match preflight")
        if any("WAVE_NOT_SETTLED" in states for states in report["scoring_states"].values()):
            raise ValueError("Terminal comparison includes unsettled rows")
    return {
        "settled_waves": report["settled_waves"],
        "whole_allocation_terminal": report["full_allocation_terminal"],
        "confirmed_physical_calls": calls,
        "confirmed_reported_tokens": tokens,
        "confirmed_unknown_usage": unknown,
        "common_paired_draws": pairs["task_draw_pairs"],
        "verified_fieldwise_denominators": checked,
        "new_model_calls": 0,
    }


def collect(waves=None):
    plan = run.read(run.RUN / "PLAN_PRIVATE.json")
    primary = replay(plan, waves)
    if waves is None and not primary["full_allocation_terminal"]:
        raise ValueError("A final export requires all waves to be settled")
    selected = primary["settled_waves"]
    bundle = {
        "REPLAY": primary, "COSTS": costs(selected), "PROFILE_TRACE": profiles(plan, selected),
        "STABILITY": stability(selected), "MISUSE_TRACE": misuse(selected),
        "DELIVERY_TRACE": delivery(selected), "FIELDWISE": fieldwise(plan, selected),
        "IDENTITY": identity(selected),
    }
    acceptance = reconcile(bundle, run.read(run.OUT / "PREFLIGHT.json"))
    return bundle, acceptance


def export(bundle, acceptance, target):
    prefix = "FINAL" if acceptance["whole_allocation_terminal"] else "WAVES" + "".join(
        str(w) for w in acceptance["settled_waves"]
    )
    files = {f"{prefix}_{name}.json": (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
             for name, value in bundle.items()}
    acceptance = {
        **acceptance,
        "verified_artifacts": {name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
    }
    files[f"{prefix}_ACCEPTANCE.json"] = (json.dumps(acceptance, indent=2, sort_keys=True) + "\n").encode()
    target.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        path = target / name
        if path.exists() and path.read_bytes() != data:
            raise ValueError(f"Existing export differs: {name}")
    for name, data in files.items():
        path = target / name
        if not path.exists():
            with path.open("xb") as handle:
                handle.write(data)
    return acceptance


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wave", nargs="+", type=int, choices=range(6))
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    bundle, acceptance = collect(args.wave)
    if args.out:
        acceptance = export(bundle, acceptance, args.out)
    print(json.dumps(acceptance, indent=2, sort_keys=True))
