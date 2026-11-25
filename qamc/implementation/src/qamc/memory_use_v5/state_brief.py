"""Structure and provenance checks; not semantic proof of a state."""
FEATURES = set('PERSONAL_RECOMMENDATION PERSONAL_PLANNING USER_HISTORY OBJECTIVE_FACT THIRD_PARTY_WRITING MULTIPLE_SUBJECTS EXPLICIT_OPTIONS POSSIBLE_UPDATE ATTRIBUTED_REPORT PLAN_VS_EVENT NEGATION_OR_EXCEPTION EXACT_COUNT FORMATTING_REQUEST'.split())

def validate_brief(obj, bundle):
    if set(obj) != {'current_requirements', 'state_items', 'relations', 'material_gaps', 'features'}:
        raise ValueError('brief fields')
    for k in obj:
        if not isinstance(obj[k], list): raise ValueError('brief lists required')
    if len(obj['state_items']) > 10 or len(obj['relations']) > 6: raise ValueError('brief item limit')
    allowed = {
        'current_requirements': ({'text','refs'}, {'text','refs'}),
        'state_items': ({'statement','subject','support','refs'}, {'statement','subject','support','refs','qualifier'}),
        'relations': ({'kind','refs','note'}, {'kind','refs','note'}),
        'material_gaps': ({'description','kind'}, {'description','kind'}),
    }
    for group, (required, permitted) in allowed.items():
        for row in obj[group]:
            if not isinstance(row,dict) or not required <= set(row) <= permitted:
                raise ValueError('invalid or answer-bearing nested fields')
            if any(not isinstance(v,str) for k,v in row.items() if k != 'refs'):
                raise ValueError('brief text fields must be strings')
    ids = {s['span_id'] for s in bundle['evidence']}
    query = bundle['query']
    for group in ('current_requirements', 'state_items', 'relations'):
        for row in obj[group]:
            if not isinstance(row, dict) or not isinstance(row.get('refs'), list) or not row['refs']:
                raise ValueError('uncited substantive item')
            for ref in row['refs']:
                if ref not in ids and not (isinstance(ref,str) and ref.startswith('QUERY:') and ref[6:] and ref[6:] in query):
                    raise ValueError('unknown citation')
    for row in obj['state_items']:
        if row.get('support') not in ('DIRECT','SUPPORTED_INFERENCE','UNRESOLVED'): raise ValueError('invalid support')
    for row in obj['relations']:
        if row.get('kind') not in ('COEXIST','SCOPED_UPDATE','CONTRAST','CAUSE_AS_REPORTED','UNRESOLVED'): raise ValueError('invalid relation')
    if not set(obj['features']) <= FEATURES: raise ValueError('unknown feature')
    for row in obj['material_gaps']:
        if not isinstance(row,dict) or row.get('kind') not in ('NOT_IN_E0','UNCERTAIN_RELATION'): raise ValueError('invalid gap')
    if any(k in obj for k in ('answer','recommendation','ranking')): raise ValueError('answer leakage')
    return obj
