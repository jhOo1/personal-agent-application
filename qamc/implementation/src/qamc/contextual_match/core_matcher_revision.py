"""One applicability revision of F11; frozen Views, compiler and Actor stay intact.

This module has no dataset labels, case identifiers, model client or Store writes.
Contract tests establish input isolation, not semantic improvement.
"""
from .four_cells_v2 import selector_request as frozen_selector_request
from .four_cells_v2 import compiled_actor


APPLICABILITY_CHECK = """\n\nBefore retaining a source, check its incremental value for an existing decision
in the current request and for the person affected by that decision. A possible
connection to the general topic is not enough. Do not invent an activity, goal,
participant, or recipient preference in order to make a source useful. Items or
advice already justified by the query alone do not by themselves demonstrate a
personalization benefit from an otherwise unrelated source.

When the request is for another person or group, the requester's personal tastes
are not evidence of that person's tastes. Retain requester facts or constraints
only when their actual role in the requested arrangement is supported. Unknown
recipient preferences should remain unknown, rather than being filled from the
requester's hobbies. This is not a blanket ban on group tasks or soft preferences.

Keep applicable negative preferences and material constraints even across a
change of occasion or season when the original source supports that transfer.
Evaluate sources jointly when a condition requires more than one source. Preserve
the existing sparse selection output; do not output this reasoning, a proposed
answer, additional fields, or new usage instructions.
"""


def selector_request(task, prompts, memory_view, task_view):
    """Change only the Matcher system instruction of the frozen F11 request."""
    body = frozen_selector_request(task, "F11", prompts, memory_view, task_view)
    body["messages"][0]["content"] += APPLICABILITY_CHECK
    return body


__all__ = ["APPLICABILITY_CHECK", "selector_request", "compiled_actor"]
