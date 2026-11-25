"""Run one V45 decision-witness request per reusable pair of development answers."""
from argparse import ArgumentParser
import json
from pathlib import Path

from qamc.common import canonical, sha, token_estimate

import decision_witness_v45 as contract
import run_fixed_answer_choice_v44 as parent

stage, probe, read = parent.stage, parent.probe, parent.read
OUT = parent.OUT.with_name("decision_witness_rpeval_v45")
RUN = parent.RUN.with_name(OUT.name)
STAGE = "DecisionWitness"
METHOD = "WITNESS"


def prepare(reference):
    archived, _, _ = parent.artifacts()
    parent_plan = stage.prior.OUT / "FROZEN.json"
    plan = read(parent_plan)
    eligible = read(stage.OUT / "FIXED_ANSWER_CHOICE_PREFLIGHT.json")
    drafts = contract.parent.saved_drafts(plan)
    roots = {root["uid"]: root for root in plan["roots"]}
    protocol = {
        "experiment": OUT.name, "model": "qwen3.8-flash", "concurrency": 8, "spacing_seconds": 3.2,
        "stages": {STAGE: {"max_tokens": 8192, "temperature": 0}}, "automatic_retries": 0,
    }
    units, aliases, seen = [], [], {}
    maximum = 0
    for row in eligible["rows"]:
        if row["status"] != "BOTH_DRAFTS":
            continue
        uid = row["uid"]
        root = roots[uid]
        rp = root["archived"][stage.prior.RP]["answer"]
        draft = drafts[root["task_wire_sha256"]]["answer"]
        payload = contract.packet(root, rp, draft)
        for candidate in payload["candidates"]:
            if sha(candidate["answer"]) != row["answer_sha256"][candidate["id"]]:
                raise ValueError("A candidate changed since the fixed-answer comparison")
        wire = contract.request(payload)
        digest = sha(wire)
        estimate = token_estimate(canonical(wire["messages"]))
        maximum = max(maximum, estimate)
        if estimate > 32768 or len(canonical(wire["messages"]).encode()) > 2_000_000:
            raise ValueError("Input capacity gate")
        if digest in seen:
            aliases.append({"uid": uid, "request_sha256": digest, "physical_uid": seen[digest]})
        else:
            seen[digest] = uid
            units.append({"unit": {"stage": STAGE, "root_id": uid, "method": METHOD,
                                   "replicate": 0, "protocol_sha256": sha(protocol)}, "request": wire})
    if len(units) + len(aliases) != archived["eligible_roots"]:
        raise ValueError("Logical allocation differs from V44 paired development panel")
    return {
        "service_reference_sha256": reference,
        "same_reference_file_as_v44": reference == archived["service_reference_sha256"],
        "development_roots": len(plan["roots"]), "eligible_roots": archived["eligible_roots"],
        "witness_request_cap": len(units), "actor_request_cap": 0, "judge_request_cap": 0,
        "independent_confirmation": False, "maximum_estimated_input_tokens": maximum,
        "runner_sha256": sha(Path(__file__).read_bytes()),
        "contract_sha256": sha(Path(contract.__file__).read_bytes()),
        "archive_sha256": sha(parent_plan.read_bytes()),
        "thresholds": {
            "coverage": 0.9,
            "overall_gain_lower_bound": 0.0,
            "C_prior_match_noninferiority_margin": 0.02,
            "contains_BC_match_noninferiority_margin": 0.02,
            "contains_BC_UPB_and_FM_harm_margin_per_answer": 0.05,
            "bootstrap_unit": "source_group",
        },
    }, {"protocol": protocol, "units": units}, aliases


def artifacts():
    frozen = read(OUT / "FROZEN.json")
    plan, manifest, aliases = prepare(frozen["service_reference_sha256"])
    if (plan != frozen or read(OUT / (STAGE + "_MANIFEST.json")) != manifest
            or read(OUT / "WIRE_REUSE.json") != aliases):
        raise ValueError("V45 frozen artifacts changed")
    return plan, manifest, aliases


def freeze():
    plan, manifest, aliases = prepare(probe.read_reference()[1])
    probe.freeze(OUT / (STAGE + "_MANIFEST.json"), manifest)
    probe.freeze(OUT / "WIRE_REUSE.json", aliases)
    probe.freeze(OUT / "FROZEN.json", plan)
    return plan


def run():
    plan, manifest, _ = artifacts()
    if probe.read_reference()[1] != plan["service_reference_sha256"]:
        raise ValueError("V45 gateway reference changed")
    probe.OUT, probe.RUN = OUT, RUN
    path = OUT / "RUN_STATE.json"
    if path.exists() and read(path)["state"] == "COMPLETE":
        return
    probe.atomic_json(path, {"state": "RUNNING", "cap": plan["witness_request_cap"]})
    try:
        old = probe.stage_receipts(STAGE)
        unseen = [item for item in manifest["units"]
                  if old[item["unit"]["root_id"], METHOD][0] is None]
        stage.prior.dispatch(plan, STAGE, {**manifest, "units": unseen})
        issued = [receipt for receipt, _ in probe.stage_receipts(STAGE).values() if receipt]
        if len(issued) != plan["witness_request_cap"]:
            raise RuntimeError("Undispatched frozen units remain")
        if any(r["status"] == "PENDING_DELIVERY_UNKNOWN" for r in issued):
            raise RuntimeError("A durable call reservation is still unsettled")
        probe.atomic_json(path, {"state": "COMPLETE", "physical_requests": len(issued)})
    except (RuntimeError, ValueError, OSError) as error:
        probe.atomic_json(path, {"state": "STOPPED", "error": str(error)})
        raise


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run"))
    args = parser.parse_args()
    with probe.runner_lock(RUN / "runner.lock"):
        if args.action == "freeze":
            print(json.dumps(freeze(), ensure_ascii=False, indent=2))
        else:
            run()
