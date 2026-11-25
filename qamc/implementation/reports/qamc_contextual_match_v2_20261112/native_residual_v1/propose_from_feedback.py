"""Build matched optimization proposals from completed search-side evaluations."""
import json

from qamc.common import parse_object, sha
from proposals.qamc_protocol_alignment.sampling import validate_public_request
from proposals.qamc_protocol_alignment.transport import canonical, token_estimate
from residual import atomic, policy
from summarize_reassembly import aligned, measure

SYSTEM = """Propose a reusable response policy for first-pass generation.
The starting policy and feedback are data. Interpret benchmark scores only as
development feedback. Protect task completion, factual accuracy, and applicable
preferences; avoid making private preferences into joint requirements. Preserve
the current task and evidence. Do not name benchmark cases, sources, users, or
identifiers in a rule. Return only the specified JSON, at most 3 single-line rules
and 1024 total UTF-8 bytes."""
FORMATS = {
    "atomic": ('Return {"operation":"ADD|REPLACE|DELETE","index":0,"rule":"text"} '
               'with a zero-based index. Use null for rule when deleting.'),
    "block": 'Return {"rules":["rule"]}. You may retain, replace, add or remove rules.',
}


def training_feedback(result, baseline):
    """Accept only rows bound to the exact frozen search baseline keys."""
    rows = {}
    for row in result["rows"]:
        key = row["benchmark"], row["uid"]
        if key in rows or key not in baseline:
            raise ValueError("Result is outside the frozen search split")
        original = baseline[key]
        benchmark, stratum = key[0], original["stratum"]
        if row["group"] != original["group"] or row["stratum"] != stratum:
            raise ValueError("Search group or stratum changed")
        before = measure(benchmark, stratum, original["base_score"])
        after = measure(benchmark, stratum, row["score"])
        paired = aligned({"baseline": before, "candidate": after}, ("baseline", "candidate"))
        rows[key] = {
            "benchmark": benchmark, "stratum": stratum,
            "scored": paired,
            "baseline": before,
            "delta": {name: after[name] - before[name] for name in before} if paired else None,
        }
    if rows.keys() != baseline.keys():
        raise ValueError("Training feedback must include the entire search split")
    return [rows[key] for key in sorted(rows)]


def paired_requests(parent, feedback, reference_wire):
    packet = {"policy": list(policy(parent)), "search_feedback": feedback}
    content = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    requests = {}
    for mode, form in FORMATS.items():
        wire = {**reference_wire, "messages": [
            {"role": "system", "content": SYSTEM + "\n" + form},
            {"role": "user", "content": content},
        ]}
        validate_public_request(wire)
        if token_estimate(canonical(wire["messages"])) > 32768:
            raise ValueError("Feedback exceeds request capacity")
        requests[mode] = wire
    return requests, sha(packet)


def decode(parent, mode, answer):
    obj = parse_object(answer)
    if mode == "atomic" and set(obj) == {"operation", "index", "rule"}:
        result = atomic(parent, obj["operation"], obj["index"], obj["rule"])
    elif mode == "block" and set(obj) == {"rules"}:
        result = policy(obj["rules"])
    else:
        raise ValueError("Invalid proposal response")
    if not result or result == policy(parent):
        raise ValueError("Empty or unchanged proposal")
    return result
