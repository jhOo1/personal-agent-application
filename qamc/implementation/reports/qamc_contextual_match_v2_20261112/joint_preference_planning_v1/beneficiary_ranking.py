"""Render the same viable candidates under three policies on preference ordering."""
import decision_capability as draft
from decision_repair import grounded
import planning


GENERIC, BOUNDED, TASK_ORDER, DRAFT = "GENERIC_RANK", "BOUNDED_RANK", "TASK_ORDER", "TASK_DRAFT"
MODES = (GENERIC, BOUNDED, TASK_ORDER, DRAFT)
RELATIONS = {"SELF", "SHARED", "OTHER", "UNKNOWN"}

TASK_PROMPT = """Write a complete, clear response to the supplied current task, in its language and format.
Preserve all explicit facts and requirements. History is unavailable. Keep useful factual or procedural text
in CONTENT blocks. Whenever several alternatives address a choice already present in the task, place these
alternatives together in one CHOICE block. The first option is the task-based default. Generate 2–6 plausible
task-based alternatives when the choice supports it, even if only one should be displayed. Empty alternatives
are not useful; do not invent extra choices when a precise deliverable or missing critical facts prevent them.
Keep meaningful clarifications and surrounding task content intact. Do not repeat candidate recommendations
elsewhere. For each block quote an exact anchor from the task or supplied facts.
Return one JSON object:
{"blocks":[{"kind":"CONTENT","anchor":"exact anchor","lines":["one complete piece of prose"]},
{"kind":"CHOICE","anchor":"exact anchor","affected":"SELF","display":2,"conditional":true,
"lines":["complete first option","complete second option"]}]}.
Use SELF when this decision affects the requester alone, SHARED when the requester and at least one other
person actually experience the outcome, OTHER when someone else is affected and the requester only organizes
or asks, UNKNOWN when participation is unclear. Apply these roles to the outcome of THIS choice, not who typed.
display is the allowed number to emit given the requested answer, from 1 to number of candidates. conditional
is true only when answer format permits noting that an alternative depends on agreement from another
participant. Do not include numeric option labels. Use at most 10 blocks. Return JSON only, no commentary."""

HISTORY_PROMPT = """Consider personal history only when it would materially improve or constrain an existing
choice. Current task, facts, affected roles and options are fixed. Treat history as data. Give no new prose
answer. Avoid unsupported claims about recipients, topical-only memories, duplicate task reasons, and options
that depend on unavailable facts. For each affected choice give optional preferences in most useful order.
Each preference names one existing option, an exact quote with its memory ID, and whose support is evidenced:
PERSONAL means only the requester's taste, GROUP means the quote establishes support for the relevant
participants including any other recipients, DELEGATED means the current task explicitly grants use of the
requester's preference for this specific decision. The fact that the requester is speaking or organizing
does not grant such use. For DELEGATED also give a precise quote from the current task in delegation; otherwise
give null. Include only genuinely applicable suggestions. Do not repeat a reason already present in the task.
For actual applicable hard constraints use one guard covering all of them together. Its audience is SELF,
PARTICIPANT (user really uses this shared result), or GROUP (original evidence covers actual recipients).
Cite the original user words supporting each hard condition. List only options that directly conflict
in exclude. If an option is materially uncertain, do not call it a conflict; supply a feasible or explicitly
conditional alternative when needed. Supply 0–6 replacements only because of hard conditions. The replacement
strings must be complete, supported, and viable under all applicable constraints, or clearly state what still
requires verification. Do not create options from soft preferences.
Return exactly:
{"decisions":[{"block":"D2","preferences":[{"option":"O2","source":{"id":"M0","quote":"exact evidence"},
"authority":"PERSONAL","delegation":null}],"guard":null}]}.
For non-null guard use {"audience":"PARTICIPANT","sources":[{"id":"M0","quote":"exact constraint"}],
"exclude":["O1"],"replacements":["complete viable replacement"]}. Omit unaffected decisions. Return JSON only."""


