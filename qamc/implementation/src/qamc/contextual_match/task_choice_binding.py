"""Bind each admitted memory to a choice from an independently built TaskView."""

from copy import deepcopy
import json

from qamc.common import parse_object

from . import goal_effect, goal_effect_gepa
from .core import exact_keys, validate_task_view
from .development import text_request


BOUND = 'TASK_CHOICE_BOUND'
REVIEW = 'TASK_CHOICE_REVIEW'

SHARED = """
The task_choice_frame was extracted from query and current context before any
memory was read. It is a fallible aid. Use the actual request as authority.
The requester, the people who experience the result, and its recipient can
be different. A person may share a choice without controlling all criteria.
Distinguish criteria already implied by the task from useful effects actually
added by memory. For example, current time constraints may justify efficiency
on their own; that is insufficient to establish an increment from memory.
Keep an applicable optional taste as well as any valid strong constraint.
Do not add another deliverable, transfer a taste to a different person,
or adopt a private belief as an objective claim.
"""

REVIEW_RULES = """
Perform a strong ordinary review of all original candidate memories against
the current task and the same independently extracted frame. Check whether
each memory improves any existing decision or valid presentation choice, and
whether its subject and conditions apply. Consider reasons to keep and reasons
to omit each source before emitting your answer. Do not reject a useful soft
preference merely because a generic answer is feasible. Use the established
memory_effects output with its exact source and task references. Return only
the original schema, with no new fields. The frame is helpful context.
"""

BOUND_RULES = """
For each admitted row, attach the influence to ONE existing choice ID from
task_choice_frame.choices and determine which of the recorded roles actually
experiences, decides or receives that effect. A role reference confirms who is
involved; it does not establish shared taste. Keep a choice unchanged when its
only memory-dependent justification needs a different beneficiary or a new
deliverable. A style preference can apply to the requested output even when its
reader is someone else. Rank within acceptable options for a shared preference.
For a constraint, only narrow the feasible options of the affected choice.

Override the output schema by adding exactly one key "task_binding" to every
memory_effects row. For an admitted row its value is
{"choice_id":"D0","role_ids":["R0"]} using only existing IDs. An empty role_ids
list is allowed if no role need be tagged, or if the isolated frame omitted a
role already established by the actual context. Otherwise name affected roles.
For a rejected row task_binding is null. The existing task_anchor remains a
literal current quote; the compiler will use the chosen choice's frozen quote.
The binding is only for an authorized use of the existing source passages.
Return only JSON. Do not add an analysis, example answer or imagined baseline.
"""


def frame(task, task_view):
    """Project only query/current-context fields with verified source offsets."""
    view = validate_task_view(task, task_view)
    choices = []
    for field_name, kind in (('deliverables', 'D'), ('constraints', 'C')):
        choices.extend({'id': f'{kind}{i}', 'kind': field_name, **field}
                       for i, field in enumerate(view[field_name])
                       if field['status'] != 'UNKNOWN')
    return {
        'choices': choices,
        'roles': [{'id': f'R{i}', **field} for i, field in enumerate(view['roles'])
                  if field['status'] != 'UNKNOWN'],
        'unresolved_mentions': view['unresolved_mentions'],
    }


def selector_request(task, task_view, method):
    suffix = {BOUND: BOUND_RULES, REVIEW: REVIEW_RULES}[method]
    payload = {**task.payload(), 'observed_probe_answers': [],
               'task_choice_frame': frame(task, task_view)}
    return text_request(goal_effect.SYSTEM + SHARED + suffix, payload)


def actor(task, task_view, raw, prompts, bridge, method):
    if method == REVIEW:
        return goal_effect_gepa.actor(task, raw, prompts, bridge)
    if method != BOUND:
        raise ValueError('Unknown choice-binding comparison arm')
    choice_frame = frame(task, task_view)
    choices = {row['id']: row for row in choice_frame['choices']}
    roles = {row['id'] for row in choice_frame['roles']}
    result = parse_object(raw)
    exact_keys(result, {'memory_effects'})
    if not isinstance(result['memory_effects'], list):
        raise ValueError('Expected a memory_effects list')
    unbound, trace = [], []
    for value in result['memory_effects']:
        exact_keys(value, {'memory_id', 'effect', 'keep_span_ids', 'task_anchor',
                           'use_instruction', 'task_binding'})
        row = deepcopy(value)
        binding = row.pop('task_binding')
        if row['effect'] in goal_effect.KEEP:
            anchor = row['task_anchor']
            if not isinstance(anchor, str) or not anchor.strip() or not any(
                    anchor in text for text in (task.query, task.current_context)):
                raise ValueError('Admitted usage lacks a literal current task anchor')
            exact_keys(binding, {'choice_id', 'role_ids'})
            choice_id, role_ids = binding['choice_id'], binding['role_ids']
            if not isinstance(choice_id, str) or choice_id not in choices:
                raise ValueError('Admitted usage must point to a fixed task choice')
            if (not isinstance(role_ids, list) or any(not isinstance(x, str) for x in role_ids)
                    or len(set(role_ids)) != len(role_ids) or not set(role_ids) <= roles):
                raise ValueError('Binding names an unknown or duplicate task role')
            row['task_anchor'] = choices[choice_id]['evidence'][0]['quote']
            trace.append({'memory_id': row['memory_id'], **binding})
        elif binding is not None:
            raise ValueError('Rejected sources cannot claim a task binding')
        unbound.append(row)
    compiled = goal_effect_gepa.actor(task, json.dumps({'memory_effects': unbound}, ensure_ascii=False),
                                     prompts, bridge)
    compiled['effect_audit']['choice_bindings'] = trace
    return compiled
