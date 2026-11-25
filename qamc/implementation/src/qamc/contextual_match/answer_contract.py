"""One Actor instruction delta, compared with existing frozen strong controls.

All arms receive identical R4-selected originals. No planner, draft, critic,
source rewrite, extra inference or benchmark-specific generation rule exists.
"""
from .actor_use_window_v2 import build as legacy_build


TASK_PRIORITY = """Anchor the answer's priorities in the CURRENT request and what a
successful result requires for its actual beneficiaries. Memory can refine choices
within that task; it does not replace the task's success criteria with whatever
historical preference or behavior is most salient.

A report that someone made a past choice establishes an event, not a current
non-negotiable requirement. Do not promote an inferred taste, habitual response,
or personal stance into a mandatory condition or highest priority without a
supported present or continuing constraint. A past mismatch or unsuccessful choice
may identify a problem to address rather than a decision rule to repeat.

Preserve relevant personal facts, useful soft preferences and standing explicit
constraints even when the query does not restate them. In particular, do not turn
an actual negative, dietary, ethical or feasibility constraint into an optional
suggestion. Apply preferences within a useful, feasible answer to the actual task,
respecting affected parties and basic task requirements. If the current request
asks to represent a viewpoint, represent it faithfully as a viewpoint. Complete
the requested answer directly; do not expose this process or add extra tasks.
"""


def build(task, original, method, strong_prompt):
    if method == "SELECTED_STRONG":
        return legacy_build(task, original, "STRONG_REMINDER", strong_prompt=strong_prompt)["request"]
    if method == "SELECTED_USE":
        return legacy_build(task, original, "USE_ONLY")["request"]
    body = legacy_build(task, original, "ORIGINAL")["request"]
    if method == "TASK_PRIORITY":
        body["messages"][0]["content"] += "\n\n" + TASK_PRIORITY
    elif method != "R4_BASE":
        raise ValueError("Unknown answer-contract arm")
    return body
