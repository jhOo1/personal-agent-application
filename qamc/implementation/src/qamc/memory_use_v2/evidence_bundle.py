"""Build one provenance-preserving E0 from the frozen Gate* output."""
from qamc.b7_projection import source_index, validate_ir, compile_evidence
from qamc.common import sha


def gate_input(case, shared):
    idx = source_index(shared['sources'], shared['candidates'], case['query'])
    payload = {'query': case['query'], 'canonical_units': idx['units'],
               'candidate_to_units': idx['candidate_to_units'],
               'candidate_navigation': [{k: c[k] for k in ('id','kind','text','source_ids') if k in c} for c in shared['candidates']]}
    return idx, payload


def make_bundle(case, shared, idx, ir):
    validate_ir(ir, idx, case['query'])
    _, audit = compile_evidence(ir, idx, case['query'], 12000)
    claims = {x['claim_id']: x for x in ir['claims']}
    units = {x['id']: x for x in idx['units']}
    ids = {u for claim in audit['selected_legal_union'] for u in claims[claim]['source_span_ids']}
    selected = []
    for unit in idx['units']:
        if unit['id'] not in ids or unit['source_id'] == '__current__':
            continue
        if unit.get('origin') == 'DUPLICATE_OF_CURRENT_INPUT':
            continue
        src = next(s for s in shared['sources'] if s['id'] == unit['source_id'])
        text = src['content']
        if text[unit['start']:unit['end']] != unit['text']:
            raise ValueError('source unit offset mismatch')
        selected.append({'span_id': unit['id'], 'source_id': unit['source_id'],
                         'text': unit['text'], 'start': unit['start'], 'end': unit['end'],
                         'carrier_role': unit['metadata'].get('role'),
                         'recorded_at': unit['metadata'].get('recorded_at')})
    # Stable source-order de-duplication; profile aliases are not extra votes.
    unique, seen = [], set()
    for item in selected:
        key = (item['source_id'], item['start'], item['end'])
        if key not in seen:
            unique.append(item); seen.add(key)
    payload = {'query': case['query'], 'current_context': case.get('current_context', []),
               'query_time': case.get('query_time'), 'evidence': unique}
    return {'payload': payload, 'bundle_hash': sha(payload), 'gate_audit': audit}
