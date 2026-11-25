"""Minimal final-answer evidence; no debate, scores or excluded source text."""
from copy import deepcopy


def evidence(table, ids):
    rows = []
    for sid in dict.fromkeys(ids):
        item = table[sid]
        # Original metadata may contain additional text; pass only provenance.
        rows.append({k: deepcopy(item[k]) for k in ('span_id', 'source_id', 'start', 'end',
                     'offset_basis', 'exact_text', 'source_version', 'source_role', 'recorded_at')})
    return rows


def compile_view(payload, sources, organized, decisions):
    uses = {u['use_id']: u for u in organized['uses']}
    if len(decisions) != len(uses) or {d['use_id'] for d in decisions} != set(uses):
        raise ValueError('Every use requires one final decision')
    if any(d['action'] not in {'KEEP', 'OMIT', 'UNRESOLVED'} for d in decisions):
        raise ValueError('Repair must be verified into a new explicit use before compilation')
    allowed = [uses[d['use_id']] for d in decisions if d['action'] == 'KEEP']
    denied_sources = {s for d in decisions if d['action'] != 'KEEP' for s in uses[d['use_id']]['source_ids']}
    allowed_sources = {s for u in allowed for s in u['source_ids']}
    # No-use preferences are also excluded from the unrestricted fact channel.
    preference_sources = {s for p in organized['preferences'] for s in p['source_ids']}
    facts = []; blocked_facts = []
    for item in organized['fact_candidates']:
        for sid in item['source_ids']:
            if sid in preference_sources or sid in denied_sources:
                blocked_facts.append(sid)
            else:
                facts.append(sid)
    permitted = []
    for use in allowed:
        permitted.append({'source_evidence': evidence(sources, use['source_ids']),
            'scope_id': use['scope_id'], 'part_id': use['part_id'], 'target': use['target'],
            'effect': use['effect'], 'conditions': list(use['conditions'])})
    # Mixed approved/denied uses of the same text remain soft semantic control.
    audit = {'blocked_fact_source_ids': sorted(set(blocked_facts)),
             'shared_allowed_and_denied_source_ids': sorted(allowed_sources & denied_sources),
             'unresolved_use_ids': [d['use_id'] for d in decisions if d['action'] == 'UNRESOLVED'],
             'unreviewed_source_ids': organized['unreviewed_source_ids'],
             'semantic_isolation_guaranteed': False}
    view = {'query': payload['query'], 'current_context': deepcopy(payload.get('current_context', [])),
            'query_time': payload.get('query_time'), 'source_facts': evidence(sources, facts),
            'permitted_preference_uses': permitted,
            'evidence_limitations': {'some_fact_candidates_mixed_with_preferences': bool(blocked_facts),
                                     'unresolved_uses': bool(audit['unresolved_use_ids']),
                                     'unreviewed_sources': bool(audit['unreviewed_source_ids'])}}
    return view, audit


def raw_view(payload, sources):
    """Strong baseline retains every provided source, without organization."""
    return {'query': payload['query'], 'current_context': deepcopy(payload.get('current_context', [])),
            'query_time': payload.get('query_time'), 'source_evidence': evidence(sources, sources)}
