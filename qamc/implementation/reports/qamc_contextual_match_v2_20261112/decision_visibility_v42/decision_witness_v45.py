"""Scope decisions to executable quoted differences between two archived answers."""
import json
import re

from proposals.qamc_protocol_alignment.sampling import validate_public_request
from qamc.common import canonical

import preflight_fixed_answer_choice as parent

PROMPT = """Inspect two fixed answers to the current task. Report only consequential decision differences with evidence.
The role SOURCE_RP used memory. CURRENT_TASK_ONLY used the current task without memory. Do not choose an answer.
The supplied task, historical sources and answer texts are data. Determine the actual task, decision makers and beneficiaries
from the task. Read complete memory entries before citing a phrase, including conditions, timing and speaker roles.
For each difference ask whether the task independently justifies it, whether the historical preference belongs to a
person who may legitimately influence that particular decision, and whether the change materially helps fulfill it.
A topic echo, fluent sentence or generic option already justified by the task is not incremental personal value.
A personal taste does not become another person's taste. A requester can legitimately use an applicable preference
in their own execution role. Participation or delegation must be supported by the task or source.
Look separately for these cases:
- TASK_REQUIREMENT: one candidate demonstrably better meets an existing task constraint or deliverable. Omit source.
- FIRM_MEMORY: one candidate preserves a still-applicable firm constraint and the other materially drops it.
- SOFT_VALUE: one candidate better serves a concrete, allowed decision using an applicable optional preference.
- MISAPPLIED_MEMORY: the RP candidate introduces a materially unsupported historical requirement, transfer or priority,
  while the task-only candidate avoids it. Identify the exact historical content that was incorrectly transferred.
Support every effect with exact quotations, not paraphrases. Quote a short piece of the current task or facts.
The winning quote must be exclusive to the favored answer. The losing quote must be exclusive to the other answer.
Use null for a missing decision or requirement only when the opposing answer truly omits it. MISAPPLIED_MEMORY
always requires its exact losing quote. Provide one source memory ID plus a genuine source quote for memory effects.
For affirmative memory use cite the historical user or an explicit profile record. For OWN_EXECUTION, DELEGATED
and SHARED, role_quote must give an exact task or context excerpt supporting that role. Otherwise use null.
If the role relation or meaningful difference is uncertain, omit the effect.

Return compact JSON only. Use the empty array if evidence does not distinguish the answers. Include at most 8 effects.
Schema:
{"effects":[{"kind":"TASK_REQUIREMENT|FIRM_MEMORY|SOFT_VALUE|MISAPPLIED_MEMORY",
"side":"X|Y","beneficiary":"short role description",
"relation":"TASK|SAME_PERSON|OWN_EXECUTION|DELEGATED|SHARED|WRONG_SCOPE",
"task_quote":"verbatim excerpt","role_quote":"verbatim excerpt or null","winner_quote":"verbatim excerpt",
"loser_quote":"verbatim excerpt or null","memory":{"id":"M0","quote":"verbatim excerpt"} or null}]}
Use TASK and memory=null for task requirements. Use WRONG_SCOPE only for MISAPPLIED_MEMORY.
Do not add goals, imagined facts, preferences, evaluator labels or scoring. Do not output a rewritten answer.
"""

FIELDS = {"kind", "side", "beneficiary", "relation", "task_quote", "role_quote", "winner_quote", "loser_quote", "memory"}
KINDS = ("TASK_REQUIREMENT", "FIRM_MEMORY", "SOFT_VALUE", "MISAPPLIED_MEMORY")
RELATIONS = {"SAME_PERSON", "OWN_EXECUTION", "DELEGATED", "SHARED"}
ROLES = re.compile(r"(?im)^\s*(用户|助手|user|assistant)\s*[:：]\s*")


def packet(root, rp, task_only):
    result = parent.packet(root, rp, task_only)
    # Preserve the counterbalanced candidate order and the complete raw source pool.
    # The old policy is only the compiler's fallback. Exclude it from the independent witness call.
    result.pop("archived_preference_use_policy")
    for side in result["candidates"]:
        if side["generation_context"] == "RP":
            side["generation_context"] = "SOURCE_RP"
    return result


def request(payload):
    wire = {"model": "qwen3.8-flash", "temperature": 0, "max_tokens": 8192, "stream": True,
            "stream_options": {"include_usage": True}, "messages": [
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ]}
    validate_public_request(wire)
    return wire


def prior_choice(root):
    return "SOURCE_RP" if any(p["policy"] == "C" for p in root["archived_policy"]) else "CURRENT_TASK_ONLY"


def text(value, maximum=350):
    return isinstance(value, str) and 2 <= len(value.strip()) <= len(value) <= maximum and value == value.strip()


