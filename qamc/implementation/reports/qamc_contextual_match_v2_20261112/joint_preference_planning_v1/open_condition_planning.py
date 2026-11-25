"""Bind independently sourced conditions to actions in a complete answer plan."""
from qamc.common import parse_object

from decision_witness_v45 import task_text, user_source
from planning import request, text
from thinking_budget_transport import controlled_wire


GENERIC, OPEN_FIRST = "GENERIC_PLAN", "OPEN_CONDITION_PLAN"
ARMS = (GENERIC, OPEN_FIRST)
BUDGET = 4096
GOALS_PROMPT = """Read the current task and the original history. List only conditions
that can change an actual choice in the current deliverable. For each, independently
cite a verbatim continuous quote from the user's historical words, and a verbatim
continuous current task anchor for the choice or affected party. Explain the
condition, including its original scope and who must actually carry it out or be
affected. Never convert the requester's private tastes into another person's
requirements. A requester may legitimately constrain their own effort or expense
even when another person experiences the result. One participant's applicable
restriction can constrain shared use without claiming the others share the taste.

REQUIRED means a genuine current requirement, firm exclusion or feasibility
condition. OPTIONAL means a beneficial, compatible soft preference for an actual
choice. Strong words in another situation do not create a current condition.
Uncertain external properties are not facts. Do not invent constraints, facts,
actions or candidate selections. Do not group different sources or roles into one
condition. Return JSON only, with explicit escaping for quotation marks in values:
{"goals":[{"memory_id":"M0","source_quote":"exact user quote","task_quote":"exact task quote",
"condition":"scope and concrete condition","strength":"REQUIRED"}]}.
Use at most 12 rows. Use an empty list when none apply."""

COMMON_PROMPT = """Deliver the complete requested answer in its requested language and format. Use the
current task and facts as ground truth. Use the supplied scoped conditions and
original evidence where appropriate to those choices and people. Keep applicable
optional personalization useful and proportionate. Protect all explicit task
requirements. Supply actual recommendations or other requested deliverables, and
never claim external attributes are established by a model guess.

Return a single JSON object {"items":[{"text":"user-facing prose or formatted answer section",
"satisfies":["G1"],"verify":[{"goal":"G2","check":"specific check for this proposal"}]}]}.
Only these plan items form the final answer. No extra prose after the object. Use
one to twelve ordered items. Each item has user-facing text and two lists of actual
relationships to known goal IDs. A satisfies entry requires an actual supporting
action or design choice in the text, not repetition of the requirement. Use
verify only for an essential external property that is still unknown, and say
what to verify for this specific item. Do not put goal IDs in user-facing text.
Escape any quotation marks in JSON string values."""

INSTRUCTION = {
    GENERIC: "Build a normal complete plan for the task. Record the scoped condition relationships in the items.",
    OPEN_FIRST: """Treat REQUIRED goals as initially open. Before settling the recommendations,
assign each open condition to at least one concrete supporting action or design
choice that you will actually put in the answer. Generate a task-compatible new
action if existing ideas cannot support it. If necessary use a specific conditional
action with its linked verification and a useful path if it fails. Do not proceed
from an open condition to an unqualified default recommendation. Render all
recommendations from the same resolved plan, including defaults and follow-up
actions, so a later item does not undo a condition handled earlier.""",
}


def goal_request(task, sources):
    return controlled_wire(request({"task": task, "source_evidence": sources}, GOALS_PROMPT, 8192), BUDGET)


def goals(task, sources, raw):
    payload = parse_object(raw)
    rows = payload.get("goals")
    if set(payload) != {"goals"} or not isinstance(rows, list) or len(rows) > 12:
        raise ValueError("Invalid goals envelope")
    users = {item["memory_id"]: user_source(item["text"]) for item in sources}
    anchors = tuple(task_text(task))
    selected, rejected, seen = [], [], set()
    for row in rows:
        keys = {"memory_id", "source_quote", "task_quote", "condition", "strength"}
        if not isinstance(row, dict) or set(row) != keys or not all(isinstance(x, str) for x in row.values()):
            rejected.append("SHAPE")
            continue
        mid, quote, anchor, condition, strength = (row[key] for key in
                                                    ("memory_id", "source_quote", "task_quote", "condition", "strength"))
        duplicate = (mid, quote, anchor, condition)
        if (not text(quote, 900) or not any(quote in user for user in users.get(mid, ()))
                or not text(anchor, 400) or not any(anchor in task for task in anchors)
                or not text(condition, 450) or strength not in ("REQUIRED", "OPTIONAL") or duplicate in seen):
            rejected.append("UNSUPPORTED_OR_DUPLICATE")
            continue
        seen.add(duplicate)
        selected.append({"id": f"G{len(selected) + 1}", **row})
    return selected, rejected


def actor_request(task, sources, conditions, arm):
    payload = {"task": task, "source_evidence": sources, "scoped_conditions": conditions}
    return controlled_wire(request(payload, COMMON_PROMPT + "\n\n" + INSTRUCTION[arm], 8192), BUDGET)


def render(task, conditions, raw):
    data = parse_object(raw)
    items = data.get("items")
    if set(data) != {"items"} or not isinstance(items, list) or not 1 <= len(items) <= 12:
        raise ValueError("Invalid plan envelope")
    known = {goal["id"] for goal in conditions}
    required = {goal["id"] for goal in conditions if goal["strength"] == "REQUIRED"}
    used, unresolved, sections = set(), set(), []
    chinese = any("\u3400" <= ch <= "\u9fff" for ch in task["query"])
    for item in items:
        if not isinstance(item, dict) or set(item) != {"text", "satisfies", "verify"} or not text(item["text"], 24000):
            raise ValueError("Malformed plan item")
        satisfies, verify = item["satisfies"], item["verify"]
        if (not isinstance(satisfies, list) or not all(isinstance(x, str) and x in known for x in satisfies)
                or len(set(satisfies)) != len(satisfies) or not isinstance(verify, list)):
            raise ValueError("Malformed goal references")
        used.update(satisfies)
        prose, checks = item["text"].strip(), {}
        for check in verify:
            if (not isinstance(check, dict) or set(check) != {"goal", "check"}
                    or not isinstance(check["goal"], str) or check["goal"] not in required
                    or check["goal"] in checks or check["goal"] in satisfies or not text(check["check"], 500)):
                raise ValueError("Malformed verification reference")
            checks[check["goal"]] = check["check"].strip()
        if checks:
            unresolved.update(checks)
            prose += "\n" + ("需核实：" if chinese else "Verify: ") + ("；" if chinese else "; ").join(checks.values())
        sections.append(prose)
    return {"answer": "\n\n".join(sections), "items": items, "claimed_supported": sorted(used),
            "action_linked_verification": sorted(unresolved), "open_without_action": sorted(required - used - unresolved),
            "required": sorted(required)}
