"""Preserve free answer text outside the JSON plan metadata."""
import json
import re

from qamc.common import canonical

import open_condition_planning as previous
from transaction_text_wire import packet_marker


ARMS, GENERIC, OPEN_FIRST, BUDGET = previous.ARMS, previous.GENERIC, previous.OPEN_FIRST, previous.BUDGET
goals, goal_request, user_source = previous.goals, previous.goal_request, previous.user_source


TEXT_CONTRACT = """Only the ordered plan items form the final answer. Return exactly one
compact JSON object containing metadata and no user-facing text values. Use one to
twelve items. In each item supply a text reference for the user-facing section.
A satisfies entry requires an actual supporting action or design in this section.
For an essential unknown property, link a specific check to its named goal and
to this section. A property needing verification here is not yet established.

Example metadata, using the goal IDs that actually exist in this task:
{"items":[{"text":"T1","satisfies":["G1"],"verify":[{"goal":"G2","check":"T2"}]}]}
Immediately after the metadata, put each referenced value on its own block.
Start a block with the marker, one space and the reference, alone on its own line.
Write its prose normally on following lines, including normal quotation marks,
backslashes or line breaks. No JSON escaping is required inside the blocks.
Finish on a separate line with the marker, one space and END. Do not emit units
that lack text or use a reference outside its data. Do not show goal IDs in the prose."""


def marker(task, conditions):
    return packet_marker(canonical({"task": task, "conditions": conditions}))


def actor_request(task, sources, conditions, arm):
    wire = previous.actor_request(task, sources, conditions, arm)
    prefix = marker(task, conditions)
    if prefix in wire["messages"][1]["content"]:
        raise ValueError("Response marker collides with the public input packet")
    semantic = previous.COMMON_PROMPT.split("\n\n", 1)[0]
    wire["messages"][0]["content"] = f"{semantic}\n\n{TEXT_CONTRACT}\nYour marker is {prefix}.\n\n{previous.INSTRUCTION[arm]}"
    return wire


def resolve(metadata, get_text):
    if set(metadata) != {"items"} or not isinstance(metadata["items"], list) or not 1 <= len(metadata["items"]) <= 12:
        raise ValueError("Invalid text-plan envelope")
    output = []
    for item in metadata["items"]:
        if not isinstance(item, dict) or set(item) != {"text", "satisfies", "verify"} or not isinstance(item["verify"], list):
            raise ValueError("Missing text-plan item fields")
        checks = []
        for check in item["verify"]:
            if not isinstance(check, dict) or set(check) != {"goal", "check"}:
                raise ValueError("Missing text-plan verification fields")
            checks.append({"goal": check["goal"], "check": get_text(check["check"])})
        output.append({**item, "text": get_text(item["text"]), "verify": checks})
    return {"items": output}


def decode(raw, prefix):
    if not isinstance(raw, str):
        raise ValueError("Missing text-plan response")
    pattern = re.compile(r"^" + re.escape(prefix) + r" (T[1-9][0-9]*|END)(?:\n|\Z)", re.MULTILINE)
    markers = list(pattern.finditer(raw))
    if not markers or markers[-1][1] != "END" or raw[markers[-1].end():].strip():
        raise ValueError("Missing or misplaced end marker")
    fields = {}
    for start, end in zip(markers, markers[1:]):
        ref = start[1]
        value = raw[start.end():end.start()].removesuffix("\n")
        if ref == "END" or ref in fields or prefix in value:
            raise ValueError("Duplicate or ambiguous text block")
        fields[ref] = value
    used = set()

    def get_text(ref):
        if not isinstance(ref, str) or ref not in fields:
            raise ValueError("Missing text reference")
        used.add(ref)
        return fields[ref]

    try:
        metadata = json.loads(raw[:markers[0].start()])
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid metadata JSON") from exc
    if not isinstance(metadata, dict):
        raise ValueError("Expected a metadata object")
    parsed = resolve(metadata, get_text)
    if used != fields.keys():
        raise ValueError("Unreferenced text block")
    return parsed


def render_items(task, conditions, data):
    required = {goal["id"] for goal in conditions if goal["strength"] == "REQUIRED"}
    by_id = {g["id"] for g in conditions}
    normalized = []
    uncertain_overlap = 0
    for item in data["items"]:
        checks, satisfies = item["verify"], item["satisfies"]
        if not isinstance(satisfies, list) or not all(isinstance(key, str) and key in by_id for key in satisfies):
            raise ValueError("Invalid declared support")
        if not all(isinstance(check["goal"], str) and check["goal"] in by_id for check in checks):
            raise ValueError("Unknown verification goal")
        verification = {check["goal"] for check in checks}
        uncertain_overlap += len(verification & set(satisfies))
        normalized.append({**item, "satisfies": [key for key in satisfies if key not in verification]})
    # The previous renderer limits checks to required IDs. Treat optional IDs as
    # linkable only for rendering, then restore true strengths in the audit.
    linkable = [{**g, "strength": "REQUIRED"} for g in conditions]
    output = previous.render(task, linkable, json.dumps({"items": normalized}, ensure_ascii=False))
    output["required"] = sorted(required)
    output["open_without_action"] = sorted(required & set(output["open_without_action"]))
    output["action_linked_verification_for_optional"] = sorted(
        set(output["action_linked_verification"]) - required)
    output["verification_over_support_count"] = uncertain_overlap
    return output


def render(task, conditions, raw):
    return render_items(task, conditions, decode(raw, marker(task, conditions)))
