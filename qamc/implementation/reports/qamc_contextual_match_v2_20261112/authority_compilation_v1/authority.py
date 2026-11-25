"""Immutable public passages with source-backed personal decisions in allocated positions."""
from copy import deepcopy
import json
import re

from proposals.qamc_protocol_alignment.sampling import validate_public_request

PUBLIC = """Plan a complete answer to the current task, based on the task and current facts alone.
Write the self-contained passages that should be independent of personal history. Leave a decision slot
where a real participant's preferences or constraints could change what to choose or propose. Keep all
explicit current requirements. Do not assume a participant or allocate a slot for a task the user did
not request. Do not preselect a personal choice in fixed prose. Give each slot a neutral fallback that
answers that part of the task without guessing an absent preference. Each passage is copied to the
answer, so do not include process commentary, placeholders, or instructions to a later model.

Return JSON with one field, "blocks", an ordered list of objects of either shape:
{"id":"P1","kind":"fixed","text":"standalone public passage"}
{"id":"D1","kind":"decision","target":"participant or audience","goal":"one existing choice","text":"neutral fallback"}.
Use unique IDs with an English letter followed by digits and preserve the intended document order."""

SHARED = """Answer the original current task. Preserve the explicit requirements and current facts.
Treat historical sources as evidence about the person or context they describe. Use a supported preference
where it adds concrete value to a choice for the relevant participant. A personal belief is not independent
support for a claim about the world, and one person's preference is not a requirement for everyone.
Keep the complete requested deliverable. Do not report internal stages or reveal source identifiers."""

GENERIC = SHARED + """
Review the public draft and its decision slots, and use the complete historical evidence where applicable.
Fix any material error or gap and return the best complete natural-language answer."""

PERSONAL = SHARED + """
The fixed public passages will be copied exactly. Supply only replacements for existing decision slots
and optional formatting operations. Leave a slot unchanged when there is no supported improvement.
A replacement is the actual proposed choice or action for the stated target. Do not add background
claims, state someone else's preferences, assert an unsupported fact, or restate a fixed passage.
Return only JSON:
{"decisions":[{"id":"D1","text":"one paragraph with the proposed decision",
"source_id":"M1","quote":"exact supporting excerpt from the source"}],
"emphasis":[{"id":"P1","text":"exact single-line phrase to emphasize",
"source_id":"M2","quote":"exact supporting excerpt about formatting"}]}.
Return empty lists if there is no justified personalization. Do not add another type of operation."""

BLOCK_ID = re.compile(r"[A-Za-z][0-9]+")
WORD = re.compile(r"\w")


def wire(base, system, payload):
    request = {**base, "messages": [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]}
    validate_public_request(request)
    return request


def public_wire(root):
    task = root["public_task"]
    object_fields(task, {"query", "current_context", "facts"})
    return wire(root["archived_actor_request"], PUBLIC, {"task": task})


def personal_wires(root, public):
    payload = {"task": root["public_task"], "public_draft": public,
               "source_evidence": root["original_sources"]}
    base = root["archived_actor_request"]
    return {"GENERIC": wire(base, GENERIC, payload), "AUTHORITY": wire(base, PERSONAL, payload)}


def unique_fields(pairs):
    fields = dict(pairs)
    if len(fields) != len(pairs):
        raise ValueError("Duplicate JSON field")
    return fields


def object_fields(value, fields):
    if not isinstance(value, dict) or value.keys() != fields:
        raise ValueError("Unexpected fields")
    return value


def nonempty(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Empty text")
    return value


def compile_public(raw):
    value = object_fields(json.loads(raw, object_pairs_hook=unique_fields), {"blocks"})
    blocks = value["blocks"]
    if not isinstance(blocks, list) or not blocks:
        raise ValueError("Missing blocks")
    seen = set()
    for block in blocks:
        if not isinstance(block, dict) or block.get("kind") not in ("fixed", "decision"):
            raise ValueError("Unknown block type")
        fields = {"id", "kind", "text"}
        if block["kind"] == "decision":
            fields |= {"target", "goal"}
        object_fields(block, fields)
        for name in fields:
            nonempty(block[name])
        if not BLOCK_ID.fullmatch(block["id"]) or block["id"] in seen:
            raise ValueError("Invalid or duplicate block identifier")
        seen.add(block["id"])
    if not any(block["kind"] == "fixed" for block in blocks):
        raise ValueError("No fixed public passage")
    return value


def compile_answer(task, public, raw, memories):
    value = object_fields(json.loads(raw, object_pairs_hook=unique_fields), {"decisions", "emphasis"})
    rendered = deepcopy(public["blocks"])
    by_id = {block["id"]: block for block in rendered}
    sources = {item["memory_id"]: item["text"] for item in memories}
    if len(sources) != len(memories):
        raise ValueError("Duplicate memory identifier")
    for kind in ("decisions", "emphasis"):
        operations = value[kind]
        if not isinstance(operations, list):
            raise ValueError("Operations must be a list")
        seen = set()
        for operation in operations:
            object_fields(operation, {"id", "text", "source_id", "quote"})
            for field in operation.values():
                nonempty(field)
            uid = operation["id"]
            if uid in seen or uid not in by_id:
                raise ValueError("Missing or repeated operation target")
            seen.add(uid)
            quote = operation["quote"]
            if not WORD.search(quote) or quote not in sources.get(operation["source_id"], ""):
                raise ValueError("Missing original evidence")
            block = by_id[uid]
            text = operation["text"]
            if len(text.splitlines()) != 1 or text != text.strip():
                raise ValueError("Operation must target a single paragraph or phrase")
            if kind == "decisions":
                if block["kind"] != "decision":
                    raise ValueError("Memory cannot replace fixed public passages")
                block["text"] = text
            else:
                current = str(task.get("query", "")) + "\n" + str(task.get("current_context", ""))
                if re.search(r"\b(?:plain[- ]text|no (?:markdown|formatting)|do not use markdown)\b", current, re.I):
                    raise ValueError("Current task forbids emphasis")
                if "*" in text or block["text"].count(text) != 1:
                    raise ValueError("Emphasis must select existing text exactly once")
                block["text"] = block["text"].replace(text, f"**{text}**", 1)
    return "\n\n".join(block["text"] for block in rendered)
