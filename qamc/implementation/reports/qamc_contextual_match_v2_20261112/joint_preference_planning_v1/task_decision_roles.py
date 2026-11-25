"""Infer who acts and who is affected for each choice from the current task."""
from qamc.common import parse_object, sha

from decision_witness_v45 import task_text
from planning import request, text
from thinking_budget_transport import controlled_wire


PARTIES = frozenset(("SELF", "OTHER", "SHARED", "UNKNOWN"))
BUDGET = 4096
PROMPT = """Resolve roles for each supplied choice using only the current task.
Keep its original identity and order. Identify the person who carries out the choice
and who experiences its outcome as separate fields. The person asking for help is SELF.
Use OTHER when the outcome belongs to another party with no confirmed participation by
the requester, SHARED when the requester and others experience it, and UNKNOWN when
the task does not establish who experiences or performs it. Making an arrangement for
someone does not establish that the organizer will experience its outcome. Drafting a
message for the requester and imposing their preferences on the recipient are distinct.
For each choice cite an exact continuous quotation from the current task, not from the
choice description. Unknown roles are allowed. Mark choices that seek missing information
as CLARIFICATION. Use DECISION for a choice that can change the requested outcome or
the execution of this task. Do not resolve missing facts or add a new choice.

Return only {"roles":[{"slot":1,"executor":"SELF","beneficiary":"OTHER",
"kind":"DECISION","task_quote":"<verbatim phrase>"}]}. One row per supplied slot."""


def payload(task, choices):
    if set(task) != {"query", "current_context", "facts"} or not 1 <= len(choices) <= 8:
        raise ValueError("Expected one public task and its ordered choices")
    slots = [{"slot": index, **choice} for index, choice in enumerate(choices, 1)]
    return {"task": task, "choices": slots}


def role_request(task, choices):
    return controlled_wire(request(payload(task, choices), PROMPT, 8192), BUDGET)


def parse_roles(task, choices, raw):
    data = parse_object(raw)
    if set(data) != {"roles"} or not isinstance(data["roles"], list):
        raise ValueError("Expected one roles array")
    roles = data["roles"]
    if len(roles) != len(choices):
        raise ValueError("Role coverage differs from the task choice list")
    anchors = tuple(task_text(task))
    for slot, role in enumerate(roles, 1):
        if (not isinstance(role, dict) or set(role) != {"slot", "executor", "beneficiary", "kind", "task_quote"}
                or type(role["slot"]) is not int or role["slot"] != slot):
            raise ValueError("Role output changed slot identity or order")
        if any(not isinstance(role[key], str) or role[key] not in PARTIES for key in ("executor", "beneficiary")):
            raise ValueError("Unrecognized participant relationship")
        if role["kind"] not in ("DECISION", "CLARIFICATION"):
            raise ValueError("Unrecognized choice kind")
        quote = role["task_quote"]
        if not text(quote, 300) or not any(quote in field for field in anchors):
            raise ValueError("Role quote must come from the current public task")
    return roles


def partition_tasks(manifest):
    """Use the same already-exposed tasks once, regardless of the history variant."""
    tasks = {}
    for row in manifest["units"]:
        body = parse_object(row["request"]["messages"][1]["content"])
        task, choices = body["task"], body["task_choices"]
        source = {"task": task, "choices": choices}
        key = sha(task)
        if key in tasks and source != tasks[key]:
            raise ValueError("One task has multiple previously frozen choice baselines")
        tasks[key] = source
    return tasks
