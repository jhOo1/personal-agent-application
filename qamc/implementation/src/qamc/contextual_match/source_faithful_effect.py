"""Minimal source-faithful use-note policy, not a proven semantic guarantee.

One Selector still predicts the existing eight effects. The original decoder,
source Compiler, and complete released GEPA Actor remain unchanged. No review
call, View, Store, or benchmark-specific decision is introduced.
"""
from . import goal_effect, goal_effect_gepa


USE_CONTRACT = '''
Use-note fidelity contract (inside this same Selector call):
After deciding applicability under the existing rules, check that the proposed
use instruction preserves the meaning, strength and supported conditions of
the selected original source in this task. A plausible-sounding instruction
can still weaken a valid preference or invent a restriction.

For a retained preference, preserve its useful positive effect; do not add an
unstated prerequisite, medium exception, or permission test that would disable
it. An unknown condition is not evidence that the condition is false. Only add
a limiting condition when the source or actual current task supports it; do not
invent one merely because it might occur. Keep source qualifiers that really
exist, including subject, scope, negation, time and uncertainty. Do not turn a
scheduled event into a completed event or a soft taste into a hard requirement.

This does not authorize a currently inapplicable source. Do not manufacture a
recipient preference, participant, event, goal or useful effect to justify
retention. Reasonable contextual inference remains allowed under the original
rules; do not demand literal restatement of every legitimate relationship.
Do not remove every conditional phrase or treat observed historical context as
an exclusive scope restriction. Keep the original omission policy for unresolved
applicability. Apply this check before returning the unchanged effect JSON;
no extra audit fields, answers, self-rating or additional call are requested.
'''

SYSTEM = goal_effect.SYSTEM + USE_CONTRACT
METHOD = 'SOURCE_FAITHFUL_EFFECT_GEPA'


def selector_request(task):
    request = goal_effect.selector_request(task)
    request['messages'][0]['content'] = SYSTEM
    return request


def decode(task, raw):
    return goal_effect.decode(task, raw)


def actor(task, raw, prompts, bridge):
    # Identical compiled evidence produces the exact same Actor wire. New
    # Selector predictions can still change evidence; do not call this a
    # same-selected-evidence experiment merely because initial sources match.
    return goal_effect_gepa.actor(task, raw, prompts, bridge)
