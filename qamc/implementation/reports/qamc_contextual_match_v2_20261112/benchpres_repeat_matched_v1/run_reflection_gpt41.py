"""A separate GPT-4.1 diagnostic on the exact frozen reflection panel."""

import argparse
from collections import Counter, defaultdict
import json

from freeze_reflection import PRIVATE, write_frozen
from proposals.qamc_protocol_alignment.sampling import RetainedSamplingAttempt, sampling_key
from proposals.qamc_protocol_alignment.transport import SamplingTransportError
from qamc.bace.runtime import runner_lock
from qamc.common import sha
from qamc.contextual_match.component_dispatch import BudgetGate
from qamc.contextual_match.runtime_minute_policy import MinuteControl, activate
from qamc.contextual_match.usage_observability import UsageObservableSampler
from qamc.transport_helpers import read_reference
from run_reflection_model import ROOT as SOURCE, make_plan, parse, run


ROOT = PRIVATE / "gpt41_model_diagnostic"
PROTOCOL = {"namespace": "benchpres_frozen_reflection_v1/gpt41_model_diagnostic",
            "model": "gpt-4.1", "concurrency": 1, "spacing_seconds": 3.2,
            "stages": {"Reflection": {"temperature": 0, "max_tokens": 2048}}}


def plan_from_source():
    source = run.read(SOURCE / "PLAN_PRIVATE.json")
    if source != make_plan():
        raise ValueError("Diagnostic source roster changed")
    jobs = []
    for original in source["jobs"]:
        unit = {"protocol_sha256": sha(PROTOCOL), "root_id": original["id"],
                "method": "reflection", "stage": "Reflection", "replicate": 0}
        request = {**original["request"], "model": PROTOCOL["model"],
                   **PROTOCOL["stages"]["Reflection"], "stream_options": {"include_usage": True}}
        jobs.append({"unit": unit, "request": request})
    if len({sampling_key(j["unit"]) for j in jobs}) != source["physical_cap"]:
        raise ValueError("Duplicated or missing diagnostic positions")
    return {"protocol": PROTOCOL, "units": jobs, "source_plan_sha256": sha(source)}


def receipt(job):
    path = ROOT / "execution" / "visible" / sampling_key(job["unit"])
    if not (path / "record.json").is_file():
        return None, None
    row = run.read(path / "record.json")
    if row["unit"] != job["unit"] or row["request_sha256"] != sha(job["request"]):
        raise ValueError("Receipt does not match the frozen unit")
    if row["status"] != "OK":
        return row, None
    saved = run.read(path / "response.json")
    try:
        return row, parse(saved["answer"], job["request"])["reflection"]
    except (TypeError, ValueError):
        return row, None


def dispatch(plan):
    if (ROOT / "TERMINAL").exists():
        return
    prior = [row for job in plan["units"] if (row := receipt(job)[0])]
    if any(r["status"] == "PENDING_DELIVERY_UNKNOWN" for r in prior):
        raise ValueError("Retained delivery-unknown unit")
    _, fingerprint = read_reference()
    write_frozen(ROOT / "SERVICE_SHA256", fingerprint)
    gate = BudgetGate(ROOT / "PACING.json", spacing=3.2, cooldown=301, limit=len(plan["units"]))
    activate(gate, max((r["started_unix"] + r["elapsed_seconds"] for r in prior if r["status"] != "OK"), default=0))
    sampler = UsageObservableSampler(ROOT / "execution", plan)
    sampler.control = MinuteControl(sampler.control, gate)
    consecutive = 0
    try:
        for job in plan["units"]:
            if receipt(job)[0] is None:
                try:
                    sampler.perform(job["unit"], job["request"])
                except (SamplingTransportError, RetainedSamplingAttempt):
                    pass
            row, label = receipt(job)
            if row is None or row["status"] == "PENDING_DELIVERY_UNKNOWN":
                return
            if row["reference_config_sha256"] != fingerprint:
                raise ValueError("Receipt came from a different service")
            if row.get("http_status") in (401, 403) or row.get("error") == "quota_or_auth":
                break
            if label is None:
                consecutive += 1
                if row["status"] == "OK":
                    sampler.control.cooldown()
                if consecutive >= 2:
                    break
            else:
                consecutive = 0
        write_frozen(ROOT / "TERMINAL", "Settled fixed-answer diagnostic\n")
    finally:
        sampler.close()


def summarize(plan):
    source = run.read(SOURCE / "PLAN_PRIVATE.json")
    metadata = {job["id"]: job for job in source["jobs"]}
    outcomes = Counter()
    shifts, pairs = defaultdict(Counter), defaultdict(dict)
    tokens = unknown = 0
    for job in plan["units"]:
        row, model_label = receipt(job)
        if row is None:
            continue
        fields = metadata[job["unit"]["root_id"]]
        old_label = "yes" if fields["old_follow"] else "no"
        outcomes[row["status"] if row["status"] != "OK" or model_label else "INVALID_LABEL"] += 1
        usage = (row.get("usage") or {}).get("total_tokens")
        tokens += usage or 0
        unknown += usage is None
        if model_label is not None:
            shifts[fields["stratum"]][f"{old_label}_to_{model_label}"] += 1
            pairs[fields["pair"]][fields["arm"]] = (fields["stratum"], old_label, model_label)
    paired = defaultdict(Counter)
    for pair in pairs.values():
        if set(pair) == set(run.METHODS):
            stratum, old_left, left = pair[run.GATE]
            _, old_right, right = pair[run.PAPER]
            paired[stratum][f"{old_left}/{old_right}_to_{left}/{right}"] += 1
    return {"model": PROTOCOL["model"], "panel_pairs": len(source["jobs"]) // 2,
            "attempted_requests": sum(outcomes.values()), "reported_tokens": tokens,
            "unknown_usage": unknown, "terminal": (ROOT / "TERMINAL").exists(),
            "request_states": outcomes, "paired_valid_votes": sum(sum(x.values()) for x in paired.values()),
            "single_vote_transitions": shifts, "paired_transitions": paired,
            "human_reviews": 0, "original_scores_replaced": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "report"))
    args = parser.parse_args()
    if args.action == "prepare":
        ROOT.mkdir(mode=0o700, exist_ok=True)
    with runner_lock(ROOT / "runner.lock"):
        plan = plan_from_source()
        path = ROOT / "PLAN_PRIVATE.json"
        if args.action == "prepare":
            write_frozen(path, json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
        if run.read(path) != plan:
            raise ValueError("Stored GPT-4.1 plan differs from reconstruction")
        if args.action == "run":
            dispatch(plan)
        print(json.dumps(summarize(plan), indent=2, sort_keys=True))
