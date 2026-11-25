"""Admission by the scope of a preference holder's current decision."""

from .development import text_request
from .query_intent_counterfactual import COMMON, DIRECT


METHOD = "PREFERENCE_DECISION_SCOPE"

SCOPE = """
Before admitting a source, link its actual holder to the specific existing
choice or expression that the memory would change. Separate the person asking
or arranging the task from the people who choose, receive, use, or experience
the result. Making arrangements does not make the organizer's personal taste
evidence of someone else's taste or a shared priority.

Check the smallest concrete effect. A person's own experience, share of a
joint decision, requested voice, or continuing constraint may justify using
their history. For another person or a group, require a connection supported
by the current request or context, such as an explicitly shared preference,
their own relevant history, the user's delegated authority to decide using
their taste, or a real operational constraint in the current task. An
organizer's past preference for easy logistics is not an operational
constraint just because the task involves organizing. Time, quiet, access, or
other criteria that follow from the request still apply on their own; admit
history only for a warranted additional effect on a current choice.

For a shared experience, a soft preference may improve the user's part
without being ascribed to companions. A valid dietary, access, or other
constraint for someone who will actually participate can matter to the shared
result. A request to draft something for others can still use the sender's
appropriate voice or formatting. Preserve applicable personal preferences
without requiring the user to restate them. A condition that changes a source's
legitimate use must survive in its original wording. If a whole supplied span
would carry an unsupported influence and no permitted subset isolates the
legitimate effect, omit it. Keep useful task facts about affected people and
objects as facts. Do not expose this review or output any extra fields.
"""


def selector_request(task):
    return text_request(COMMON + DIRECT + SCOPE, task.payload(), cap=8192)
