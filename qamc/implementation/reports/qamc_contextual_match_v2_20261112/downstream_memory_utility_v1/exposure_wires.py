"""Project a frozen Actor request onto original history without editing task facts."""
from copy import deepcopy
import json


def _positions(items, selected):
    positions = list(selected)
    if (any(type(i) is not int or not 0 <= i < len(items) for i in positions)
            or len(set(positions)) != len(positions)):
        raise ValueError("Invalid or repeated original source position")
    return sorted(positions)


def rp_projection(request, selected, proposed_policy=None):
    wire = deepcopy(request)
    system, user = wire["messages"]
    if (system["role"], user["role"]) != ("system", "user"):
        raise ValueError("Unexpected Actor roles")
    body = json.loads(user["content"])
    if set(body) != {"query", "current_context", "facts", "source_evidence", "preference_use_policy"}:
        raise ValueError("Unexpected RP Actor task fields")
    sources = body["source_evidence"]
    ids = [x["memory_id"] for x in sources]
    policy = {x["memory_id"]: x["policy"] for x in body["preference_use_policy"]}
    if (len(ids) != len(set(ids)) or set(ids) != policy.keys()
            or len(policy) != len(body["preference_use_policy"])
            or any(v not in ("A", "B", "C") for v in policy.values())):
        raise ValueError("RP Actor sources do not align with policy")
    positions = _positions(sources, selected)
    overrides = {} if proposed_policy is None else proposed_policy
    selected_ids = {ids[i] for i in positions}
    if not overrides.keys() <= selected_ids or any(v not in ("A", "B", "C") for v in overrides.values()):
        raise ValueError("Proposed policy exceeds the archived Actor contract")
    body["source_evidence"] = [sources[i] for i in positions]
    body["preference_use_policy"] = [{"memory_id": ids[i], "policy": overrides.get(ids[i], policy[ids[i]])}
                                     for i in positions]
    user["content"] = json.dumps(body, ensure_ascii=False)
    return wire


def rendered_projection(request, original, selected, render_history, *, archived_positions=None, bench_guidance=None):
    """Keep the frozen renderer, including its original model and template."""
    wire = deepcopy(request)
    system, user = wire["messages"]
    if (system["role"], user["role"]) != ("system", "user"):
        raise ValueError("Unexpected Actor roles")
    previous = _positions(original, range(len(original)) if archived_positions is None else archived_positions)
    if render_history([original[i] for i in previous]) != system["content"]:
        raise ValueError("Frozen history renderer does not reproduce the archived system")
    positions = _positions(original, selected)
    system["content"] = render_history([original[i] for i in positions])
    if bench_guidance is not None:
        body = json.loads(user["content"])
        if (not set(body) <= {"query", "current_context", "fixed_facts", "selected_memory_use_guidance"}
                or not {"query", "current_context", "fixed_facts"} <= body.keys()):
            raise ValueError("Unexpected Strong Gate Actor task fields")
        original_guidance = body.pop("selected_memory_use_guidance", [])
        previous_guide = {}
        for entry in original_guidance:
            i = entry["memory_position_1_based"]
            if type(i) is not int or not 1 <= i <= len(previous) or i in previous_guide:
                raise ValueError("Archived guidance points outside the archived exposure")
            previous_guide[i] = entry["use_instruction"]
        instructions = {previous[i - 1]: note for i, note in previous_guide.items()}
        if (not bench_guidance.keys() <= set(positions)
                or any(not isinstance(v, str) or not v.strip() for v in bench_guidance.values())):
            raise ValueError("Proposed guidance points outside the projected exposure")
        instruction_list = [
            {"memory_position_1_based": new_pos, "use_instruction": bench_guidance.get(old, instructions.get(old))}
            for new_pos, old in enumerate(positions, 1)
            if old in bench_guidance or old in instructions
        ]
        if instruction_list:
            body["selected_memory_use_guidance"] = instruction_list
        user["content"] = json.dumps(body, ensure_ascii=False)
    return wire
