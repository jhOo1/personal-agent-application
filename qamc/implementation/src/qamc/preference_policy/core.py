"""Source-grounded use proposals and a single bounded resolution pass.

Validation proves referential consistency, not semantic correctness. All source
text is retained verbatim; no inferred world authority is granted by this module.
"""
from copy import deepcopy
import re
from qamc.b6_evidence import canonical_index
from qamc.common import sha, canonical

USES = {'PERSONAL_RANKING', 'PLAN_ADAPTATION', 'STYLE_ADAPTATION', 'USER_HISTORY', 'FACT_EVIDENCE'}
ACTIONS = {'APPLY', 'LIMITED', 'OMIT', 'UNRESOLVED'}


def fields(obj, required):
    if not isinstance(obj, dict) or set(obj) != set(required.split()):
        raise ValueError('expected fields: ' + required)


def short(value, maximum=800):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError('nonempty bounded string required')
    return value


def strings(value):
    if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
        raise ValueError('string list required')
    return value


def candidate_input(case, shared):
    """Reuse pre-Gate R and frozen Profile dependencies, not reduced E0.

    Official supplied profiles are complete and bypass artificial Top-K cropping.
    Historical input must be an exact subset of the legal benchmark prefix.
    """
    if case['benchmark'] == 'benchpres':
        sources = deepcopy(case['history'])
        candidates = [{'id': 'official:' + s['id'], 'source_ids': [s['id']]} for s in sources]
        retrieved = []
    else:
        if shared['top_k'] != 24 or len(shared['retrieved_ids']) > 24:
            raise ValueError('fixed detailed retrieval K=24 required')
        legal = {s['id']: s for s in case['history']}
        for s in shared['sources']:
            if legal.get(s['id']) != s:
                raise ValueError('source outside exact legal history prefix')
        sources, candidates = deepcopy(shared['sources']), deepcopy(shared['candidates'])
        retrieved = list(shared['retrieved_ids'])
    idx = canonical_index(sources, candidates, case['query'])
    units = []
    for u in idx['units']:
        if u['origin'] == 'DUPLICATE_OF_CURRENT_INPUT':
            continue
        source = next(s for s in sources if s['id'] == u['source_id'])
        if source['content'][u['start']:u['end']] != u['text']:
            raise ValueError('source offset mismatch')
        units.append({'unit_id': u['id'], 'source_id': u['source_id'], 'start': u['start'],
                      'end': u['end'], 'exact_text': u['text'], 'carrier': source.get('role', 'unknown'),
                      'memory_version': sha(source), 'attributed_author': None, 'subject': 'unknown',
                      'time': source.get('recorded_at'), 'modality': 'unknown'})
    payload = {'query': case['query'], 'current_context': deepcopy(case.get('current_context', [])),
               'query_time': case.get('query_time'), 'units': units}
    return {'payload': payload, 'input_hash': sha(payload), 'source_hash': sha(sources),
            'candidate_hash': sha(candidates), 'profile_hash': sha(shared.get('profile')),
            'retrieved_ids': retrieved, 'detailed_k': len(retrieved),
            'source_mode': 'complete_official_profile' if case['benchmark'] == 'benchpres' else 'frozen_top24_plus_profile_sources'}


def validate_scope(obj, payload):
    fields(obj, 'scopes task_unit_ids material_gaps')
    units = {u['unit_id'] for u in payload['units']}
    if not isinstance(obj['scopes'], list) or not 1 <= len(obj['scopes']) <= 3:
        raise ValueError('one to three real task scopes required')
    ids = set()
    for s in obj['scopes']:
        fields(s, 'scope_id query_anchor target_decision subject beneficiary recipient target_time shared_constraint_refs')
        short(s['scope_id'], 24)
        if s['scope_id'] in ids:
            raise ValueError('duplicate scope')
        ids.add(s['scope_id'])
        if short(s['query_anchor'], 12000) not in payload['query']:
            raise ValueError('scope anchor absent from query')
        for k in ('target_decision', 'subject', 'beneficiary', 'target_time'):
            short(s[k], 120)
        if s['recipient'] is not None:
            short(s['recipient'], 120)
        if not set(strings(s['shared_constraint_refs'])) <= units:
            raise ValueError('unknown shared constraint reference')
    if not set(strings(obj['task_unit_ids'])) <= units:
        raise ValueError('unknown task fact')
    strings(obj['material_gaps'])
    return obj


def use_key(x):
    return x['unit_id'], x['scope_id'], x['use_kind']


