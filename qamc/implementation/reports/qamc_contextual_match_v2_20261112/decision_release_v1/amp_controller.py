"""Fixed AMP task frame and authorization wire contracts."""
import json

from amp_release import KINDS, Permission, Slot, compile_release

FRAME = """Read only the current task, current context and fixed task facts. Identify existing decisions the answer must make, including potential choices of the requester and people actually affected, expression for the named recipient, and factual fields the deliverable needs. Do not invent a person, preference or task. Return JSON {"slots":[{"id":"S1","kind":"decision|expression|fact","description":"existing decision or factual field; specify whose choice or whose fact when grounded"}]}. Return 1 to 12 slots, no answer and no rationale."""

AUTHORIZE = """Read the fixed task frame and original history. By default do not use history. Use it only to perform an existing task operation and only for the people and scope it actually governs. An individual interest cannot determine another person's or group's choices. In a formal document use required facts but avoid unnecessary private style or alias disclosure. A personal belief is not authority about the objective world. Do not merely spot topic matches or create a new choice to use history. A condition or constraint must retain its subject, strength, negation and exceptions.
Return JSON {"permissions":[{"source":"original source ID","slot":"task frame slot ID","type":"prefer|require|express|ground","quote":"exact original supporting span","effect":"concrete execution instruction without the private reason, or null for ground"}]}. Prefer can improve a limited choice, require can govern a necessary condition or a clearly dominating authorized choice, express controls delivery only, and ground releases an exact original fact or condition. Ground requires effect null; other operations must give a short concrete instruction. Return an empty list if nothing has a legitimate use. Do not generate the answer."""

FREE = """Read the task frame and original history. Build a useful and concise downstream memory view for completing the task using source details only when appropriate. You are free to select, omit, summarize or transform the material. Respect current requirements, identify who actually makes or benefits from a decision, avoid unnecessary disclosure in formal communications, retain needed constraints and avoid taking private beliefs as objective facts. Return JSON {"memory_view":"contents for answer generation only"}. Empty text is valid if no history should be used. Do not generate the answer or include an explanation of what was omitted."""

ADAPTER = """The request includes auxiliary task-grounded memory input. It may contain original factual evidence and separately authorized operational choices, or a general selected history view. Use such material only for its stated task and scope. Treat a decision or expression instruction as guidance with its stated force, never as a factual assertion about a person. Treat source facts as attributed and context limited. The unchanged query and current facts define the deliverable and take priority. Return only the requested final deliverable."""


def parse(raw):
    def unique(items):
        out = {}
        for k, v in items:
            if k in out:
                raise ValueError("Duplicate JSON key")
            out[k] = v
        return out
    if not isinstance(raw, str):
        raise ValueError("Missing controller reply")
    return json.loads(raw, object_pairs_hook=unique)


def task_frame(raw):
    value = parse(raw)
    slots = value.get("slots") if isinstance(value, dict) and value.keys() == {"slots"} else None
    if not isinstance(slots, list) or not 1 <= len(slots) <= 12:
        raise ValueError("Invalid task slot inventory")
    result = []
    for row in slots:
        if (not isinstance(row, dict) or row.keys() != {"id", "kind", "description"}
                or row["id"] != f"S{len(result)+1}" or row["kind"] not in set(KINDS.values())
                or not isinstance(row["description"], str) or not 1 <= len(row["description"].strip()) <= 260):
            raise ValueError("Invalid task slot")
        result.append(Slot(row["id"], row["kind"], row["description"]))
    return tuple(result)


def authorize(raw, slots, sources):
    value = parse(raw)
    rows = value.get("permissions") if isinstance(value, dict) and value.keys() == {"permissions"} else None
    if not isinstance(rows, list) or len(rows) > 24:
        raise ValueError("Invalid permission inventory")
    plan = []
    for row in rows:
        if not isinstance(row, dict) or row.keys() != {"source", "slot", "type", "quote", "effect"}:
            raise ValueError("Invalid permission fields")
        key, slot, action, quote, effect = (row[k] for k in ("source", "slot", "type", "quote", "effect"))
        if (not isinstance(key, str) or key not in sources or not isinstance(slot, str)
                or not isinstance(action, str) or action not in KINDS
                or not isinstance(quote, str) or not quote.strip() or quote not in sources[key]):
            raise ValueError("Cannot bind permission to an exact original quote")
        if action == "ground":
            if effect is not None:
                raise ValueError("Ground must preserve source wording")
            start = sources[key].index(quote)
            plan.append(Permission(key, slot, action, span=(start, start + len(quote))))
        else:
            if not isinstance(effect, str) or not effect.strip():
                raise ValueError("Missing effect instruction")
            plan.append(Permission(key, slot, action, instruction=effect))
    # Contract validation is common to all authorization-based arms.
    compile_release(slots, sources, tuple(plan), exposure="partitioned")
    return tuple(plan)


def free_view(raw):
    v = parse(raw)
    if (not isinstance(v, dict) or v.keys() != {"memory_view"} or not isinstance(v["memory_view"], str)
            or len(v["memory_view"]) > 16000):
        raise ValueError("Malformed unconstrained memory view")
    return {"memory_view": v["memory_view"]}
