"""Prospective sparse use-boundary interface; not dispatched or promoted.

Adapted from the observed MemAdapter source-use mechanism. The original R4
admission and source compiler remain unchanged; policy-rejected notes disappear.
"""
from copy import deepcopy
import json

from qamc.common import parse_object
from . import query_mode, use_admission
from .core import normalize_selection


BOUNDARY_NOTE = """
This prospective variant adds exactly one top-level object: use_bounds.
Its keys must be exactly the memory_ids retained by your preference_actions
before the program's admission checks. Each value is one concise instruction
(at most 80 words), grounded in the retained original span(s) and current task.

For each source, state its concrete helpful influence on an existing task
decision and the limit on that influence. Do not merely repeat PERSONAL_CHOICE
or APPLICABLE. A relevant preference may improve a choice without becoming a
mandatory or highest-priority constraint. A past unsuccessful event may reveal
a risk to address rather than a decision to repeat. Preserve explicit continuing
constraints and useful optional preferences; do not make all personalization
conditional on the query repeating it. Apply task-relevant basic feasibility,
accuracy and affected-party requirements without inventing a new user objective.

Personal views can inform a requested portrayal but do not become external
truth or automatically justify categorical advice. Respect the requested genre
and legitimate stance while keeping attribution and appropriate limits clear.
Give source-use boundaries, not an answer, option ranking, recommendation list,
new personal fact, or rewritten memory. Do not quote rejected content in a note.
The notes are fallible instructions, not new evidence or verified conclusions.
Return only preference_actions, unresolved_ids, source_uses and use_bounds.
"""


def selector_request(task, prompts, memory_view, old_task_view, frame):
    body = query_mode.selector_request(task, prompts, memory_view, old_task_view, frame)
    system = body['messages'][0]['content']
    forbidden = 'No free-form use instructions, answer text, extra evidence, or additional calls.'
    if system.count(forbidden) != 1:
        raise ValueError('R4 prompt boundary changed')
    # Replace all old conflicting output restrictions in this new variant only.
    replacements = {
        forbidden: 'No answer text, extra evidence, or additional calls.',
        'Do not\nadd other fields.': 'Use only the fields in the final variant contract below.',
        'Keep the source_uses output\ncontract above unchanged. Do not produce additional fields or an answer.':
            'Keep the source_uses records unchanged; the final variant contract may add use_bounds. Do not produce an answer.'}
    for before, after in replacements.items():
        if system.count(before) != 1: raise ValueError('Inherited output instruction changed')
        system = system.replace(before, after)
    body['messages'][0]['content'] = system + BOUNDARY_NOTE
    return body


def actor(task, answer, prompts, frame, show_bounds=True):
    obj = parse_object(answer)
    if not isinstance(obj, dict) or set(obj) != {'preference_actions', 'unresolved_ids', 'source_uses', 'use_bounds'}:
        raise ValueError('Expected sparse R4 decision plus concrete use_bounds')
    bounds = obj['use_bounds']
    legacy = {k: deepcopy(v) for k, v in obj.items() if k != 'use_bounds'}
    decoded = use_admission.decode(task, json.dumps(legacy, ensure_ascii=False), enforce=False)
    normalized = normalize_selection(task, json.loads(decoded['answer']))
    selected_ids = {r['memory_id'] for r in normalized['preference_actions'] if r['keep_span_ids']}
    if not isinstance(bounds, dict) or set(bounds) != selected_ids:
        raise ValueError('Use bounds must cover exactly the predicted retained sources')
    for note in bounds.values():
        if not isinstance(note, str) or not note.strip() or len(note.split()) > 80 or len(note) > 700:
            raise ValueError('Invalid or excessive source-use boundary')
    result = query_mode.actor(task, json.dumps(legacy, ensure_ascii=False), prompts, frame, enforce=True)
    body = deepcopy(result['request'])
    payload = json.loads(body['messages'][1]['content'])
    final_ids = [r['memory_id'] for r in payload['source_evidence']]
    notes = [{'memory_id': mid, 'use_instruction': bounds[mid]} for mid in final_ids]
    if show_bounds and notes:
        payload['memory_use_instructions'] = notes
        body['messages'][1]['content'] = json.dumps(payload, ensure_ascii=False)
    return {**result, 'request': body, 'concrete_use_audit': {
        'predicted_bounds': bounds, 'admitted_bounds': notes, 'shown_to_actor': show_bounds,
        'semantic_correctness_proven': False, 'method_promoted': False}}
