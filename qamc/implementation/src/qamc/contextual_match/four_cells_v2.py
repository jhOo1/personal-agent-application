"""v2 four-cell input/selector interface; original compilation and Actor intact.

No Store, retriever, reference labels, model client or performance gate exists
here. Views are fallible predictions; their presence never changes candidates.
"""
import json
from .core import validate_memory_view, validate_task_view
from .development import read_request, actor_request

CELLS = {'F00': (False, False), 'F01': (False, True),
         'F10': (True, False), 'F11': (True, True)}

MATCHER = """\n\nUse the same original sparse selection contract. Perform both checks within
this one selection: positive task value and unsupported application boundaries.

For each original source, identify what existing choice, constraint, expression
or practical requirement it could improve. Useful soft preferences need not be
necessary, and the query need not repeat every applicable taste. Preserve valid
negative preferences and conditions, including evidence that jointly resolves
participants or references. Select all warranted original sources directly;
there is no later dependency closure or second reviewer to repair omissions.

Then check whether that benefit actually depends on changing the beneficiary,
assuming participation, inventing recipient preferences, broadening the source's
meaning, treating an attributed belief as world evidence, or creating a new goal.
Do not confuse a context where a preference was expressed with an explicit limit
on where it applies. A legitimate transfer preserves the supported condition or
choice; neither topic overlap alone nor a change of domain settles applicability.

When supplied, Memory View and Task View help locate subjects, polarity,
conditions, scope, provenance and current task dimensions. They are fallible
aids, not replacements for the full query and original sources. Check proposed
connections against those originals. EXPLICIT and TASK_IMPLIED are distinct;
ordinary choices entailed by the request are allowed, but inferred fields do not
authorize extra goals. INFERRED is not automatically a proven task implication.
UNKNOWN fields alone neither invalidate a source nor establish global scope.

Keep the original memory IDs, existing span boundaries and sparse JSON output.
Do not generate answers, new source text, usage instructions, audit graphs,
dependency edges, additional output fields, or a more permissive uncertainty
fallback. If a source is retained, the unchanged Compiler forwards its original
text; decide appropriately under that interface rather than assuming hidden
per-decision instructions will constrain the Actor.
"""


def selector_request(task, cell, prompts, memory_view=None, task_view=None):
    if cell not in CELLS:raise ValueError('Unknown four-cell arm')
    uses_views, uses_matcher = CELLS[cell]
    # F00 is byte-identical to the actual frozen R0 builder. F10 changes only
    # the user-side payload, not the original Selector system instructions.
    body = read_request(task, 'R0', prompts)
    if uses_views:
        payload = json.loads(body['messages'][-1]['content'])
        payload['memory_view'] = validate_memory_view(task, memory_view)
        payload['task_view'] = validate_task_view(task, task_view)
        body['messages'][-1]['content'] = json.dumps(payload, ensure_ascii=False)
    elif memory_view is not None or task_view is not None:
        raise ValueError('Raw arm cannot silently receive a View')
    if uses_matcher:body['messages'][0]['content'] += MATCHER
    return body


def compiled_actor(task, selection_answer, prompts):
    # All four use the original sparse normalization, V1 source compiler and
    # Actor request. No dependency helper, deduplication or generated use hint.
    return actor_request(task, 'R0', selection_answer, prompts)


def prompt_manifest(prompts):
    return {'original_selector': prompts['style_selector'],
            'paired_matcher': prompts['style_selector'] + MATCHER,
            'matcher_addendum': MATCHER, 'actor': prompts['actor'],
            'same_system_pairs': [['F00', 'F10'], ['F01', 'F11']],
            'first_round_dependencies': False, 'first_round_actor_changes': False}
