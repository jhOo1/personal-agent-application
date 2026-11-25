"""Validate the disposition of a frozen recommendation option set."""


def compile_options(options, decisions, binding_sources):
    """Return the visible option roles after checking coverage and provenance.

    Source strings must already be admitted as task facts or binding conditions.
    Exact quotation validates provenance only, not semantic incompatibility.
    """
    if not options or len({row["id"] for row in options}) != len(options):
        raise ValueError("Expected a nonempty option set with unique IDs")
    by_id = {row["id"]: row for row in options}
    seen = set()
    visible = []
    for row in decisions:
        option_id = row["id"]
        if option_id in seen or option_id not in by_id:
            raise ValueError("Unknown or duplicate option")
        seen.add(option_id)
        option = by_id[option_id]
        role = row["role"]
        if role == "omit":
            quote = row.get("quote")
            source = binding_sources.get(row.get("source_id"), "")
            if not isinstance(quote, str) or not quote.strip() or quote not in source:
                raise ValueError("Omission requires an exact binding source")
            conflict = row.get("conflict")
            if not isinstance(conflict, str) or not conflict.strip():
                raise ValueError("Omission requires a specific conflict")
            continue
        if role not in {"default", "alternative", "conditional"}:
            raise ValueError("Invalid option role")
        if option["conditional"] and role != "conditional":
            raise ValueError("An unverified prerequisite cannot become unconditional")
        visible.append({**option, "role": role})
    if seen != by_id.keys() or not visible:
        raise ValueError("Every option needs a disposition and at least one must remain")
    if sum(row["role"] == "default" for row in visible) > 1:
        raise ValueError("Conflicting defaults")
    return visible
