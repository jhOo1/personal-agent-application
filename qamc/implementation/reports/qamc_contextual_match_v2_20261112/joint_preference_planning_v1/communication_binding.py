"""Bind communication preferences to the acts they can affect."""
import json

from qamc.common import parse_object

import decision_realization as base


ACTS = {"ADDRESS", "SIGN_OR_IDENTIFY", "REGISTER", "LAYOUT", "OTHER"}
RELATIONS = {"SAME_HOLDER", "DIFFERENT_HOLDER", "UNKNOWN", "NOT_APPLICABLE"}
FIT = {"COMPATIBLE", "CONFLICT", "UNKNOWN", "NOT_APPLICABLE"}
PERSONAL = {"ADDRESS", "SIGN_OR_IDENTIFY"}
EXTRA = """For each proposed memory use, include a seventh field communication with exactly
source_act, task_act, role_relation, and register_fit. Consider what the source would allow
in its own context, and separately what the proposed use does in this task. Do not omit a
plausible proposal just because these four fields identify a disagreement. The runtime
will check them and may remove the use.

source_act and task_act: ADDRESS (someone directly addresses another), SIGN_OR_IDENTIFY
(self-identification or third-person reference in a deliverable), REGISTER (tone, humor,
emojis, or manner of writing), LAYOUT (format, emphasis, structure), OTHER (noncommunication).
Classify the effect, not the subject matter. A preference for what others call someone is
ADDRESS, even if a proposed use would put that name in a signature. A preference about
signatures is SIGN_OR_IDENTIFY. For a personal act, role_relation is SAME_HOLDER only if
the person being addressed or identified by the actual output is the person whose preference
authorizes that same act. Otherwise DIFFERENT_HOLDER or UNKNOWN. NOT_APPLICABLE for other acts.
For REGISTER or LAYOUT set register_fit to COMPATIBLE, CONFLICT or UNKNOWN based on the
actual purpose, recipient and conventions of the requested deliverable. Compatible general
concision, clarity and emphasis are often useful. Casual private interaction, emphatic
emotions or humor do not automatically fit a separate formal or sensitive communication.
Do not infer a conflict from professional context alone. For other acts set NOT_APPLICABLE.
Use the same exact source_quote and task_quote to anchor your justification. Do not use
benchmark labels or answer the task. The seven-field entries are the only change to the schema."""


def selector(root):
    instruction = base.SELECT.replace("affected_role, task_quote, source_quote.",
                                      "affected_role, task_quote, source_quote, communication.")
    return base.planning.request(base.planning.packet(root), instruction + "\n\n" + EXTRA, 8192)


def gate(value):
    source, action, role, fit = (value[key] for key in ("source_act", "task_act", "role_relation", "register_fit"))
    if source in PERSONAL or action in PERSONAL:
        if source != action:
            return "INCOMPATIBLE_COMMUNICATION_ACT"
        if role != "SAME_HOLDER":
            return "PERSONAL_ACT_NOT_GROUNDED"
    if "REGISTER" in (source, action) and (source != action or fit != "COMPATIBLE"):
        return "REGISTER_NOT_SUPPORTED_FOR_DELIVERY"
    if "LAYOUT" in (source, action) and (source != action or fit == "CONFLICT"):
        return "LAYOUT_NOT_SUPPORTED_FOR_DELIVERY"
    return None


def compile_views(root, raw):
    obj = parse_object(raw)
    proposed = obj.get("uses")
    if set(obj) != {"uses"} or not isinstance(proposed, list):
        raise ValueError("Expected a communication-bound uses list")
    fields = {"source_act": ACTS, "task_act": ACTS, "role_relation": RELATIONS, "register_fit": FIT}
    uses, typed = [], {}
    for entry in proposed:
        if not isinstance(entry, dict) or set(entry) != {*base.EDGES, "communication"}:
            raise ValueError("Missing communication binding")
        comm, mid = entry["communication"], entry["memory_id"]
        if (not isinstance(mid, str) or mid in typed or not isinstance(comm, dict)
                or set(comm) != fields.keys()
                or any(not isinstance(comm[k], str) or comm[k] not in options for k, options in fields.items())):
            raise ValueError("Invalid or duplicate communication binding")
        uses.append({k: v for k, v in entry.items() if k != "communication"})
        typed[mid] = comm
    ordered, bad_quotes = base.compile_uses(root, json.dumps({"uses": uses}, ensure_ascii=False))
    decisions = {edge["memory_id"]: gate(typed[edge["memory_id"]]) for edge in ordered}
    retained = [edge for edge in ordered if decisions[edge["memory_id"]] is None]
    return {"plain": ordered, "bound": retained, "typed": typed, "gate": decisions, "base_rejections": bad_quotes}
