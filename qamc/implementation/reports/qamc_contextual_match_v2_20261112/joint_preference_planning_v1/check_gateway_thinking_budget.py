"""Check gateway handling of one reasoning cap on exact archived requests."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path
from unittest.mock import patch

from qamc.common import sha

from audit_decision_transactions import reasoning_tokens
import run_decision_transactions as parent
from thinking_budget_transport import FIELD, MODEL, ThinkingBudgetSampler, controlled_wire


OUT = parent.BASE_OUT / "budget_calibration"
RUN = parent.BASE_RUN / "budget_calibration"
STAGE = "ThinkingBudget"
BUDGET = 4096
DEVELOPMENT_CASES = ("explicit/029", "explicit/116")
probe = parent.probe


def prepare():
    smoke = parent.BASE_OUT / "smoke"
    if parent.read(smoke / "RUN_STATE.json")["state"] != "COMPLETE":
        raise ValueError("Unverified smoke archive")
    _, jobs, _, _, cache = parent.prepare("smoke")
    archived = {**cache[parent.STAGE], **parent.read(smoke / f"{parent.STAGE}_EXACT.json")}
    protocol = {"experiment": "decision_transactions_thinking_budget_calibration", "model": MODEL,
                "concurrency": 2, "spacing_seconds": 3.2, "automatic_retries": 0,
                "stages": {STAGE: {"temperature": 0, "max_tokens": 8192, FIELD: BUDGET}}}
    metadata, units = {}, []
    for uid, arm, request in jobs:
        if not uid.endswith(DEVELOPMENT_CASES):
            continue
        digest = sha(request)
        record, _ = archived[digest]
        if record["status"] != "OK" or record["request_sha256"] != digest:
            raise ValueError("Calibration requires a matching prior request and successful receipt")
        key = {"stage": STAGE, "root_id": uid, "method": arm, "replicate": 0, "protocol_sha256": sha(protocol)}
        metadata[f"{uid}/{arm}"] = {"default_wire_sha256": digest, "reported_usage": record["usage"],
                                    "reported_reasoning_tokens": reasoning_tokens(record)}
        units.append({"unit": key, "request": controlled_wire(request, BUDGET)})
    digests = {sha(item["request"]) for item in units}
    if len(units) != 4 or len(digests) != 4 or digests & archived.keys():
        raise ValueError("Calibration roster or wire identity changed")
    files = [Path(__file__), Path(ThinkingBudgetSampler.__init__.__code__.co_filename), smoke / "FROZEN.json",
             smoke / f"{parent.STAGE}_EXACT.json", smoke / "SETTLED.json"]
    repository = Path(__file__).resolve().parents[3]
    return {
        "manifest": {"protocol": protocol, "units": units},
        "prior": metadata, "physical_cap": len(units), "new_scores": 0,
        "service_reference_sha256": parent.read(smoke / "FROZEN.json")["service_reference_sha256"],
        "sha256": {str(p.resolve().relative_to(repository)): sha(p.read_bytes()) for p in files},
    }


def observe(plan):
    work = probe.stage_receipts(STAGE)
    comparison = []
    for item in plan["manifest"]["units"]:
        unit, request = item["unit"], item["request"]
        uid, arm = unit["root_id"], unit["method"]
        record, text = work.get((uid, arm), (None, None))
        if record and record["request_sha256"] != sha(request):
            raise ValueError("Calibrated receipt differs from the frozen request")
        reported = reasoning_tokens(record) if record else None
        before = plan["prior"][f"{uid}/{arm}"]
        comparison.append({"uid": uid, "method": arm, "default": before, "requested_thinking_budget": BUDGET,
                           "status": record["status"] if record else "UNISSUED",
                           "reported_usage": record["usage"] if record else None, "reported_reasoning_tokens": reported,
                           "within_requested_reasoning": reported <= BUDGET if reported is not None else None,
                           "receipt": record, "answer": text if record and record["status"] == "OK" else None})
    exceeds_by_default = [r for r in comparison if (r["default"]["reported_reasoning_tokens"] or 0) > BUDGET]
    return {
        "rows": comparison, "statuses": Counter(r["status"] for r in comparison),
        "actual_requests": sum(r["receipt"] is not None for r in comparison), "new_scores": 0,
        "originally_above_cap": len(exceeds_by_default),
        "all_originally_above_observed_within_cap": bool(exceeds_by_default) and all(
            r["status"] == "OK" and r["within_requested_reasoning"] is True for r in exceeds_by_default),
        "provider_general_enforcement_certified": False,
    }


def execute(plan):
    if parent.read(OUT / "FROZEN.json") != plan:
        raise ValueError("Calibration differs from the frozen inputs")
    if (OUT / "SETTLED.json").exists():
        raise ValueError("Completed calibration is not restarted")
    # The pilot has its own pacing and journal. Hold its runner lock so the
    # calibration never overlaps its live dispatch.
    with probe.runner_lock(parent.BASE_RUN / "pilot" / "runner.lock"), probe.runner_lock(RUN / "runner.lock"):
        probe.OUT, probe.RUN = OUT, RUN
        manifest = plan["manifest"]
        probe.freeze(OUT / f"{STAGE}_MANIFEST.json", manifest)
        probe.atomic_json(OUT / "RUN_STATE.json", {"state": "RUNNING"})
        try:
            with patch.object(probe, "UsageObservableSampler", ThinkingBudgetSampler):
                parent.replay.prior.dispatch(plan, STAGE, manifest)
        except (ValueError, RuntimeError, OSError) as error:
            probe.atomic_json(OUT / "RUN_STATE.json", {"state": "STOPPED", "error": str(error)})
            raise
        finally:
            observed = observe(plan)
            probe.freeze(OUT / f"OBSERVED_{sha(observed)[:16]}.json", observed)
        if any(r["status"] in {"UNISSUED", "PENDING_DELIVERY_UNKNOWN"} for r in observed["rows"]):
            probe.atomic_json(OUT / "RUN_STATE.json", {"state": "STOPPED", "error": "Unresolved delivery"})
            raise RuntimeError("Unresolved delivery")
        probe.freeze(OUT / "SETTLED.json", observed)
        probe.atomic_json(OUT / "RUN_STATE.json", {"state": "COMPLETE", "actual_requests": observed["actual_requests"]})


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "freeze", "run"))
    args = parser.parse_args()
    plan = prepare()
    if args.action == "run":
        execute(plan)
    else:
        print(json.dumps({"new_requests": 0, "possible_live_requests": plan["physical_cap"],
                          "recorded_defaults": plan["prior"]}, ensure_ascii=False, indent=2))
        if args.action == "freeze":
            probe.freeze(OUT / "FROZEN.json", plan)
