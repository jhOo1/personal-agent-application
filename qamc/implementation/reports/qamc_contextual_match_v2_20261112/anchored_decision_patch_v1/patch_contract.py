"""Compile an exact, all-or-nothing decision substitution."""

from qamc.common import parse_object


def string(value, limit):
    return isinstance(value, str) and 0 < len(value.strip()) <= limit


def patch(raw, draft, task, evidence):
    parsed = parse_object(raw)
    if parsed == {"edits": []}:
        return draft, None
    if set(parsed) != {"decision", "task_anchor", "source_id", "quote", "edits"}:
        raise ValueError("Unexpected patch fields")
    decision, anchor, source, quote, edits = (
        parsed[k] for k in ("decision", "task_anchor", "source_id", "quote", "edits"))
    current = (task.get("query") or "", task.get("current_context") or "")
    if not string(decision, 120) or not string(anchor, 360) or not any(anchor in txt for txt in current):
        raise ValueError("No verified anchor for the named current decision")
    if not isinstance(source, str) or source not in evidence or not string(quote, 550) or quote not in evidence[source]:
        raise ValueError("No literal excerpt from the selected evidence source")
    if not isinstance(edits, list) or not 1 <= len(edits) <= 2:
        raise ValueError("Need one or two changes for one decision")
    spans = []
    for edit in edits:
        if set(edit) != {"old", "new"}:
            raise ValueError("Unexpected substitution fields")
        old, new = edit["old"], edit["new"]
        if not string(old, 360) or not string(new, 420) or old == new:
            raise ValueError("Substitution is empty, unchanged, or too broad")
        start = draft.find(old)
        if start < 0 or draft.find(old, start + 1) >= 0:
            raise ValueError("Old text is not a unique original span")
        spans.append((start, start + len(old), new))
    spans.sort()
    if len(spans) == 2 and spans[0][1] > spans[1][0]:
        raise ValueError("Substitutions overlap")
    for start, end, new in reversed(spans):
        draft = draft[:start] + new + draft[end:]
    return draft, {"decision": decision, "task_anchor": anchor, "source_id": source, "quote": quote,
                   "num_spans": len(spans)}
