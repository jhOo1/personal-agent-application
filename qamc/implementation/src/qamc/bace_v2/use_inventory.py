"""Concrete source-versioned uses with complete, non-truncating scheduling."""
import hashlib
import json

FIELDS = {'preference_id', 'source_ids', 'scope_id', 'part_id', 'target',
          'effect', 'role', 'conditions', 'query_refs'}
ROLES = {'PERSONAL_RANKING', 'PLAN_ADAPTATION', 'STYLE_ADAPTATION',
         'USER_HISTORY', 'FACT_EVIDENCE'}


def use_card(proposal, sources, query_catalog, parts, scopes, preference_ids):
    if set(proposal) != FIELDS:
        raise ValueError('Exact concrete-use schema required')
    for field in ('preference_id', 'scope_id', 'part_id', 'target', 'effect', 'role'):
        if not isinstance(proposal[field], str) or not proposal[field].strip():
            raise ValueError('Nonempty use identity required: ' + field)
    if proposal['preference_id'] not in preference_ids:
        raise ValueError('Unknown preference')
    if proposal['part_id'] not in parts or proposal['scope_id'] not in scopes:
        raise ValueError('Unknown task output part or scope')
    if proposal['role'] not in ROLES:
        raise ValueError('Unknown influence role')
    for field in ('source_ids', 'query_refs', 'conditions'):
        value = proposal[field]
        if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value):
            raise ValueError('String list required: ' + field)
        if len(set(value)) != len(value):
            raise ValueError('Duplicate reference or condition')
    if not proposal['source_ids'] or not set(proposal['source_ids']) <= set(sources):
        raise ValueError('Unknown or missing historical source')
    if not proposal['query_refs'] or not set(proposal['query_refs']) <= set(query_catalog):
        raise ValueError('Unknown or missing query reference')
    # Include concrete influence and version, so different effects never merge.
    value = {**proposal, 'source_versions': {
        key: sources[key]['source_version'] for key in proposal['source_ids']}}
    identity = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return {**value, 'use_id': 'USE:' + hashlib.sha256(identity.encode()).hexdigest()[:24],
            'proposal_status': 'PROPOSED_NOT_APPROVED'}


def batches(cards, batch_size=12):
    if type(batch_size) is not int or batch_size < 1:
        raise ValueError('Positive integer batch size required')
    seen = set(); unique = []
    # Preserve source/proposal encounter order, not arbitrary ID lexical order.
    for card in cards:
        if card['use_id'] not in seen:
            unique.append(card); seen.add(card['use_id'])
    return [unique[i:i + batch_size] for i in range(0, len(unique), batch_size)]


def validate_complete_assessment(cards, rows):
    expected = {c['use_id'] for c in cards}
    actual = [r['use_id'] for r in rows]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError('Every proposed use needs one explicit assessment state')
