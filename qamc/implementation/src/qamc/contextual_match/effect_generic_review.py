"""Same-call holistic review control for the source-faithful policy candidate."""
from . import goal_effect, goal_effect_gepa


REVIEW = '''
General final review (inside this same Selector call):
Before returning the JSON, reconsider the complete proposed selection and its
use instructions against the original current request and all original memories.
Perform a careful holistic review, rather than accepting your first plausible
judgment. Do not output this review or request another model call.

First verify the actual purpose, affected people and relevant decisions. For
each proposed retained source, check that it offers a concrete useful effect
on the task as asked. For each rejected source, check that you have not overlooked
a valid constraint, helpful soft preference or ordinary contextual connection.
Consider the strongest reasonable case both for retaining and for rejecting
the source. Resolve those alternatives using the given evidence, not a tendency
to personalize everything or to avoid personalization altogether.

Review attribution, chronology, participants, scope and compatibility with the
current instructions. Separate the user's views from world knowledge and the
user's own preferences from another person's needs. Check that combined sources
remain coherent and that useful information was not lost merely because it was
optional. A change in domain alone does not settle relevance. Keep supported
inferences but do not invent facts or adopt a flattering explanation as evidence.

Finally check every effect code, span reference, literal task anchor and use
instruction. The instructions should clearly explain the appropriate role of
retained evidence without drifting away from the original task or its supported
meaning. Ensure all input memories have one complete row, rejected memories have
no use instruction, and retained sources obey the original length limits.
Return only the unchanged effect JSON. Preserve the original uncertainty policy,
source text, output schema and boundaries; no additional fields, answers,
rankings, explanations or self-assigned quality score are requested.
'''

SYSTEM = goal_effect.SYSTEM + REVIEW
METHOD = 'GENERIC_REVIEW_EFFECT_GEPA'


def selector_request(task):
    body = goal_effect.selector_request(task)
    body['messages'][0]['content'] = SYSTEM
    return body


def actor(task, raw, prompts, bridge):
    return goal_effect_gepa.actor(task, raw, prompts, bridge)