def validate_role(obj, payload, scopes, role):
    group, rest = ('proposals', 'gaps') if role == 'allow' else ('objections', 'uncertain')
    fields(obj, group + ' ' + rest)
    units = {u['unit_id'] for u in payload['units']}
    scope_ids = {s['scope_id'] for s in scopes['scopes']}
    if not isinstance(obj[group], list) or len(obj[group]) > 32:
        raise ValueError('sparse proposals required; maximum 32')
    seen = set()
    for x in obj[group]:
        common = 'unit_id scope_id use_kind source_refs query_anchor '
        fields(x, common + ('benefit support_level' if role == 'allow' else 'reason_code boundary'))
        k = use_key(x)
        if k in seen or k[0] not in units or k[1] not in scope_ids or k[2] not in USES:
            raise ValueError('duplicate or unknown UseKey')
        seen.add(k)
        refs = strings(x['source_refs'])
        if k[0] not in refs or not set(refs) <= units:
            raise ValueError('source refs must include the actual unit and stay within R')
        if short(x['query_anchor'], 12000) not in payload['query']:
            raise ValueError('query anchor must be exact')
        text = x['benefit'] if role == 'allow' else x['boundary']
        short(text, 500)
        # A syntactic guard cannot certify that a rationale is answer-free.
        if re.search(r'(?i)(?:correct|best|choose|answer)\s+(?:option\s*)?\(?[abcd]\)?\b', text):
            raise ValueError('option answer in proposal')
        if role == 'allow' and x['support_level'] not in {'DIRECT', 'SUPPORTED_INFERENCE', 'UNCERTAIN'}:
            raise ValueError('invalid support level')
        if role == 'deny':
            short(x['reason_code'], 80)
    strings(obj[rest])
    return obj


def validate_joint(obj, payload, scopes):
    fields(obj, 'allow deny')
    validate_role(obj['allow'], payload, scopes, 'allow')
    validate_role(obj['deny'], payload, scopes, 'deny')
    return obj


def merge(allow, deny, scope):
    """Conflict is per UseKey, not a global ban on the carrier or source."""
    aa = {use_key(x): x for x in allow['proposals']}
    dd = {use_key(x): x for x in deny['objections']}
    decisions, conflicts = [], []
    for key in sorted(aa.keys() | dd.keys()):
        if key in aa and key in dd:
            conflicts.append({'unit_id': key[0], 'scope_id': key[1], 'use_kind': key[2],
                              'allow': aa[key], 'deny': dd[key]})
        else:
            x = aa.get(key) or dd[key]
            action = 'APPLY' if key in aa and x['support_level'] != 'UNCERTAIN' else 'UNRESOLVED' if key in aa else 'OMIT'
            decisions.append({'unit_id': key[0], 'scope_id': key[1], 'use_kind': key[2],
                              'action': action, 'source_refs': x['source_refs'],
                              'boundary': x.get('boundary', x.get('benefit', ''))})
    gaps = list(dict.fromkeys(scope['material_gaps'] + allow['gaps'] + deny['uncertain']))
    if not aa and not dd:
        gaps.append('No preference-use proposals; this is not evidence of perfect selectivity.')
    return {'decisions': decisions, 'conflicts': conflicts, 'material_gaps': gaps}


def validate_resolution(obj, merged, payload, scope):
    fields(obj, 'decisions material_gaps')
    allowed = {use_key(x) for x in merged['conflicts']}
    seen = set()
    for x in obj['decisions']:
        fields(x, 'unit_id scope_id use_kind action source_refs boundary')
        k = use_key(x)
        if k not in allowed or k in seen or x['action'] not in ACTIONS:
            raise ValueError('resolver changed a nonconflicting use or returned contradictory decisions')
        seen.add(k)
        units = {u['unit_id'] for u in payload['units']}
        if k[0] not in strings(x['source_refs']) or not set(x['source_refs']) <= units:
            raise ValueError('invalid resolution sources')
        short(x['boundary'], 500)
    if seen != allowed:
        raise ValueError('resolver must decide every requested conflict exactly once')
    strings(obj['material_gaps'])
    return obj


def actor_view(payload, scope, decisions, gaps):
    """Shared task facts survive purpose-specific restrictions; metadata is soft."""
    kept = set(scope['task_unit_ids'])
    for s in scope['scopes']:
        kept.update(s['shared_constraint_refs'])
    for x in decisions:
        if x['action'] in {'APPLY', 'LIMITED'}:
            kept.update(x['source_refs'])
    evidence = [u for u in payload['units'] if u['unit_id'] in kept]
    return {'query': payload['query'], 'current_context': payload['current_context'],
            'query_time': payload['query_time'], 'source_evidence': evidence,
            'use_guidance': [x for x in decisions if x['unit_id'] in kept],
            'material_gaps': list(gaps)}
