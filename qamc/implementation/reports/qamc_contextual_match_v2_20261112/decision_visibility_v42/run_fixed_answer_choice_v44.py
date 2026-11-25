"""Launch V44 on the preflighted fixed-answer panel with one durable dispatch ledger."""
from argparse import ArgumentParser
import json
from pathlib import Path

from qamc.common import canonical, sha, token_estimate

import preflight_fixed_answer_choice as contract

stage = contract.study
probe, read = stage.probe, stage.read
OUT = stage.OUT.with_name("fixed_answer_choice_rpeval_v44")
RUN = stage.RUN.with_name(OUT.name)
STAGE = "AnswerChoice"
ARMS = tuple(contract.METHOD_PROMPTS)


def prepare(reference):
    preflight = contract.preflight()
    previous = stage.OUT / "FIXED_ANSWER_CHOICE_PREFLIGHT.json"
    if read(previous) != preflight:
        raise ValueError("Request contract differs from the prior offline preflight")
    parent_path = stage.prior.OUT / "FROZEN.json"
    parent = read(parent_path)
    drafts = contract.saved_drafts(parent)
    by_uid = {root["uid"]: root for root in parent["roots"]}
    protocol = {
        "experiment": OUT.name, "model": "qwen3.8-flash", "concurrency": 8,
        "spacing_seconds": 3.2, "stages": {STAGE: {"max_tokens": 8192, "temperature": 0}},
        "automatic_retries": 0,
    }
    units, seen, reuse = [], {}, []
    maximum_input = 0
    for row in preflight["rows"]:
        if row["status"] != "BOTH_DRAFTS":
            continue
        root = by_uid[row["uid"]]
        rp = root["archived"][stage.prior.RP]["answer"]
        payload = contract.packet(root, rp, drafts[root["task_wire_sha256"]]["answer"])
        for method in ARMS:
            wire = contract.request(payload, method)
            digest = sha(wire)
            if digest != row["request_sha256"][method]:
                raise ValueError("A live request differs from its offline identity")
            estimate = token_estimate(canonical(wire["messages"]))
            maximum_input = max(maximum_input, estimate)
            if estimate > 32768 or len(canonical(wire["messages"]).encode()) > 2_000_000:
                raise ValueError("Frozen request exceeds input capacity")
            key = {"uid": row["uid"], "method": method}
            if digest in seen:
                reuse.append({**key, "wire_sha256": digest, "reuse": seen[digest]})
            else:
                seen[digest] = key
                units.append({"unit": {"stage": STAGE, "root_id": row["uid"], "method": method,
                                       "replicate": 0, "protocol_sha256": sha(protocol)}, "request": wire})
    if len(units) + len(reuse) != preflight["planned_max_choice_requests"]:
        raise ValueError("Live manifest does not conserve frozen allocations")
    return {
        "service_reference_sha256": reference,
        "same_reference_file_as_archived": reference == parent["service_reference_sha256"],
        "preflight_sha256": sha(previous.read_bytes()),
        "archive_sha256": sha(parent_path.read_bytes()),
        "runner_sha256": sha(Path(__file__).read_bytes()),
        "independent_confirmation": False,
        "choice_request_cap": len(units), "actor_request_cap": 0, "judge_request_cap": 0,
        "eligible_roots": sum(row["status"] == "BOTH_DRAFTS" for row in preflight["rows"]),
        "maximum_estimated_input_tokens": maximum_input,
        "thresholds": {
            "overall_match_margin_vs_generic": 0.0,
            "overall_match_margin_vs_original_rp": 0.0,
            "overall_match_margin_vs_archived_strong_review": 0.0,
            "contains_BC_match_noninferiority_margin": 0.02,
            "UPB_and_FM_harm_margin_points_per_answer": 0.05,
            "paired_valid_fraction_minimum": 0.9,
            "bootstrap_unit": "source_group",
        },
    }, {"protocol": protocol, "units": units}, reuse


def artifacts():
    frozen = read(OUT / "FROZEN.json")
    plan, manifest, aliases = prepare(frozen["service_reference_sha256"])
    if (plan != frozen or read(OUT / (STAGE + "_MANIFEST.json")) != manifest
            or read(OUT / "WIRE_REUSE.json") != aliases):
        raise ValueError("Frozen V44 artifacts changed")
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
        raise ValueError("The V44 gateway reference changed after the new freeze")
    probe.OUT, probe.RUN = OUT, RUN
    state = OUT / "RUN_STATE.json"
    if state.exists() and read(state)["state"] == "COMPLETE":
        return
    probe.atomic_json(state, {"state": "RUNNING", "cap": plan["choice_request_cap"]})
    try:
        existing = probe.stage_receipts(STAGE)
        remaining = [job for job in manifest["units"]
                     if existing[job["unit"]["root_id"], job["unit"]["method"]][0] is None]
        stage.prior.dispatch(plan, STAGE, {**manifest, "units": remaining})
        issued = [r for r, _ in probe.stage_receipts(STAGE).values() if r]
        if len(issued) != plan["choice_request_cap"]:
            raise RuntimeError("Some frozen units remain undispatched")
        if any(r["status"] == "PENDING_DELIVERY_UNKNOWN" for r in issued):
            raise RuntimeError("A durable receipt is awaiting delivery settlement")
        probe.atomic_json(state, {"state": "COMPLETE", "physical_requests": len(issued)})
    except (RuntimeError, ValueError, OSError) as error:
        probe.atomic_json(state, {"state": "STOPPED", "error": str(error)})
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
