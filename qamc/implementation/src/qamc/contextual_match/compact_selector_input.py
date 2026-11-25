"""A reversible representation for single-span Selector sources."""

from copy import deepcopy
import json


SINGLE_SPAN_NOTICE = (
    '\n\nA memory with one span may omit its duplicate text field. '
    'The sole value in spans is its entire original text. '
    'Use its existing span ID exactly as usual.'
)


def compact_selector_request(request):
    """Remove only a proven byte-identical whole-source duplicate."""
    system, user = request['messages']
    if (system['role'], user['role']) != ('system', 'user'):
        raise ValueError('Expected the frozen two-message Selector interface')
    payload = json.loads(user['content'])
    removed = []
    for memory in payload['memories']:
        spans = memory['spans']
        text = memory['text']
        if len(spans) == 1 and text == next(iter(spans.values())):
            del memory['text']
            removed.append(memory['memory_id'])
    compact = deepcopy(request)
    if removed:
        compact['messages'][0]['content'] += SINGLE_SPAN_NOTICE
        compact['messages'][1]['content'] = json.dumps(payload, ensure_ascii=False)
    return compact, removed


def restore_public_payload(compact):
    """Recover the original public object for audit or offline replay."""
    payload = json.loads(compact['messages'][1]['content'])
    for memory in payload['memories']:
        if 'text' in memory:
            continue
        spans = memory['spans']
        if len(spans) != 1:
            raise ValueError('Compact memory must contain exactly one original span')
        memory['text'], = spans.values()
    return payload
