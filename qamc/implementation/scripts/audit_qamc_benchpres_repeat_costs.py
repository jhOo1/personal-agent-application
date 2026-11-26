"""Reconcile the actual transports and paired Actor costs on settled BenchPreS waves."""

import argparse
from collections import Counter, defaultdict
import json
from statistics import median

import run_qamc_benchpres_three_draw as run
from proposals.qamc_protocol_alignment.sampling import sampling_key
from qamc.common import sha


USAGE = ("prompt_tokens", "completion_tokens", "total_tokens")


def totals(records):
    return {"calls": len(records), "statuses": Counter(r["status"] for r in records),
            "automatic_retries": sum(r["automatic_retries"] for r in records),
            "usage": {key: {"known": sum((r["usage"] or {}).get(key, 0) for r in records),
                            "unknown": sum(key not in (r["usage"] or {}) for r in records)}
                      for key in USAGE}}


def audit(waves):
    plan = run.read(run.RUN / "PLAN_PRIVATE.json")
    run.valid(plan)
    if sha(plan) != run.read(run.OUT / "PREFLIGHT.json")["plan_sha256"]:
        raise ValueError("Private plan differs from committed preflight")
    grouped = defaultdict(lambda: defaultdict(list))
    answers = defaultdict(dict)
    for wave in waves:
        area = run.RUN / f"wave-{wave}"
        if not (area / "RESULTS.json").exists():
            raise ValueError("Offline cost audit requires all requested waves to be settled")
        ledger = []
        for stage, stem in (("generation", "ACTOR"), ("grading", "JUDGE")):
            jobs = run.read(area / f"{stem}_MANIFEST.json")["units"]
            keys = {sampling_key(j["unit"]): j for j in jobs}
            if len(jobs) != len(keys):
                raise ValueError("Repeated unit in frozen stage")
            for p in (area / stage / "execution/visible").glob("*/record.json"):
                r = run.read(p)
                j = keys[p.parent.name]
                if (j["unit"] != r["unit"] or sha(j["request"]) != r["request_sha256"]
                        or r["reference_config_sha256"] != plan["reference_sha256"]):
                    raise ValueError("Transport receipt does not match frozen plan")
                unit = r["unit"]
                arm = unit["method"]
                grouped[arm][stage].append(r)
                ledger.append(r)
                if stage == "generation" and r["status"] == "OK":
                    key = unit["root_id"], unit["replicate"]
                    if arm in answers[key]:
                        raise ValueError("Repeated physical Actor for one sampling unit")
                    answers[key][arm] = r
        summary = run.read(area / "SUMMARY.json")
        if len(ledger) != summary["new_model_calls"] or totals(ledger)["usage"]["total_tokens"]["known"] != summary["reported_tokens"]:
            raise ValueError("Ledger and settlement totals differ")
    paired = [cell for cell in answers.values() if set(cell) == set(run.METHODS)]
    comparison = {}
    for arm in run.METHODS:
        rows = [p[arm] for p in paired]
        comparison[arm] = {"summary": totals(rows), "median_elapsed_seconds": median(
            [r["elapsed_seconds"] for r in rows]) if rows else None}
        for name in USAGE:
            values = [(r["usage"] or {})[name] for r in rows if name in (r["usage"] or {})]
            comparison[arm]["median_" + name] = median(values) if values else None
    return {"waves": waves, "methods": {arm: {stage: totals(rows) for stage, rows in grouped[arm].items()}
                                        for arm in run.METHODS},
            "successful_actor_pairs": len(paired), "paired_actor": comparison,
            "frozen_selector_cost_excluded": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wave", type=int, nargs="+", required=True, choices=range(6))
    args = parser.parse_args()
    print(json.dumps(audit(sorted(set(args.wave))), indent=2, sort_keys=True))
