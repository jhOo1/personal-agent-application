"""Lossless action-list envelope compatibility, not semantic model repair.

Unknown uncertainty metadata stays unreported in the audit. The compiler-only
empty list is not a claim that every decision was resolved. Original source
actions, IDs, legal spans and the strict compiler remain unchanged.
"""
import json
from .core import normalize_selection
from qamc.common import parse_object


def compiler_input(task,answer):
    # The legacy object extractor finds the first {...} inside an array. Read
    # complete JSON first so a one-action list cannot become a bare action dict.
    try:value=json.loads(answer.strip())
    except json.JSONDecodeError:value=parse_object(answer)
    bare=isinstance(value,list)
    selection={'preference_actions':value,'unresolved_ids':[]} if bare else value
    # The strict original validator rejects missing/duplicate sources, shorthand
    # labels, extra fields and illegal PARTIAL spans. Never infer a decision.
    normalize_selection(task,selection)
    return {'answer':json.dumps(selection,ensure_ascii=False),
            'audit':{'envelope_only':bare,'uncertainty_metadata':'UNREPORTED' if bare else 'EXPLICIT',
                     'actions_rewritten':False,'source_text_rewritten':False}}
