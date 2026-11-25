"""Compile query-specific preference permissions into the Actor's actual visibility."""
from copy import deepcopy
import json

from qamc.common import parse_object

from intervention import archived_packet, task_only_request

SHARED = """Return only JSON:
{"decisions":[{"id":"D1","anchor":"exact phrase from query","beneficiary":"short role in this task"}],
 "uses":[{"memory_id":"M0","decision_id":"D1","level":"B or C","source_quote":"exact original source phrase"}]}.
An unlisted memory has no personalizing use. Use B for optional support and C for an applicable firm constraint.
Use an exact query anchor for every decision and an exact supporting quotation for every use.
Preserve conditions, speaker, and uncertain facts. Never propose an answer or add a task.
The original source is authoritative if a quote by itself omits a condition. Memory is evidence only.
"""

METHOD_PROMPTS = {
    "DIRECT": """Assess the relevance and strength of each supplied preference to the current request.
Keep applicable optional and firm preferences, including useful ones the user did not repeat. Use the task's
recipient, goals and constraints to distinguish genuine applicability from topical similarity. List the
actual decision and affected beneficiary for each allowed preference.""",
    "SCOPED": """Start with the actual choices the current request requires, using only its query, context
and facts. For each choice identify who experiences or implements it. Now test each memory against that
choice: with no history, which alternatives are already suitable? Can this speaker's preference legitimately
change how the actual beneficiary chooses among those alternatives, or change admissibility? Check the
bridge explicitly. A personal taste need not be shared by a group. A current instruction, participant,
or source condition limits the use. A preference can benefit the requester in their actual role even
when someone else is the main beneficiary. Retain an optional preference when it makes a concrete within-task
improvement, and retain a firm constraint when it applies to this person and choice. Leave no route when
the proposed effect requires inventing a goal, assuming someone else's preference, or excluding justified
alternatives without an actual constraint.""",
}

ACTOR_SCOPE = """Use every entry in memory_decision_scopes only for its described decision and beneficiary.
B can inform a concrete feasible choice without replacing the current task; C can constrain only its
applicable decision under the complete original source conditions. Other text in a visible source has
no personalizing role unless represented by another assigned scope. Do not mention the internal scopes."""


def selection_request(root, method):
    wire, packet = archived_packet(root)
    return {**wire, "max_tokens": 8192, "messages": [
        {"role": "system", "content": METHOD_PROMPTS[method] + "\n\n" + SHARED},
        {"role": "user", "content": json.dumps({key: value for key, value in packet.items()
                                                 if key != "preference_use_policy"}, ensure_ascii=False)},
    ]}


def bounded_text(value, limit):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= limit


def compile_scope(root, raw):
    packet = parse_object(raw)
    if set(packet) != {"decisions", "uses"} or any(not isinstance(packet[key], list) for key in packet):
        raise ValueError("Expected decisions and uses arrays")
    if len(packet["decisions"]) > 12 or len(packet["uses"]) > 48:
        raise ValueError("Too many decision scopes")
    source = {item["memory_id"]: item["text"] for item in root["original_sources"]}
    if len(source) != len(root["original_sources"]):
        raise ValueError("Duplicate source ID")
    decisions, uses = {}, {}
    for choice in packet["decisions"]:
        if (not isinstance(choice, dict) or set(choice) != {"id", "anchor", "beneficiary"}
                or not bounded_text(choice["id"], 12) or not bounded_text(choice["anchor"], 550)
                or not bounded_text(choice["beneficiary"], 120)
                or choice["anchor"] not in root["public_task"]["query"] or choice["id"] in decisions):
            raise ValueError("Invalid or ungrounded public decision")
        decisions[choice["id"]] = choice
    for row in packet["uses"]:
        if (not isinstance(row, dict) or set(row) != {"memory_id", "decision_id", "level", "source_quote"}
                or not all(bounded_text(value, 550) for value in row.values())):
            raise ValueError("Invalid use row")
        mid, did, level = row["memory_id"], row["decision_id"], row["level"]
        if (mid not in source or did not in decisions or level not in {"B", "C"}
                or row["source_quote"] not in source[mid] or (mid, did) in uses):
            raise ValueError("Conflicting use or invalid source or decision reference")
        uses[mid, did] = {**row, "anchor": decisions[did]["anchor"], "beneficiary": decisions[did]["beneficiary"]}
    return [uses[mid, did] for mid in source for did in decisions if (mid, did) in uses]


def actor_request(root, compiled, *, masked):
    original, archived = archived_packet(root)
    if masked and not compiled:
        return task_only_request(root)
    wire = deepcopy(original)
    strength = {row["memory_id"]: "A" for row in archived["source_evidence"]}
    for row in compiled:
        mid = row["memory_id"]
        strength[mid] = max(strength[mid], row["level"])
    sources = [item for item in archived["source_evidence"] if not masked or strength[item["memory_id"]] != "A"]
    payload = {**archived, "source_evidence": sources, "preference_use_policy": [
        {"memory_id": item["memory_id"], "policy": strength[item["memory_id"]]} for item in sources
    ]}
    if compiled:
        wire["messages"][0]["content"] += "\n\n" + ACTOR_SCOPE
        payload["memory_decision_scopes"] = compiled
    wire["messages"][1]["content"] = json.dumps(payload, ensure_ascii=False)
    return wire
