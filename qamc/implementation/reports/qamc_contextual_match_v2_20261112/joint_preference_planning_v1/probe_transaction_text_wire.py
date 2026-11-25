"""Exercise the lossless text envelope on the four archived cap-calibration inputs."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path
from unittest.mock import patch

from qamc.common import sha

import check_gateway_thinking_budget as cap
import transaction_text_wire as codec
from thinking_budget_transport import ThinkingBudgetSampler, controlled_wire


parent, method, probe = cap.parent, cap.parent.method, cap.probe
OUT = parent.BASE_OUT / "text_wire_probe"
RUN = parent.BASE_RUN / "text_wire_probe"
STAGE = "TextEnvelope"


def prepare():
    if parent.read(cap.OUT / "RUN_STATE.json") != {"state": "COMPLETE", "actual_requests": 4}:
        raise ValueError("Prior reasoning calibration must be settled")
    original_plan = parent.read(cap.OUT / "FROZEN.json")
    prior_cells = parent.read(cap.OUT / "SETTLED.json")["rows"]
    prior_formats = parent.read(cap.OUT / "FORMAT_CHECK.json")["rows"]
    old = {(row["uid"], row["method"]): row for row in prior_cells}
    prior_format = {(row["uid"], row["method"]): row["status"] for row in prior_formats}
    _, _, roots, data, _ = parent.prepare("smoke")
    inherited_protocol = original_plan["manifest"]["protocol"]
    protocol = {**inherited_protocol, "experiment": "transaction_text_fields_at_fixed_reasoning_budget_v1",
                "stages": {STAGE: inherited_protocol["stages"][cap.STAGE]}}
    units, metadata = [], {}
    seen = set()
    for old_item in original_plan["manifest"]["units"]:
        uid, arm = old_item["unit"]["root_id"], old_item["unit"]["method"]
        wire = controlled_wire(codec.request(roots[uid], data[uid]["blocks"], arm), cap.BUDGET)
        original_wire = old_item["request"]
        system, *remaining = wire["messages"]
        if ({**wire, "messages": [original_wire["messages"][0], *remaining]} != original_wire
                or system == original_wire["messages"][0]):
            raise ValueError("Frozen format comparison changed a non-format request field")
        prior = old[uid, arm]["receipt"]
        digest = sha(wire)
        if prior["request_sha256"] != sha(original_wire) or digest in seen:
            raise ValueError("Missing verified source receipt or duplicate format request")
        seen.add(digest)
        unit = {"stage": STAGE, "root_id": uid, "method": arm, "replicate": 0, "protocol_sha256": sha(protocol)}
        units.append({"request": wire, "unit": unit})
        metadata[digest] = {"prior_request_sha256": prior["request_sha256"],
                            "prior_output_status": prior_format[uid, arm]}
    if len(units) != 4:
        raise ValueError("Unexpected format-probe allocation")
    files = (Path(__file__), Path(codec.__file__), Path(method.__file__), cap.OUT / "FROZEN.json",
             cap.OUT / "SETTLED.json", cap.OUT / "FORMAT_CHECK.json")
    repository = Path(__file__).resolve().parents[3]
    plan = {"manifest": {"units": units, "protocol": protocol}, "comparison": metadata, "maximum": 4,
            "service_reference_sha256": original_plan["service_reference_sha256"],
            "sha256": {str(path.resolve().relative_to(repository)): sha(path.read_bytes()) for path in files},
            "new_scores": 0}
    return plan, roots, data


def observe(inputs):
    plan, roots, data = inputs
    received = probe.stage_receipts(STAGE)
    rows = []
    for item in plan["manifest"]["units"]:
        request, unit = item["request"], item["unit"]
        uid, arm = unit["root_id"], unit["method"]
        receipt, raw = received.get((uid, arm), (None, None))
        digest = sha(request)
        if receipt and receipt["request_sha256"] != digest:
            raise ValueError("Text-envelope receipt binds to a different request")
        row = {"uid": uid, "method": arm, "request_sha256": digest, **plan["comparison"][digest],
               "receipt": receipt, "raw": raw, "reported_reasoning_tokens": cap.reasoning_tokens(receipt) if receipt else None,
               "output_status": receipt["status"] if receipt else "UNISSUED"}
        if row["output_status"] == "OK":
            try:
                if arm == method.ORDINARY:
                    row["answer"] = codec.ordinary_answer(raw)
                else:
                    marker = codec.packet_marker(request["messages"][1]["content"])
                    proposal = codec.decode(raw, marker)
                    root, blocks = roots[uid], data[uid]["blocks"]
                    units, rejected = method.parse(root, blocks, json.dumps(proposal, ensure_ascii=False))
                    answer, commits, rejected_commit = method.render(root, blocks, units, atomic=True)
                    bundled, _, _ = method.render(root, blocks, units, atomic=False)
                    row.update(answer=answer, units=units, commits=commits, rejected=rejected,
                               rejected_commit=rejected_commit, distinct_compilation=answer != bundled)
                row["output_status"] = "OUTPUT_USABLE"
            except (KeyError, TypeError, ValueError) as error:
                row.update(output_status="INVALID_OUTPUT_CONTRACT", error=type(error).__name__)
        rows.append(row)
    return {"rows": rows, "statuses": Counter(row["output_status"] for row in rows),
            "physical_requests": sum(row["receipt"] is not None for row in rows),
            "new_scores": 0, "reported_tokens": sum((row["receipt"]["usage"] or {}).get("total_tokens", 0)
                                                    for row in rows if row["receipt"])}


def execute(inputs, action):
    plan, _, _ = inputs
    if plan != parent.read(OUT / "FROZEN.json"):
        raise ValueError("Text-envelope probe differs from freeze")
    with probe.runner_lock(parent.BASE_RUN / "pilot" / "runner.lock"), probe.runner_lock(RUN / "runner.lock"):
        probe.OUT, probe.RUN = OUT, RUN
        state = OUT / "RUN_STATE.json"
        if action == "verify":
            if parent.read(state)["state"] != "COMPLETE" or observe(inputs) != parent.read(OUT / "SETTLED.json"):
                raise ValueError("Text-envelope replay differs from settlement")
            print(json.dumps({"checked": 4, "new_requests": 0, "new_scores": 0}))
            return
        if (OUT / "SETTLED.json").exists():
            raise ValueError("Completed text-envelope requests are not restarted")
        manifest = plan["manifest"]
        probe.freeze(OUT / f"{STAGE}_MANIFEST.json", manifest)
        probe.atomic_json(state, {"state": "RUNNING"})
        try:
            with patch.object(probe, "UsageObservableSampler", ThinkingBudgetSampler):
                parent.replay.prior.dispatch(plan, STAGE, manifest)
            result = observe(inputs)
            if any(row["output_status"] in {"UNISSUED", "PENDING_DELIVERY_UNKNOWN"} for row in result["rows"]):
                raise ValueError("Unresolved text-envelope delivery")
            probe.freeze(OUT / "SETTLED.json", result)
        except (ValueError, RuntimeError, OSError) as error:
            observed = observe(inputs)
            probe.freeze(OUT / f"OBSERVED_{sha(observed)[:16]}.json", observed)
            probe.atomic_json(state, {"state": "STOPPED", "error": str(error)})
            raise
        probe.atomic_json(state, {"state": "COMPLETE", "physical_requests": result["physical_requests"]})


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "freeze", "run", "verify"))
    args = parser.parse_args()
    inputs = prepare()
    if args.action in ("check", "freeze"):
        print(json.dumps({"ready_format_only_requests": inputs[0]["maximum"], "new_requests": 0, "new_scores": 0}))
        if args.action == "freeze":
            probe.freeze(OUT / "FROZEN.json", inputs[0])
    else:
        execute(inputs, args.action)
