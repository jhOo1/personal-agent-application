"""Compare use mapping and equally budgeted review after evidence is committed.

Source admission is inherited unchanged. These are fallible use instructions,
not a formal shield, a new profile, or a source of personal facts.
"""
from copy import deepcopy
import json

from qamc.common import parse_object


COMMON = """Read the original current task, fixed factual context and COMMITTED
original excerpts. A previous frozen selector has already selected these sources.
You cannot add, delete, rewrite or rescore sources. Help the final assistant use
the evidence to complete the original request accurately. Protect useful optional
preferences as well as explicit continuing constraints. Preserve attribution,
negation, conditions, chronology and uncertainty. A person's belief is not world
evidence; a past event is not automatically a continuing requirement. Respect a
perspective the CURRENT task asks to explain or represent, without silently
endorsing it as universal truth. Do not invent goals, facts or missing details.
Do not answer the task, rank concrete options, or create a new user profile.
"""

MAP = """Return only {"memory_use_instructions":[{"memory_id":"...",
"use_instruction":"..."}]}, exactly one record per committed source, in input
order. For each source specify its concrete useful influence WITHIN the current
task and what it cannot establish or override. Distinguish a supported local
preference from a condition needed for the requested outcome to succeed. Where
influences interact, keep their compatible roles rather than making every source
an unconditional or highest-priority rule. Do not turn an undesirable past outcome
into a prescription to repeat it. If a source has no warranted influence under
this task, say so in its instruction; the original still remains visible. Do not
repeat unrelated content or claim that these instructions are verified facts.
Each instruction is at most80 words/700 characters. Empty sources require [].
"""

REVIEW = """Perform a strong ordinary review of how the committed evidence can
help this specific task. Summarize the task-relevant facts, useful personalization,
conditions, conflicts and uncertainties that the final assistant should respect.
Consider positive usefulness and overextension together; do not merely repeat a
generic safety warning. You may identify unwarranted influences while retaining
the source text. Return only {"review":"a concise evidence-grounded review"}.
Use at most80 words/700 characters per committed source in total (minimum one
such allowance). This is a generation aid, not an answer or new evidence.
"""


def request(actor_request, method):
    if method not in {'USE_MAP', 'GENERIC_REVIEW'}:
        raise ValueError('Unknown committed-use method')
    payload = json.loads(actor_request['messages'][1]['content'])
    if set(payload) != {'query', 'current_context', 'facts', 'source_evidence'}:
        raise ValueError('Expected original, unannotated evidence payload')
    # Carry the frozen streaming/usage envelope, not only semantic model fields.
    body = deepcopy(actor_request)
    body.update(temperature=0, max_tokens=8192,
                messages=[{'role': 'system', 'content': COMMON + (MAP if method == 'USE_MAP' else REVIEW)},
                          {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)}])
    return body


def actor(original, answer, method):
    body = deepcopy(original)
    payload = json.loads(body['messages'][1]['content'])
    ids = [s['memory_id'] for s in payload['source_evidence']]
    obj = parse_object(answer)
    if not isinstance(obj, dict):
        raise ValueError('Use aid must be an object')
    if method == 'USE_MAP':
        if set(obj) != {'memory_use_instructions'} or not isinstance(obj['memory_use_instructions'], list):
            raise ValueError('Expected source use map')
        notes = obj['memory_use_instructions']
        if any(not isinstance(n, dict) or set(n) != {'memory_id', 'use_instruction'} for n in notes):
            raise ValueError('Unexpected use record')
        if [n['memory_id'] for n in notes] != ids:
            raise ValueError('Cannot add, omit or reorder committed source IDs')
        texts, allowance = [n['use_instruction'] for n in notes], 1
        if notes:
            payload['memory_use_instructions'] = notes
    elif method == 'GENERIC_REVIEW':
        if set(obj) != {'review'}:
            raise ValueError('Expected generic review')
        texts, allowance = [obj['review']], max(1, len(ids))
        payload['review_summary'] = obj['review']
    else:
        raise ValueError('Unknown committed-use method')
    if any(not isinstance(t, str) or not t.strip() or len(t.split()) > 80 * allowance
           or len(t) > 700 * allowance for t in texts):
        raise ValueError('Invalid or excessive use aid')
    body['messages'][1]['content'] = json.dumps(payload, ensure_ascii=False)
    return body