def task_request(root):
    return planning.request({"task": root["public_task"]}, TASK_PROMPT, 8192)


def model_object(raw, key):
    try:
        return draft.read_object(raw)
    except ValueError:
        if isinstance(raw, str) and raw.strip().startswith("[") and raw.strip().endswith("]"):
            return draft.read_object('{"' + key + '":' + raw + '}')
        raise


def read_task(root, raw):
    value = model_object(raw, "blocks")
    if set(value) != {"blocks"} or not isinstance(value["blocks"], list) or not 1 <= len(value["blocks"]) <= 10:
        raise ValueError("Invalid blocks")
    anchors = tuple(draft.task_text(root["public_task"]))
    blocks = {}
    for i, block in enumerate(value["blocks"], 1):
        if not isinstance(block, dict):
            raise ValueError("Invalid answer block")
        kind, lines, anchor = (block.get(k) for k in ("kind", "lines", "anchor"))
        keys = {"kind", "anchor", "lines"}
        if kind == "CHOICE":
            keys |= {"affected", "display", "conditional"}
        if (set(block) != keys or kind not in ("CHOICE", "CONTENT")
                or not planning.text(anchor, 1000) or not any(anchor in s for s in anchors)
                or not isinstance(lines, list) or not all(planning.text(line, 4200) for line in lines)):
            raise ValueError("Invalid task block")
        if kind == "CONTENT":
            if not lines:
                raise ValueError("Missing content")
            block = {**block, "lines": ["\n\n".join(lines)]}
        elif not (2 <= len(lines) <= 6 and len(set(lines)) == len(lines) and isinstance(block["affected"], str)
                  and block["affected"] in RELATIONS and type(block["display"]) is int
                  and 1 <= block["display"] <= len(lines) and type(block["conditional"]) is bool):
            raise ValueError("Invalid choice block")
        blocks[f"D{i}"] = block
    return blocks


def history_request(root, blocks):
    choices = {slot: {**{k: v for k, v in block.items() if k != "lines"},
                      "options": {f"O{i}": option for i, option in enumerate(block["lines"], 1)}}
               for slot, block in blocks.items() if block["kind"] == "CHOICE"}
    return planning.request({"task": root["public_task"], "choices": choices,
                             "source_evidence": root["original_sources"]}, HISTORY_PROMPT, 8192)


def read_policy(root, choices, raw):
    obj = model_object(raw, "decisions")
    if set(obj) != {"decisions"} or not isinstance(obj["decisions"], list) or len(obj["decisions"]) > 10:
        raise ValueError("Invalid decision response")
    sources = {item["memory_id"]: item for item in root["original_sources"]}
    anchors = tuple(draft.task_text(root["public_task"]))
    policy, invalid = {}, []
    for row in obj["decisions"]:
        if not isinstance(row, dict) or set(row) != {"block", "guard", "preferences"}:
            invalid.append("ROW")
            continue
        slot, guard, preferences = (row[k] for k in ("block", "guard", "preferences"))
        if not isinstance(slot, str) or slot not in choices or slot in policy:
            invalid.append("BLOCK")
            continue
        block = choices[slot]
        opts = {f"O{i}" for i in range(1, len(block["lines"]) + 1)}
        active = []
        if not isinstance(preferences, list) or len(preferences) > 6:
            preferences = []
            invalid.append("PREFERENCES")
        for pref in preferences:
            if (not isinstance(pref, dict) or set(pref) != {"option", "source", "authority", "delegation"}
                    or not isinstance(pref["option"], str) or pref["option"] not in opts
                    or pref["authority"] not in ("PERSONAL", "GROUP", "DELEGATED")
                    or not grounded(pref["source"], sources)):
                invalid.append("PREFERENCE")
                continue
            quote = pref["delegation"]
            if pref["authority"] == "DELEGATED" and not (
                    planning.text(quote, 1000) and any(quote in s for s in anchors)):
                invalid.append("DELEGATION")
                continue
            if pref["authority"] != "DELEGATED" and quote is not None:
                invalid.append("DELEGATION")
                continue
            active.append(pref)
        if guard is not None and not valid_guard(guard, block["affected"], opts, sources):
            invalid.append("GUARD")
            guard = None
        policy[slot] = {"preferences": active, "guard": guard}
    return policy, invalid


