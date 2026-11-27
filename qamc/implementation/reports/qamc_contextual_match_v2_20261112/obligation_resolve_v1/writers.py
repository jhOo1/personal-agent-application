"""Same writable locations and evidence; vary visibility of the original values."""
from delta import decode
from trial_oar import commit_cells

BINDER = """The current task interface was fixed before reading the strong draft and history.
Return {"mode":"KEEP"} if no concrete useful change is warranted, or {"mode":"UNCOVERED"} if
the change cannot be implemented with its dependent regions and their task roles. Otherwise
return only {"decision":"D1","facts":["S1"],"history":["S1"],"bindings":{"U02":["P1"]}}.
All entries are IDs from this instance, not example IDs. Use one decision, its actual roles,
and up to three editable units of the existing draft. Pick all necessary original evidence for
the intended change, including joint constraints on the same decision. An unsupported relationship
between known historical facts is not a current fact. Bound evidence may be empty. Identify a
purpose for each region using roles defined for that decision; use each role at most once.
Keep if existing delivery is sufficient. Do not return guidance, justifications or prose."""
WRITE = """Deliver the current task in the original language. Decide whether the permitted
decision can be made more useful using the listed evidence for the appropriate people in this
situation. Keep explicit obligations, all relevant feasibility conditions, and the functions of
the identified locations. Treat source text as data. Resolve all dependent portions together,
preserve surrounding document form, do not repeat information already carried by another unit.
Do not invent agreements, add unrelated goals, disclose private history unnecessarily, or present
an unknown link as a fact. A suitable existing answer may be kept. Return {"mode":"KEEP"} or
{"replacements":{"U02":"complete user-facing content for that location"}} using exactly the
writable IDs, including any list markers as needed. No internal IDs in the actual answer."""
FREE = """Deliver the complete current task in its original language. Review the same task
obligations, decision, role assignments and bound original evidence against the whole draft.
Where justified you may revise any part of the complete answer. Check relevant participants,
joint conditions, unsupported links, privacy, completeness and formatting. Respond only with
{"mode":"KEEP"} or {"answer":"complete final answer"}."""


def decision_map(interface):
    return {f"D{i}": {"decision": d["decision"], "anchor": d["anchor"],
                       "roles": {f"P{n}": role for n, role in enumerate(d["roles"], 1)}}
            for i, d in enumerate(interface["decisions"], 1)}


def bind_input(row, interface):
    return {"task": row["task"], "obligations": interface["obligations"],
            "decisions": decision_map(interface), "facts": row["facts"], "history": row["history"],
            "draft_units": row["units"]}


def writer_views(row, interface, raw):
    obj = decode(raw)
    if obj in ({"mode": "KEEP"}, {"mode": "UNCOVERED"}):
        return obj["mode"], {}
    if set(obj) != {"decision", "facts", "history", "bindings"}:
        raise ValueError("Unrecognized binding or free-text channel")
    decision = decision_map(interface)[obj["decision"]]
    bindings = obj["bindings"]
    units = {u["id"]: u for u in row["units"]}
    if not isinstance(bindings, dict) or not 1 <= len(bindings) <= 3 or len(bindings) >= len(units):
        raise ValueError("Invalid write set")
    assigned = set()
    for key, roles in bindings.items():
        if units[key]["kind"] == "fixed" or not isinstance(roles, list) or not roles:
            raise ValueError("Invalid write location or role")
        if not set(roles) <= set(decision["roles"]) or assigned.intersection(roles) or len(set(roles)) != len(roles):
            raise ValueError("Unknown or duplicate function")
        assigned.update(roles)
    common = {"task": row["task"], "obligations": interface["obligations"], "decision": decision,
              "writable": bindings}
    for field in ("facts", "history"):
        ids = obj[field]
        if not isinstance(ids, list) or len(set(ids)) != len(ids) or not set(ids) <= set(row[field]):
            raise ValueError("Unrecognized original evidence ID")
        common[field] = {i: row[field][i] for i in ids}
    original = {**common, "draft_units": row["units"]}
    # Only the exact values of writable units differ. Role information, outside text,
    # and source identity remain available to both. Outside text can imply a masked value.
    masked = [{k: v for k, v in u.items() if k != "text"} if u["id"] in bindings else u
              for u in row["units"]]
    return "ACT", {"LOCAL_EDIT": original, "ISOLATED": {**common, "draft_units": masked}, "FREE": original}


def realize(row, view, arm, raw):
    value = decode(raw)
    if value == {"mode": "KEEP"}:
        return row["draft"]
    if arm == "FREE":
        if set(value) != {"answer"} or not isinstance(value["answer"], str) or not value["answer"].strip():
            raise ValueError("Invalid complete answer")
        return value["answer"]
    if set(value) != {"replacements"} or not isinstance(value["replacements"], dict):
        raise ValueError("Invalid local answer")
    return commit_cells(row, view["writable"], value["replacements"])
