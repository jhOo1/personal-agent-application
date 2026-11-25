"""Validate transient source organization; never write memory or approve uses."""
from copy import deepcopy
import hashlib
import json
from .use_inventory import use_card


def exact(obj, fields):
    if not isinstance(obj, dict) or set(obj) != set(fields.split()):
        raise ValueError('Schema mismatch: ' + fields)


def refs(value, allowed, nonempty=True):
    if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
        raise ValueError('Reference list required')
    if len(value) != len(set(value)) or not set(value) <= set(allowed) or (nonempty and not value):
        raise ValueError('Invalid or missing source references')


def compile_organization(obj, sources, query_sources):
    exact(obj, 'task_frame preferences fact_candidates uncertain_source_ids unreviewed_source_ids proposed_uses no_use')
    frame = obj['task_frame']
    exact(frame, 'goal requester beneficiary recipient output_parts requirements')
    for field in ('goal', 'requester', 'beneficiary', 'recipient'):
        if not isinstance(frame[field], str): raise ValueError('Task text required')
    parts = {}; scopes = set()
    for part in frame['output_parts']:
        exact(part, 'part_id scope_id description query_refs')
        if not all(isinstance(part[k], str) and part[k] for k in ('part_id', 'scope_id', 'description')):
            raise ValueError('Part identity required')
        if part['part_id'] in parts: raise ValueError('Duplicate output part')
        refs(part['query_refs'], query_sources)
        parts[part['part_id']] = part; scopes.add(part['scope_id'])
    if not parts: raise ValueError('At least one requested output part required')
    for req in frame['requirements']:
        exact(req, 'text basis query_refs')
        if not isinstance(req['text'], str) or req['basis'] not in {'EXPLICIT', 'CONTEXT_INFERENCE'}:
            raise ValueError('Explicit versus inferred requirement required')
        refs(req['query_refs'], query_sources)
    preferences = []; aliases = {}; covered = set()
    for pref in obj['preferences']:
        exact(pref, 'preference_id source_ids subject kind status scope_note uncertainty')
        refs(pref['source_ids'], sources)
        if pref['status'] not in {'EXPLICIT', 'SUPPORTED_IMPLICIT', 'UNCERTAIN'}:
            raise ValueError('Unknown evidence status')
        for k in ('preference_id', 'subject', 'kind', 'scope_note', 'uncertainty'):
            if not isinstance(pref[k], str): raise ValueError('Preference text required')
        if not pref['preference_id'] or pref['preference_id'] in aliases:
            raise ValueError('Duplicate preference alias')
        identity = {k: v for k, v in pref.items() if k != 'preference_id'}
        identity['source_versions'] = {s: sources[s]['source_version'] for s in pref['source_ids']}
        pid = 'P:' + hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:24]
        aliases[pref['preference_id']] = pid
        preferences.append({**deepcopy(pref), 'preference_id': pid})
        covered.update(pref['source_ids'])
    facts = []
    preference_sources = {s for p in preferences for s in p['source_ids']}
    mixed = set()
    for fact in obj['fact_candidates']:
        exact(fact, 'source_ids task_relation')
        refs(fact['source_ids'], sources)
        if not isinstance(fact['task_relation'], str): raise ValueError('Fact relation required')
        # Mixed text is not granted an unrestricted factual route. It remains
        # auditable and triggers downstream ambiguity handling, not silent trust.
        overlap = set(fact['source_ids']) & preference_sources
        mixed.update(overlap); covered.update(fact['source_ids'])
        facts.append({**deepcopy(fact), 'mixed_preference_source_ids': sorted(overlap)})
    for key in ('uncertain_source_ids', 'unreviewed_source_ids'):
        refs(obj[key], sources, nonempty=False); covered.update(obj[key])
    uses = []
    for proposal in obj['proposed_uses']:
        if proposal.get('preference_id') not in aliases: raise ValueError('Unknown proposed preference')
        normalized = {**proposal, 'preference_id': aliases[proposal['preference_id']]}
        use = use_card(normalized, sources, query_sources, parts, scopes, set(aliases.values()))
        pref = next(p for p in preferences if p['preference_id'] == use['preference_id'])
        if not set(use['source_ids']) <= set(pref['source_ids']):
            raise ValueError('Use cites unrelated preference evidence')
        uses.append(use)
    no_use = []
    for item in obj['no_use']:
        exact(item, 'preference_id reason')
        if item['preference_id'] not in aliases or not isinstance(item['reason'], str) or not item['reason'].strip():
            raise ValueError('Explicit no-use reason required')
        no_use.append({**item, 'preference_id': aliases[item['preference_id']]})
    proposed = {u['preference_id'] for u in uses}; unused = {i['preference_id'] for i in no_use}
    if proposed & unused or proposed | unused != set(aliases.values()) or len(unused) != len(no_use):
        raise ValueError('Every identified preference needs uses or an explicit no-use reason')
    return {'task_frame': deepcopy(frame), 'preferences': preferences, 'fact_candidates': facts,
            'uses': uses, 'no_use': no_use, 'mixed_source_ids': sorted(mixed),
            'uncertain_source_ids': list(obj['uncertain_source_ids']),
            'unreviewed_source_ids': list(dict.fromkeys(obj['unreviewed_source_ids'] + [s for s in sources if s not in covered])),
            'semantic_coverage_verified': False, 'admission_performed': False}
