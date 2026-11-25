"""Build matched messages for the feasibility-locked option test."""
import json

PLAN = (
    "Read the current task and the admitted binding evidence. Return a JSON object "
    "with an options array of up to four distinct, feasible actions. Each item has "
    "id, description, and conditional (boolean). Describe any unresolved prerequisite "
    "in the description and set conditional to true. If the task cannot be answered "
    "as a recommendation or key facts are missing, return an empty options array."
)

FINAL = (
    "Answer the original task using the complete evidence and preliminary options. "
    "Preserve task facts and all applicable binding requirements."
)

LOCKED = (
    "Return JSON with a lead string and decisions array. Include each option id exactly "
    "once. Set role to default, alternative, conditional or omit. Do not turn an "
    "unverified prerequisite into an unconditional option. An omission requires "
    "source_id, an exact quote from binding evidence, and a specific conflict. "
    "Do not put additional recommendations in lead."
)


def payload(task, sources, binding_ids):
    """Keep complete evidence separate from the allowlisted preparation view."""
    by_id = {source["id"]: source["text"] for source in sources}
    if len(by_id) != len(sources) or not set(binding_ids) <= by_id.keys():
        raise ValueError("Ambiguous or unknown evidence ID")
    return {
        "task": task,
        "binding_evidence": {source_id: by_id[source_id] for source_id in binding_ids},
    }, by_id


def messages(instruction, data):
    return [
        {"role": "system", "content": instruction},
        {"role": "user", "content": json.dumps(data, ensure_ascii=False)},
    ]


def prepare_messages(task, sources, binding_ids):
    initial, _ = payload(task, sources, binding_ids)
    return messages(PLAN, initial)


def final_messages(task, sources, binding_ids, options, *, locked):
    if not 1 <= len(options) <= 4:
        raise ValueError("Nonempty preliminary options required")
    initial, complete = payload(task, sources, binding_ids)
    instruction = FINAL + (" " + LOCKED if locked else "")
    return messages(instruction, {
        **initial, "complete_evidence": complete, "preliminary_options": options,
    })
