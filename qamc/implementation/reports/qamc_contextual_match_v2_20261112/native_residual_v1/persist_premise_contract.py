"""Render one anchored question without replacing the original deliverable."""
from collections.abc import Mapping


def grounded_probe(probe, sources):
    if probe is None:
        return None
    fields = {"source_id", "quote", "open_question"}
    if not isinstance(probe, Mapping) or set(probe) != fields:
        raise ValueError("Expected one source, quotation and open question")
    if any(not isinstance(probe[field], str) or not probe[field].strip() for field in fields):
        raise ValueError("Premise probe fields must contain text")
    source = sources.get(probe["source_id"])
    if source is None or probe["quote"] not in source:
        raise ValueError("Premise probe quote does not match the named source")
    if not probe["open_question"].rstrip().endswith("?"):
        raise ValueError("Expected an open question")
    return dict(probe)


def comparison_inputs(task, memory, preparation):
    """Give both arms the same task, memory and ordinary preparation."""
    if "query" in memory:
        raise ValueError("Reserved source ID")
    sources = {"query": task["query"], **memory}
    probe = grounded_probe(preparation.get("premise_probe"), sources)
    control = {"task": task, "memory": memory, "preparation": preparation["reasoning_note"]}
    if probe is None:
        return control, control
    return control, {**control, "open_premise": probe}
