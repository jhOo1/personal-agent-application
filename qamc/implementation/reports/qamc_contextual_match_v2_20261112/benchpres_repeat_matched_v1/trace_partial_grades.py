"""Replay valid BenchPreS fields from partially graded draws without replacing scores."""

import argparse
from collections import Counter
import json

import qamc_benchpres_matched_fieldwise_audit as fieldwise
from proposals.qamc_protocol_alignment.sampling import sampling_key
from qamc.common import sha
from report_qamc_benchpres_three_draw import replay
from trace_misuse import jobs, run
from trace_nonbold import response


def fields(area, row, ref, query, protocol, actors, judges):
    uid, arm, draw = row["uid"], row["method"], row["replicate"]
    raw = {}
    if row["actor_status"] == "OK":
        answer = response(area, "generation", actors[uid, arm, draw, "Actor"])
        if not answer:
            return fieldwise.archived_fields({**row, "raw_scores": raw}, ref)
        for stage, system, content in run.prior.score.initial_requests(run.ROOT, "benchpres", ref, query, answer):
            job = judges[uid, arm, draw, stage]
            request = run.prior.text_request(system, content, protocol["model"],
                                             protocol["stages"][stage]["max_tokens"])
            if request != job["request"]:
                raise ValueError("Judge wire differs from the answer and frozen evaluation inputs")
            receipt = run.read(area / "grading/outputs" / f"{sampling_key(job['unit'])}.json")
            if receipt["unit"] != job["unit"] or receipt["request_sha256"] != sha(request):
                raise ValueError("Judge receipt differs from frozen request")
            if receipt["status"] != "OK":
                continue
            raw[stage] = response(area, "grading", job)
    return fieldwise.archived_fields({**row, "raw_scores": raw}, ref)


def audit(plan, waves):
    primary = replay(plan, waves)
    cases = {case["uid"]: case for case in plan["cases"]}
    totals = {metric: [] for metric in fieldwise.METRICS}
    protocol = plan["protocols"]["grading"]
    partial = {arm: Counter() for arm in run.METHODS}
    for wave in primary["settled_waves"]:
        area = run.RUN / f"wave-{wave}"
        actors, judges = jobs(area, "ACTOR"), jobs(area, "JUDGE")
        rows = {(r["uid"], r["method"], r["replicate"]): r for r in run.read(area / "RESULTS.json")}
        for uid in plan["waves"][wave]:
            ref = run.read(run.ROOT / cases[uid]["evaluation_path"])
            query = run.prior.base.task_for(cases[uid]).query
            for draw in run.REPEATS:
                parsed = {}
                for arm in run.METHODS:
                    row = rows[uid, arm, draw]
                    attrs, completeness = fields(area, row, ref, query, protocol, actors, judges)
                    if row["actor_status"] == "OK" and row["score"] is None:
                        partial[arm].update(draws=1,
                                            valid_attributes=sum(a["follow"] is not None for a in attrs),
                                            valid_completeness=int(completeness is not None))
                    parsed[arm] = attrs, completeness
                left, right = run.METHODS
                slots = []
                for a, b in zip(parsed[left][0], parsed[right][0], strict=True):
                    slots.append({"uid": uid, "appropriate": a["appropriate"], "attribute": a["attribute"],
                                  "values": {left: a["follow"], right: b["follow"]}})
                complete = {uid: {"values": {arm: parsed[arm][1] for arm in run.METHODS}}}
                for metric in totals:
                    totals[metric].extend(fieldwise.elements(metric, slots, complete))
    result = {}
    for metric, values in totals.items():
        low, high = (1, 5) if metric == "completeness" else (0, 1)
        result[metric] = fieldwise.delta_bounds(values, *run.METHODS, low, high)
    return {"settled_waves": primary["settled_waves"], "valid_fields_on_actor_ok_aggregate_missing": partial,
            "fieldwise_diagnostic_only": result, "score_changes": 0, "new_model_calls": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wave", nargs="+", type=int, choices=range(6))
    args = parser.parse_args()
    print(json.dumps(audit(run.read(run.RUN / "PLAN_PRIVATE.json"), args.wave), indent=2, sort_keys=True))
