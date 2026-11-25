"""Remove unbound RPEval memory sources and their policy rows."""
import json

from proposals.qamc_protocol_alignment.sampling import validate_public_request
from scope_contract import render


def restricted_wire(original, guidance, sources):
    ids = [item["memory_id"] for item in sources]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate original source ID")
    bindings = {f"M{i}": value for i, value in enumerate(ids)}
    kept = {bindings[item["source"]] for item in guidance["preferences"]}
    wire = render(original, guidance, scoped=True)
    user, = [message for message in wire["messages"] if message["role"] == "user"]
    packet = json.loads(user["content"])
    if packet["source_evidence"] != sources:
        raise ValueError("Unexpected ordering or content of archived evidence")
    policy = packet["preference_use_policy"]
    if any(item["memory_id"] not in ids for item in policy):
        raise ValueError("Unknown memory source in original policy")
    if kept != set(ids):
        packet["source_evidence"] = [item for item in sources if item["memory_id"] in kept]
        packet["preference_use_policy"] = [item for item in policy if item["memory_id"] in kept]
        user["content"] = json.dumps(packet, ensure_ascii=False)
    validate_public_request(wire)
    return wire, len(ids) - len(kept)