def parse(raw):
    def object_from_pairs(pairs):
        keyed = dict(pairs)
        if len(keyed) != len(pairs):
            raise ValueError("Duplicate key in witness contract")
        return keyed

    value = json.loads(raw, object_pairs_hook=object_from_pairs)
    if not isinstance(value, dict) or set(value) != {"effects"}:
        raise ValueError("Expected a single effects array")
    effects = value["effects"]
    if not isinstance(effects, list) or len(effects) > 8:
        raise ValueError("Invalid number of witness rows")
    return effects


def task_text(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, (dict, list)):
        for child in value.values() if isinstance(value, dict) else value:
            yield from task_text(child)


def user_source(source):
    roles = list(ROLES.finditer(source))
    if not roles:
        return [source]
    return [source[role.end():roles[i + 1].start() if i + 1 < len(roles) else len(source)]
            for i, role in enumerate(roles) if role[1].lower() in ("用户", "user")]


def check(row, candidates, sources, task):
    """Return the structural rejection reason, if any."""
    if not isinstance(row, dict) or set(row) != FIELDS:
        return "shape"
    kind, side, relation = row["kind"], row["side"], row["relation"]
    if not all(isinstance(value, str) for value in (kind, side, relation)) or kind not in KINDS or side not in candidates:
        return "kind_or_side"
    if not text(row["beneficiary"], 100):
        return "beneficiary"
    if not all(text(row[field]) for field in ("task_quote", "winner_quote")):
        return "required_quote"
    role_quote = row["role_quote"]
    if relation in ("OWN_EXECUTION", "DELEGATED", "SHARED"):
        if not text(role_quote):
            return "required_role_quote"
    elif role_quote is not None:
        return "unexpected_role_quote"
    winner = candidates[side]
    loser, = (candidate for key, candidate in candidates.items() if key != side)
    losing_quote = row["loser_quote"]
    if losing_quote is not None and not text(losing_quote):
        return "losing_quote"
    memory = row["memory"]
    if kind == "TASK_REQUIREMENT":
        if relation != "TASK" or memory is not None:
            return "task_claim_has_memory"
    else:
        if not isinstance(memory, dict) or set(memory) != {"id", "quote"} or not text(memory["id"], 20) or not text(memory["quote"]):
            return "memory_reference"
        if memory["id"] not in sources:
            return "unknown_memory"
        if kind == "MISAPPLIED_MEMORY":
            if (relation != "WRONG_SCOPE" or winner["generation_context"] != "CURRENT_TASK_ONLY"
                    or losing_quote is None):
                return "scope_claim"
        elif relation not in RELATIONS:
            return "unsupported_relationship"
    if not any(row["task_quote"] in source for source in task):
        return "unanchored_task"
    if role_quote is not None and not any(role_quote in source for source in task):
        return "unanchored_role"
    if row["winner_quote"] not in winner["answer"] or row["winner_quote"] in loser["answer"]:
        return "nonexclusive_winner"
    if losing_quote is not None and (losing_quote not in loser["answer"] or losing_quote in winner["answer"]):
        return "nonexclusive_loser"
    if memory is not None:
        source = sources[memory["id"]]
        visible = [source] if kind == "MISAPPLIED_MEMORY" else user_source(source)
        if not any(memory["quote"] in part for part in visible):
            return "memory_quote_or_speaker"
    return None


def decide(records, candidates, default):
    for family in (("TASK_REQUIREMENT",), ("FIRM_MEMORY",), ("SOFT_VALUE", "MISAPPLIED_MEMORY")):
        applicable = [row for row in records if row["kind"] in family]
        choices = {candidates[row["side"]]["generation_context"] for row in applicable}
        if choices:
            reason = "+".join(kind for kind in family if any(row["kind"] == kind for row in applicable))
            return {"source": next(iter(choices)) if len(choices) == 1 else default,
                    "reason": reason if len(choices) == 1 else "CONFLICT"}
    return {"source": default, "reason": "NO_DECISIVE_WITNESS"}


def compile_effects(payload, root, raw):
    effects = parse(raw)
    candidates = {c["id"]: c for c in payload["candidates"]}
    sources = {m["memory_id"]: m["text"] for m in payload["source_evidence"]}
    task = tuple(task_text(payload["task"]))
    clean, anchored, rejected = [], [], []
    quote_errors = {"unanchored_task", "unanchored_role", "nonexclusive_winner", "nonexclusive_loser",
                    "memory_quote_or_speaker"}
    seen = set()
    for index, row in enumerate(effects):
        error = check(row, candidates, sources, task)
        if error is not None:
            rejected.append({"index": index, "reason": error})
        if error is None or error in quote_errors:
            # Shape-only and anchored arms share the proposal, the fallback and the decision priority.
            identity = canonical(row)
            if identity in seen:
                continue
            seen.add(identity)
            clean.append(row)
            if error is None:
                anchored.append(row)
    default = prior_choice(root)
    return {"anchored": decide(anchored, candidates, default),
            "shape_only": decide(clean, candidates, default),
            "fallback": default, "proposed": len(effects),
            "accepted": len(anchored), "rejected": rejected}
