"""Bounded local Policy deltas with isolated evaluation and immutable versions."""
from copy import deepcopy
import re
from qamc.common import sha, canonical
from .core import fields, short, strings

OPERATIONS = {'ADD', 'EDIT', 'NARROW_TRIGGER', 'ADD_EXCEPTION', 'MERGE', 'RETIRE'}
CARD_FIELDS = 'policy_id version target_role trigger positive_use boundary exceptions evidence_pattern support_experience_ids validation status'


def validate_library(cards):
    if not isinstance(cards, list) or len(cards) > 12:
        raise ValueError('maximum 12 policy cards')
    ids = set()
    for c in cards:
        fields(c, CARD_FIELDS)
        if c['policy_id'] in ids or not re.fullmatch(r'P_[A-Z0-9_]{1,40}', c['policy_id']):
            raise ValueError('invalid or duplicate policy id')
        ids.add(c['policy_id'])
        if type(c['version']) is not int or c['version'] < 1 or c['target_role'] not in {'allow','deny','both'}:
            raise ValueError('invalid policy version or role')
        for k in ['trigger','positive_use','boundary']:
            short(c[k], 600)
        for k in ['exceptions','evidence_pattern','support_experience_ids']:
            strings(c[k])
        if len(canonical(c)) > 2400 or c['status'] not in {'draft','active','retired'}:
            raise ValueError('unbounded/invalid policy')
        fields(c['validation'], 'tested improved regressed')
        if any(type(v) is not int or v < 0 for v in c['validation'].values()):
            raise ValueError('invalid policy validation')
        text = canonical({k: c[k] for k in ['trigger','positive_use','boundary','exceptions']})
        if re.search(r'[0-9a-f]{8}-[0-9a-f-]{27,}|\b(?:personamem|benchpres|prefeval|op-bench)\b|(?i:correct option|answer is [abcd])', text):
            raise ValueError('benchmark identity/answer leakage into card')
    return cards


def apply_delta(cards, delta, phase='opt'):
    if phase != 'opt':
        raise ValueError('policy updates prohibited outside D_opt')
    fields(delta, 'operation target_ids card explanation')
    op = delta['operation']
    if op not in OPERATIONS:
        raise ValueError('unknown delta operation')
    targets = strings(delta['target_ids'])
    by = {c['policy_id']: deepcopy(c) for c in cards}
    if any(i not in by or by[i]['status'] != 'active' for i in targets):
        raise ValueError('unknown/retired target')
    if op == 'ADD':
        if targets or not delta['card'] or delta['card']['policy_id'] in by:
            raise ValueError('ADD must create one fresh card')
    elif op == 'MERGE':
        if len(set(targets)) < 2 or not delta['card'] or delta['card']['policy_id'] in by:
            raise ValueError('MERGE needs two existing cards and one fresh card')
        for i in targets:
            by[i]['status'] = 'retired'
    elif len(targets) != 1:
        raise ValueError('one target required')
    elif op == 'RETIRE':
        if delta['card'] is not None:
            raise ValueError('RETIRE does not add content')
        by[targets[0]]['status'] = 'retired'
    else:
        new, old = delta['card'], by[targets[0]]
        if not new or new['policy_id'] != old['policy_id'] or new['version'] != old['version'] + 1:
            raise ValueError('EDIT must increment the same policy version')
        if op == 'NARROW_TRIGGER' and any(new[k] != old[k] for k in old if k not in {'version','trigger','validation','support_experience_ids'}):
            raise ValueError('NARROW_TRIGGER may only change trigger and provenance')
        if op == 'ADD_EXCEPTION' and (not set(old['exceptions']) < set(new['exceptions']) or any(new[k] != old[k] for k in old if k not in {'version','exceptions','validation','support_experience_ids'})):
            raise ValueError('ADD_EXCEPTION must preserve the card and add an exception')
    if delta['card'] is not None:
        by[delta['card']['policy_id']] = deepcopy(delta['card'])
    # Retired versions live in the append-only version log, not in the active cap.
    out = [x for x in by.values() if x['status'] != 'retired']
    validate_library(out)
    return out


def retrieve(cards, payload, role):
    """Input-only lexical routing; never sees benchmark ids, references or scores."""
    query = payload['query'] + ' ' + ' '.join(x['exact_text'] for x in payload['units'])
    terms = set(re.findall(r'\w+', query.lower()))
    eligible = [c for c in cards if c['status']=='active' and c['target_role'] in {role,'both'}]
    return sorted(eligible, key=lambda c: (-len(terms & set(re.findall(r'\w+', c['trigger'].lower()))), c['policy_id']))[:3]


def promote(parent, candidate, target_improved):
    """Automatic development screening; not statistical or semantic certification."""
    if not target_improved or candidate['valid'] < parent['valid'] or candidate['correct'] < parent['correct']:
        return False
    if 'quality_valid' not in candidate:
        return False
    if candidate['quality_valid'] != candidate['planned'] or parent['quality_valid'] != parent['planned']:
        return False
    for key in ['unsupported','proxy_overuse','proxy_underuse']:
        if candidate[key] is None or parent[key] is None or candidate[key] > parent[key]:
            return False
    return candidate['task_faithfulness'] >= parent['task_faithfulness'] - .2
