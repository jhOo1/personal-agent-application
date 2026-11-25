"""Conservative evaluation-only flags, never replacement scores or truth labels."""
import json


def source_free_wire(body, actor_system):
    """Recognize only the exact common-Actor query-only envelope.

    An empty source_evidence list is insufficient if a summary, use instruction,
    fixed fact, current history or another message can still carry memories.
    The public Query itself may contain tastes; this is not a guarantee that
    the answer ought to receive a perfect Benchmark score.
    """
    messages = body.get('messages', [])
    if (len(messages) != 2 or messages[0] != {'role': 'system', 'content': actor_system}
            or messages[1].get('role') != 'user'):
        return False
    try:
        payload = json.loads(messages[1]['content'])
    except (ValueError, TypeError):
        return False
    return (isinstance(payload, dict)
            and set(payload) == {'query', 'current_context', 'facts', 'source_evidence'}
            and isinstance(payload['query'], str)
            and payload['current_context'] == '' and payload['facts'] == []
            and payload['source_evidence'] == [])


def diagnostic_flags(reference, score, no_supplied_memory):
    if score is None:
        return []
    multiple = isinstance(reference['persona'], list)
    label = reference['intent_type']
    if not multiple:
        label = {'ignore': 'A', 'support': 'B', 'supportive': 'B',
                 'dominate': 'C', 'dominant': 'C'}.get(label, label)
    all_a = isinstance(label, str) and bool(label) and set(label) == {'A'}
    result = []
    if no_supplied_memory and score['matched'] != score['total']:
        result.append('SOURCE_FREE_NONPERFECT_MATCH_NEEDS_ANSWER_REVIEW')
    if all_a and score['severity']['UPB'] > 0:
        result.append('ALL_A_POSITIVE_UPB_NEEDS_RUBRIC_REVIEW')
    return result
