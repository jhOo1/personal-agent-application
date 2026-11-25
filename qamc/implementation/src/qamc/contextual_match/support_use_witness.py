"""Verify a SUPPORT decision in the Selector's existing call and compiler path."""
import json
from unicodedata import normalize

from qamc.common import parse_object
from . import goal_effect, goal_effect_gepa


METHOD = 'SUPPORT_USE_WITNESS'
OWNERS = {'REQUESTER', 'SHARED', 'TARGET', 'DELIVERY'}
REJECTED_SUPPORT = {'NO_SCOPE': 'SCOPE_MISMATCH', 'NO_INCREMENT': 'COMPATIBLE_ONLY',
                    'UNRESOLVED': 'UNRESOLVED'}
WITNESS_FIELDS = {'status', 'decision_owner', 'source_span_id', 'source_quote',
                  'ordinary_choice', 'memory_choice'}

SUPPORT_PROTOCOL = '''
For a SUPPORT row, substantiate its use in a concrete decision that actually
belongs to the current task. Add exactly one support_witness to that row. Keep
all existing effect fields. Other effects, including applicable constraints
and requested representation, use their existing contract.

A supported witness has status USEFUL, decision_owner REQUESTER, SHARED,
TARGET, or DELIVERY, source_span_id, source_quote, ordinary_choice and
memory_choice. Select one existing decision owner. A TARGET decision concerns
the actual beneficiary or recipient, such as the person who will receive a
gift. A requester's interests can affect their own preparation, budget or a
shared decision without establishing another person's taste. A DELIVERY choice
concerns how this actual answer or deliverable should be expressed. Identify
the scope bridge in the retained source; distinguish the user's words from a
historical assistant suggestion.

source_quote must be a verbatim, meaningful excerpt within source_span_id, an
already kept span. Compare one plausible task-appropriate choice without the
memory to the concrete choice, priority or constraint the original evidence
would change or protect. Keep the goal and participants fixed across these
short descriptions. A useful soft option qualifies; novelty and necessity are
not required. A different wording of the same recommendation, a personal
attribution alone or an invented side goal does not establish a benefit.

Use at most 160 characters for source_quote and 120 for each choice. These
descriptions are evidence for deciding admission only; do not write answers.
If a SUPPORT row cannot support its proposed use, give only status NO_SCOPE,
NO_INCREMENT or UNRESOLVED in its witness, or choose the appropriate existing
non-SUPPORT effect in the first place. Do not add witness fields to other rows.
'''

_OLD_CONTRACT = 'keep_span_ids,task_anchor,use_instruction. No additional decisions or explanations.'
_NEW_CONTRACT = ('keep_span_ids,task_anchor,use_instruction. A SUPPORT row has one additional '
                 'support_witness as defined below. No additional decisions or explanations.')
SYSTEM = goal_effect.SYSTEM.replace(_OLD_CONTRACT, _NEW_CONTRACT) + SUPPORT_PROTOCOL


def selector_request(task):
    request = goal_effect.selector_request(task)
    request['messages'][0]['content'] = SYSTEM
    return request


def choice_identity(text):
    # Normalize spelling and spacing only, with no semantic equivalence claim.
    return ''.join(ch for ch in normalize('NFKC', text).casefold() if ch.isalnum())


def verify_witness(memory, kept, witness):
    if not isinstance(witness, dict) or not isinstance(witness.get('status'), str):
        raise ValueError('SUPPORT requires a structured witness')
    status = witness['status']
    if status in REJECTED_SUPPORT:
        if witness.keys() != {'status'}:
            raise ValueError('A rejected witness must contain only its status')
        return REJECTED_SUPPORT[status]
    if status != 'USEFUL' or witness.keys() != WITNESS_FIELDS:
        raise ValueError('Unexpected SUPPORT witness fields')
    if witness['decision_owner'] not in OWNERS:
        raise ValueError('Unknown SUPPORT decision owner')

    span_id = witness['source_span_id']
    quote = witness['source_quote']
    if (memory is None or not isinstance(span_id, str) or span_id not in kept
            or not isinstance(quote, str) or not quote.strip() or len(quote) > 160
            or quote not in memory.spans().get(span_id, '')):
        raise ValueError('SUPPORT witness is outside the selected original span')
    ordinary, proposed = (witness['ordinary_choice'], witness['memory_choice'])
    if any(not isinstance(text, str) or len(text) > 120 or not choice_identity(text)
           for text in (ordinary, proposed)):
        raise ValueError('SUPPORT witness must specify two concrete choices')
    return 'COMPATIBLE_ONLY' if choice_identity(ordinary) == choice_identity(proposed) else 'SUPPORT'


def actor(task, raw, prompts, bridge):
    result = parse_object(raw)
    if result.keys() != {'memory_effects'} or not isinstance(result['memory_effects'], list):
        raise ValueError('Expected exactly memory_effects')
    memories = {memory.memory_id: memory for memory in task.memories}
    normalized, decisions = [], []
    for row in result['memory_effects']:
        if not isinstance(row, dict):
            raise ValueError('Invalid effect row')
        base = {key: value for key, value in row.items() if key != 'support_witness'}
        normalized.append(base)
        if row.get('effect') != 'SUPPORT':
            if 'support_witness' in row:
                raise ValueError('Only SUPPORT can supply a witness')
            continue
        identity = row['memory_id']
        witness = row.get('support_witness')
        effect = verify_witness(memories.get(identity), row['keep_span_ids'], witness)
        decisions.append({'memory_id': identity, 'effective_effect': effect, 'witness': witness})
        if effect != 'SUPPORT':
            base.update(effect=effect, keep_span_ids=[], use_instruction=None)

    built = goal_effect_gepa.actor(task, json.dumps({'memory_effects': normalized}, ensure_ascii=False),
                                   prompts, bridge)
    built['effect_audit']['support_witnesses'] = decisions
    built['audit'].update(support_witness_is_hidden_from_actor=True,
                          support_semantics_validated=False,
                          additional_model_calls_per_case=0)
    return built
