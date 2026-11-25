"""Compile provenance-checked obligations and decision-scoped preferences."""
from copy import deepcopy


def cited_span(sources, entry):
    source, quote = entry["source"], entry["quote"]
    if not isinstance(quote, str) or not quote.strip() or quote not in sources.get(source, ""):
        raise ValueError("Quote must occur in the referenced source")
    return {"source": source, "quote": quote}


def compile_guidance(task_sources, memory_sources, plan):
    if set(task_sources) & set(memory_sources):
        raise ValueError("Task and history must use separate source IDs")
    obligations = [cited_span(task_sources, row) for row in plan["obligations"]]
    decisions = {}
    for row in plan["decisions"]:
        key = row["id"]
        if not isinstance(key, str) or not key.strip() or key in decisions:
            raise ValueError("Invalid or duplicate decision ID")
        decisions[key] = cited_span(task_sources, row)
    bindings = []
    for row in plan["preferences"]:
        decision, use = row["decision"], row["use"]
        if decision not in decisions or use not in ("option", "constraint"):
            raise ValueError("Unknown decision or preference use")
        bindings.append({**cited_span(memory_sources, row), "decision": decision, "use": use})
    return {"obligations": obligations, "decisions": decisions, "preferences": bindings}


def render(wire, guidance, *, scoped):
    """Both arms receive identical task obligations and preference quotations."""
    result = deepcopy(wire)
    systems = [message for message in result["messages"] if message["role"] == "system"]
    if len(systems) != 1:
        raise ValueError("Expected one system message")
    obligations = [entry["quote"] for entry in guidance["obligations"]]
    options = []
    for entry in guidance["preferences"]:
        line = entry["quote"]
        if scoped:
            target = guidance["decisions"][entry["decision"]]["quote"]
            line = f"{line} | target: {target} | use: {entry['use']}"
        options.append(line)
    systems[0]["content"] += (
        "\n\nTask obligations and supplied facts:\n" + "\n".join(obligations)
        + "\n\nHistorical evidence to consider:\n" + "\n".join(options)
    )
    return result
