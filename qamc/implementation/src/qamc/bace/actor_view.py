"""Compile only explicit fact spans and admitted preference uses.

Fact admission and semantic boundaries remain predicted. This compiler does not
claim hard semantic isolation, and never promotes scope.task_unit_ids to facts.
"""
from copy import deepcopy
from .contract import generation_input,require_context_boundary


def compile_view(payload, scopes, facts, decisions):
    payload=generation_input(payload)
    units={u['unit_id']:u for u in payload['units']}
    scope_ids={s['scope_id'] for s in scopes['scopes']}
    facts_out=[]; permitted=[]; restricted=[]
    denied=[]
    for decision in decisions:
        key=decision['key']; span=require_context_boundary(decision['span'],units)
        if key.unit_id!=span.unit_id or key.scope_id not in scope_ids:
            raise ValueError('Decision span or scope mismatch')
        if decision['action'] not in {'ALLOW','LIMITED','DENY_THIS_USE','REVIEW'}:
            raise ValueError('Invalid decision')
        if decision['action'] in {'DENY_THIS_USE','REVIEW'}:
            denied.append(span)
            # Do not re-inject the forbidden quote or free-form role rationale.
            restricted.append({'unit_id':key.unit_id,'scope_id':key.scope_id,
                               'use_kind':key.use_kind,'action':decision['action']})
            continue
        u=units[key.unit_id]
        if key.unit_id=='Q0' or u.get('modality')=='current_input':
            raise ValueError('Current request cannot be historical preference evidence')
        if decision['action']=='LIMITED' and not decision.get('revalidation_passed',False):
            raise ValueError('LIMITED requires recorded bilateral revalidation')
        if decision.get('current_status') in {'SUPPRESSED','EXPIRED'} and key.use_kind!='USER_HISTORY':
            raise ValueError('Inactive preference cannot silently regain current force')
        permitted.append({'unit_id':key.unit_id,'scope_id':key.scope_id,'use_kind':key.use_kind,
                          'source_id':u['source_id'],'start':u['start']+span.start,
                          'end':u['start']+span.end,'exact_quote':span.exact_quote,
                          'action':decision['action'],'boundary':decision.get('boundary','')})
    for fact in facts:
        span=require_context_boundary(fact['span'],units)
        if fact['kind'] not in {'OBJECTIVE_TASK_FACT','USER_SPECIFIC_FACT','HISTORICAL_BACKGROUND'}:
            raise ValueError('Preference is not an independently admitted task fact')
        if fact['scope_id'] not in scope_ids:
            raise ValueError('Unknown fact scope')
        if span.unit_id=='Q0':
            continue  # Original query is already always present.
        overlap=any(s.unit_id==span.unit_id and max(s.start,span.start)<min(s.end,span.end) for s in denied)
        if overlap and (fact['kind']!='HISTORICAL_BACKGROUND' or not fact.get('background_only_verified')):
            raise ValueError('Mixed denied preference needs narrower fact span or explicit background review')
        u=units[span.unit_id]
        facts_out.append({'unit_id':span.unit_id,'scope_id':fact['scope_id'],'kind':fact['kind'],
                          'source_id':u['source_id'],'start':u['start']+span.start,
                          'end':u['start']+span.end,'exact_quote':span.exact_quote,
                          'background_only':bool(overlap)})
    visible={x['source_id'] for x in facts_out+permitted}
    return {'query':payload['query'],'current_context':deepcopy(payload.get('current_context',[])),
            'query_time':payload.get('query_time'),'scopes':deepcopy(scopes['scopes']),
            'source_facts':facts_out,'permitted_preference_uses':permitted,
            'restricted_uses':restricted,
            'source_metadata':{k:deepcopy(v) for k,v in payload.get('source_metadata',{}).items() if k in visible}}
