"""Unrun policy: distinguish supported personal assertions from proposals.

The caller supplies a frozen compiled Actor input. Admission, original evidence,
use notes and public request are immutable. No sampling or reliability claim.
"""
from copy import deepcopy

CONTRACT = '''
Grounded delivery contract:
Produce the requested deliverable, distinguishing what the user can reasonably
ask or propose from what is already known about this user.

Personal assertions need support in the current request or supplied evidence.
Do not invent an earlier event, cause, conflict, diagnosis, completion, dispute
subject, availability or outcome merely to make a message sound complete.
Keep plans, enrollment, appointments and completed events distinct. Do not treat
a missing detail as false or zero, or turn a plausible connection into a known
personal fact.

Requests and proposals can still be concrete. When the task asks for a message
seeking an action, make a useful, appropriate request without fabricating the
personal history that would justify it. Do not retreat to merely asking how to
write or submit the message. Missing particulars need not erase the known facts,
legitimate preferences, or the requested action.

Use only the background needed for this deliverable, rather than listing the
entire available profile. Honor applicable concise, courteous, formatting and
other supplied preferences in the actual answer. Completeness means serving the
current purpose, not repeating every available fact. Avoid extra versions,
prefaces and explanations unless requested; return one complete deliverable at
an appropriate length. Ordinary world knowledge and supported contextual
inferences remain available; this is not a requirement to quote every sentence.
'''

REVIEW = '''
General delivery review:
Before returning the answer, review the whole draft against the actual request,
current context, supplied evidence and selected memory guidance. Perform this
review inside the same answer call; do not output an audit or ask for another
model call.

Check that the answer achieves the requested purpose, addresses the intended
recipient, includes every necessary part, and uses a suitable structure. Prefer
a useful finished response over a vague description of what could be done.
Consider whether a reader could act on it and whether any requested constraint
has been overlooked.

Reconsider the relevance and accuracy of the details used. Keep warranted
personalization, helpful optional preferences and applicable constraints without
letting irrelevant history take over the response. Review subjects, chronology,
scope and attribution; avoid unfounded claims, contradictions and distracting
background. Preserve useful information even when other details are unknown.

Finally check clarity, coherence, emphasis, tone and length. Make concise
preferences visible in the answer, and keep appropriate formatting and courtesy.
Remove unnecessary repetition, filler, side topics, awkward phrasing and extra
commentary. Ensure the answer is specific enough to help while remaining faithful
to the provided information. Return the requested final answer only, without
the review, a self-rating or a description of these checks.
'''

METHODS = ('GROUNDED_DELIVERY', 'GENERIC_DELIVERY_REVIEW')


def from_frozen_actor(compiled, method):
    """Change only the system suffix, retaining the exact evidence and request."""
    if method not in METHODS:
        raise ValueError('Unknown prospective delivery policy')
    built = deepcopy(compiled)
    request = built['request']
    systems = [m for m in request['messages'] if m['role'] == 'system']
    if len(systems) != 1 or not isinstance(systems[0]['content'], str):
        raise ValueError('Expected one unchanged base Actor system message')
    systems[0]['content'] += CONTRACT if method == METHODS[0] else REVIEW
    built.setdefault('audit', {}).update(
        delivery_policy=method, selection_changed=False, evidence_changed=False,
        original_use_notes_changed=False, additional_model_calls=0,
        semantic_grounding_guaranteed=False)
    return built