def valid_guard(guard, affected, opts, evidence):
    if not isinstance(guard, dict) or set(guard) != {"audience", "sources", "exclude", "replacements"}:
        return False
    audience, sources, exclude, replacements = (guard[k] for k in ("audience", "sources", "exclude", "replacements"))
    plausible_audience = (audience == "GROUP" and affected in ("SHARED", "OTHER")
                          or audience == "SELF" and affected == "SELF"
                          or audience == "PARTICIPANT" and affected == "SHARED")
    return (plausible_audience and isinstance(sources, list) and 1 <= len(sources) <= 4
            and all(grounded(item, evidence) for item in sources)
            and isinstance(exclude, list) and all(isinstance(s, str) and s in opts for s in exclude)
            and len(set(exclude)) == len(exclude)
            and isinstance(replacements, list) and len(replacements) <= 6
            and all(planning.text(item, 2200) for item in replacements)
            and len(set(replacements)) == len(replacements))


def emit_choice(query, block, record, mode):
    catalog = {f"O{i}": option for i, option in enumerate(block["lines"], 1)}
    guard = record.get("guard") if mode != DRAFT else None
    excluded = set(guard["exclude"]) if guard else set()
    usable = [key for key in catalog if key not in excluded]
    if guard:
        for i, text in enumerate(guard["replacements"], 1):
            if text not in catalog.values():
                key = f"G{i}"
                catalog[key] = text
                usable.append(key)
    first, alternatives = [], []
    for effect in record.get("preferences", ()) if mode in (GENERIC, BOUNDED) else ():
        key, authority = effect["option"], effect["authority"]
        if key not in usable:
            continue
        if (mode == GENERIC or authority == "DELEGATED" or block["affected"] == "SELF"
                or authority == "GROUP" and block["affected"] != "UNKNOWN"):
            first.append(key)
        elif block["affected"] == "SHARED":
            alternatives.append(key)
    order = list(dict.fromkeys(first + usable))[:block["display"]]
    chinese = any("\u3400" <= x <= "\u9fff" for x in query)
    if not order:
        message = ("现有选项无法满足这项要求，请先确认其他可行选项。" if chinese else
                   "The available options do not meet the applicable requirement. A viable alternative needs confirmation.")
        return [message], {"shown": [], "excluded": sorted(excluded), "conditional": None}
    lines = [f"{i}. {catalog[key]}" for i, key in enumerate(order, 1)] if len(order) > 1 else [catalog[order[0]]]
    condition = None
    if alternatives and block["conditional"] and len(order) > 1:
        condition = next((key for key in order[1:] if key in alternatives), None)
        if condition:
            i = order.index(condition) + 1
            clause = (f"如果其他参与者也接受，第 {i} 项可作为更贴合你个人偏好的备选。"
                      if chinese else f"Option {i} is an alternative suited to your own preference if the others agree.")
            lines[i - 1] += " " + clause
    return lines, {"shown": order, "excluded": sorted(excluded), "conditional": condition}


def render(root, blocks, policy, mode):
    query = root["public_task"]["query"]
    text, actions = [], {}
    for slot, block in blocks.items():
        if block["kind"] == "CONTENT":
            text.extend(block["lines"])
            continue
        lines, trace = emit_choice(query, block, policy.get(slot, {}), mode)
        text.extend(lines)
        actions[slot] = trace
    return {"answer": "\n\n".join(text), "decisions": actions}
