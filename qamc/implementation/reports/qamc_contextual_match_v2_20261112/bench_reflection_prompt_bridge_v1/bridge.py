"""Vary only the evaluation model on the existing fixed-answer audit."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
import json
from pathlib import Path

import run_reflection_gpt41 as parent
from analyze_reflection import agreement
from qamc.common import sha
from run_car import engine, probe
from extend import archived, merge_stage

HERE = Path(__file__).resolve().parent
RUN = engine.RUN.with_name(HERE.name)
MODEL = "qwen3.8-flash"
STAGE = "QwenReflection"
LABELS = {"yes": 1, "no": 0}
METHODS = (parent.run.GATE, parent.run.PAPER)
TRACKS = ("Original Qwen", "Masked Qwen", "Masked GPT-4.1")


def locked_work():
    prior = parent.plan_from_source()
    source = parent.run.read(parent.SOURCE / "PLAN_PRIVATE.json")
    prior_jobs = {unit["unit"]["root_id"]: unit for unit in prior["units"]}
    source_jobs = {item["id"]: item for item in source["jobs"]}
    if len(prior_jobs) != 28 or set(prior_jobs) != set(source_jobs):
        raise ValueError("The existing frozen 14 pairs are required")
    jobs, history = {}, {}
    cohorts = defaultdict(set)
    for key, unit in prior_jobs.items():
        old_record, old_vote = parent.receipt(unit)
        if old_record is None or old_record["status"] != "OK" or old_vote not in LABELS:
            raise ValueError("Earlier masked vote is not usable")
        item = source_jobs[key]
        if sha(unit["request"]) != old_record["request_sha256"]:
            raise ValueError("Archived request drift")
        jobs[key, "BLIND"] = {**unit["request"], "model": MODEL}
        history[key] = {k: item[k] for k in ("pair", "arm", "stratum", "old_follow")}
        history[key]["masked_gpt41"] = LABELS[old_vote]
        cohorts[item["pair"]].add(item["arm"])
    if any(arms != set(METHODS) for arms in cohorts.values()):
        raise ValueError("Original diagnostic paired assignment changed")
    return jobs, history, {
        "old_plan_sha256": sha(prior),
        "cases_sha256": sha(history),
        "request_sha256": sha(list(jobs.values())),
        "protocol_sha256": sha((HERE / "PROTOCOL.md").read_bytes()),
        "code_sha256": sha(Path(__file__).read_bytes()),
        "physical_request_cap": len(jobs),
        "actor_requests": 0,
    }


def verdict(result, wire):
    if result["status"] != "OK":
        return result["status"], None
    try:
        value = parent.parse(result["answer"], wire)["reflection"]
    except (TypeError, ValueError, KeyError):
        return "INVALID_CONTRACT", None
    return ("OK", LABELS[value]) if value in LABELS else ("UNCERTAIN", None)


def aggregate(history, replies, jobs):
    cohorts = defaultdict(dict)
    status = Counter()
    for key, prev in history.items():
        unit = key, "BLIND"
        record, label = verdict(replies[unit], jobs[unit])
        status[record] += 1
        if label is None:
            continue
        cohorts[prev["pair"]][prev["arm"]] = (
            prev["stratum"], (int(prev["old_follow"]), label, prev["masked_gpt41"]))
    strata = defaultdict(list)
    for pair in cohorts.values():
        if set(pair) != set(METHODS):
            continue
        left, right = (pair[m] for m in METHODS)
        if left[0] != right[0]:
            raise ValueError("Different strata within a pair")
        strata[left[0]].append((left[1], right[1]))
    totals = {}
    for stratum in sorted({row["stratum"] for row in history.values()}):
        pairs = strata[stratum]
        totals[stratum] = {"common_pairs": len(pairs)}
        for pos, track in enumerate(TRACKS):
            totals[stratum][track] = {method: sum(pair[idx][pos] for pair in pairs)
                                      for idx, method in enumerate(METHODS)}
        for idx, method in enumerate(METHODS):
            votes = [pair[idx] for pair in pairs]
            totals[stratum][f"{method}/presentation_agreement"] = agreement([(old, masked) for old, masked, _ in votes])
            totals[stratum][f"{method}/masked_model_agreement"] = agreement([(masked, gpt) for _, masked, gpt in votes])
    return {"assigned_pairs": len(history) // 2, "states": status, "comparison": totals,
            "old_scores_replaced": 0, "human_reviews": 0}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "report"))
    args = parser.parse_args()
    jobs, history, pin = locked_work()
    RUN.mkdir(parents=True, exist_ok=True)
    engine.OUT = probe.OUT = probe.RUN = RUN
    engine.CAP = {STAGE: len(jobs)}
    with probe.runner_lock(RUN / "runner.lock"):
        if args.action == "freeze":
            probe.freeze(RUN / "FROZEN.json", pin)
            print(json.dumps(pin, indent=2))
            return
        if probe.read(RUN / "FROZEN.json") != pin:
            raise ValueError("Frozen scope drift")
        if args.action == "run":
            identity = {"experiment_sha256": sha(pin), "service_reference_sha256": probe.read_reference()[1]}
            probe.freeze(RUN / "EXECUTION.json", identity)
            cache, _ = archived(jobs, HERE.parents[2])
            cache = {key: row for key, row in cache.items() if RUN.name not in Path(row["archive"]).parts}
            ledger = []
            results = merge_stage(STAGE, jobs, cache, identity, ledger)
            draft = aggregate(history, results, jobs)
            totals = [(row.get("usage") or {}).get("total_tokens") for row in ledger]
            draft.update({"physical_requests": len(ledger), "exact_archive_hits": len(cache),
                          "reported_tokens": sum(n or 0 for n in totals),
                          "unknown_usage": totals.count(None), "actor_requests": 0,
                          "automatic_retries": sum(row.get("automatic_retries", 0) for row in ledger)})
            probe.freeze(RUN / "PHYSICAL_LEDGER.json", ledger)
            probe.freeze(RUN / "SUMMARY.json", draft)
        print(json.dumps(probe.read(RUN / "SUMMARY.json"), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
