"""Recover complete text-wire responses with optional empty fields or an EOF terminator."""
import json
import re

import open_condition_text_wire as wire


def recover(task, conditions, raw, receipt):
    if receipt.get("status") != "OK" or receipt.get("finish_reason") != "stop" or not receipt.get("received_done"):
        raise ValueError("Unconfirmed delivery cannot be reconstructed")
    prefix = wire.marker(task, conditions)
    if not isinstance(raw, str):
        raise ValueError("Missing response")
    start = re.search(r"^" + re.escape(prefix) + r" T[1-9][0-9]*\n", raw, re.MULTILINE)
    if start is None:
        raise ValueError("No anchored text sections")
    try:
        header = json.loads(raw[:start.start()])
    except json.JSONDecodeError as exc:
        raise ValueError("Unreadable metadata stays invalid") from exc
    if not isinstance(header, dict) or set(header) != {"items"} or not isinstance(header["items"], list):
        raise ValueError("Missing original metadata envelope")
    rows = []
    for item in header["items"]:
        if not isinstance(item, dict) or "text" not in item or set(item) - {"text", "satisfies", "verify"}:
            raise ValueError("Unknown metadata shape")
        rows.append({"satisfies": [], "verify": [], **item})
    body = raw[start.start():].rstrip("\n")
    if not body.endswith("\n" + prefix + " END"):
        body = body.removesuffix("\n" + prefix) + "\n" + prefix + " END"
    reconstructed = json.dumps({"items": rows}, ensure_ascii=False) + "\n" + body
    normalized = wire.decode(reconstructed, prefix)
    if conditions:
        return wire.render_items(task, conditions, normalized)

    # A model can copy sample IDs when the task has no admitted conditions.
    # Preserve the already delivered prose and checks, bound support to nothing.
    referenced = set()
    for row in normalized["items"]:
        if not isinstance(row["satisfies"], list):
            raise ValueError("Ambiguous unsupported goal references")
        for key in (*row["satisfies"], *(item["goal"] for item in row["verify"])):
            if not isinstance(key, str) or not re.fullmatch(r"G[1-9][0-9]*", key):
                raise ValueError("Ambiguous unsupported goal reference")
            referenced.add(key)
    if not referenced:
        return wire.render_items(task, conditions, normalized)
    formatting_ids = [{"id": key, "strength": "OPTIONAL"} for key in sorted(referenced)]
    rendered = wire.render_items(task, formatting_ids, normalized)
    return {**rendered, "claimed_supported": [], "action_linked_verification": [],
            "action_linked_verification_for_optional": [], "unbound_goal_references": sorted(referenced)}
