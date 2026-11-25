"""Validate compact JSON contracts before any score-based routing."""
from .contract import UseKey,Span,Assessment,USES


def exact_fields(obj,fields):
    if not isinstance(obj,dict) or set(obj)!=set(fields.split()):
        raise ValueError('Expected exact fields: '+fields)


def key_from(x):return UseKey(x['unit_id'],x['scope_id'],x['use_kind'])


def span_from(x,units):
    exact_fields(x,'unit_id start end exact_quote')
    return Span(**x).validate(units)


def validate_inventory(obj,payload,scopes):
    exact_fields(obj,'uses necessary_facts evidence_gaps')
    units={u['unit_id']:u for u in payload['units']};scope_ids={s['scope_id'] for s in scopes}
    if not isinstance(obj['uses'],list) or len(obj['uses'])>12:
        raise ValueError('At most 12 material proposed uses')
    seen=set()
    for x in obj['uses']:
        exact_fields(x,'unit_id scope_id use_kind query_anchor source_span')
        k=key_from(x)
        if k in seen or k.unit_id not in units or k.scope_id not in scope_ids:
            raise ValueError('Duplicate or unknown UseKey')
        seen.add(k)
        question=payload['query'].split('\n\nChoose the best option')[0].split("I'm trying to decide on this")[0]
        if not isinstance(x['query_anchor'],str) or not x['query_anchor'] or len(x['query_anchor'])>240 or x['query_anchor'] not in question:
            raise ValueError('Query anchor must be exact')
        span=span_from(x['source_span'],units)
        if span.unit_id!=k.unit_id:raise ValueError('Use span must cite own unit')
        if k.unit_id=='Q0':raise ValueError('Current request is not a historical preference')
    if not isinstance(obj['necessary_facts'],list) or len(obj['necessary_facts'])>16:
        raise ValueError('At most 16 necessary fact clauses')
    for fact in obj['necessary_facts']:
        exact_fields(fact,'scope_id kind source_span reason')
        if fact['scope_id'] not in scope_ids or fact['kind'] not in {'OBJECTIVE_TASK_FACT','USER_SPECIFIC_FACT','HISTORICAL_BACKGROUND'}:
            raise ValueError('Invalid fact scope or type')
        span_from(fact['source_span'],units)
        if not isinstance(fact['reason'],str) or len(fact['reason'])>400:
            raise ValueError('Fact justification must be bounded')
    if not isinstance(obj['evidence_gaps'],list) or any(not isinstance(g,str) for g in obj['evidence_gaps']):
        raise ValueError('Explicit gap list required')
    return obj


def validate_assessments(obj,role,payload,scopes,inventory):
    exact_fields(obj,'assessments')
    wanted={key_from(x) for x in inventory};seen=set();result=[]
    units={u['unit_id']:u for u in payload['units']};scope_ids={s['scope_id'] for s in scopes}
    for x in obj['assessments']:
        exact_fields(x,'unit_id scope_id use_kind status raw_score evidence reason uncertainty hard_conflict_claimed finding')
        k=key_from(x)
        if k not in wanted or k in seen:raise ValueError('Unexpected or repeated assessment')
        seen.add(k)
        if type(x['hard_conflict_claimed']) is not bool:raise ValueError('Boolean conflict claim required')
        allowed={'POSITIVE_SUPPORT','NO_POSITIVE_SUPPORT','UNCERTAIN'} if role=='allow' else {'CONCRETE_RISK','NO_CONCRETE_VIOLATION_FOUND','UNCERTAIN'}
        if x['finding'] not in allowed:raise ValueError('Invalid role finding')
        spans=tuple(span_from(s,units) for s in x['evidence'])
        a=Assessment(k,role,x['status'],x['raw_score'],spans,x['reason'],x['uncertainty'],x['hard_conflict_claimed'])
        a.validate(units,scope_ids)
        if len(a.reason)>600 or len(a.uncertainty)>400:raise ValueError('Keep evidence rationale short')
        result.append(a)
    if seen!=wanted:raise ValueError('Every supplied use needs ASSESSED or explicit UNASSESSED')
    return result
