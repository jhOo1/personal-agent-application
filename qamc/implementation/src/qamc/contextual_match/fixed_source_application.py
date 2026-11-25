"""Generation-interface probe with frozen, already compiled evidence only."""
from dataclasses import replace
from . import draft_application as base
from .draft_application import METHODS,COMMON,REWRITE,PATCH,draft_request,apply_request,decode,checked_answer,units


def selected_task(task,evidence):
    # Preserve original identities, complete text, order and qualifiers. A partial
    # source would require a separate explicit contract; never silently expand it.
    originals={m.memory_id:m for m in task.memories}
    ids=[e['memory_id'] for e in evidence]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate selected evidence')
    for e in evidence:
        if e['memory_id'] not in originals or e['text']!=originals[e['memory_id']].text:
            raise ValueError('This probe permits only exact complete saved sources')
    return replace(task,memories=tuple(originals[mid] for mid in ids))
