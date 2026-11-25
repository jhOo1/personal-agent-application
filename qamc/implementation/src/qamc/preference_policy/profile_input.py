"""Correct shared input: retain frozen Profile navigation and raw provenance.

No Writer/Store/Retriever changes. Status annotations are existing predictions,
not authority guarantees. Current-query duplicates are not historical preferences.
"""
from copy import deepcopy
from qamc.b6_evidence import canonical_index,query_body
from qamc.common import sha,canonical
from .core import actor_view as raw_actor_view

LEGEND='Stored Profile annotations are navigation derived by the frozen Writer, not independent evidence or guaranteed semantic truth. An active record may describe a past event; suppressed current-state records may remain valid historical facts. Check raw source, subject, scope, conditions and explicit updates. Message ordinal is conversation order, not necessarily event time. Current-input-only facets do not establish a prior preference.'


def build(case,shared):
    if case['benchmark']=='benchpres':
        sources=deepcopy(case['history']);candidates=[];profile=[];retrieved=[]
    else:
        if shared['top_k']!=24 or len(shared['retrieved_ids'])>24:raise ValueError('fixed top24 required')
        legal={s['id']:s for s in case['history']}
        if any(legal.get(s['id'])!=s for s in shared['sources']):raise ValueError('source outside legal prefix')
        sources=deepcopy(shared['sources']);candidates=deepcopy(shared['candidates']);profile=deepcopy(shared['profile']);retrieved=list(shared['retrieved_ids'])
    idx=canonical_index(sources,candidates,case['query']);ordinal={s['id']:i for i,s in enumerate(case['history'])}
    units=[];source_table={};by_source={};duplicates=set();body=query_body(case['query'])
    for s in sources:
        content=s['content'].strip().removeprefix('User: ').strip()
        if body and content==body:duplicates.add(s['id'])
        source_table[s['id']]={'carrier':s.get('role','unknown'),'recorded_at':s.get('recorded_at'),
            'message_ordinal':ordinal[s['id']],'origin':'CURRENT_INPUT_DUPLICATE'if s['id']in duplicates else'OFFICIAL_PROFILE'if case['benchmark']=='benchpres'else'HISTORICAL_SOURCE'}
    aliases={}
    for u in idx['units']:
        if u['origin']=='DUPLICATE_OF_CURRENT_INPUT'or u['text'].strip().lower()in {'user:','assistant:','system:'}:continue
        src=next(s for s in sources if s['id']==u['source_id'])
        if src['content'][u['start']:u['end']]!=u['text']:raise ValueError('source offset mismatch')
        uid=f'U{len(units)+1}';aliases[uid]=u['id'];by_source.setdefault(u['source_id'],[]).append(uid)
        units.append({'unit_id':uid,'source_id':u['source_id'],'start':u['start'],'end':u['end'],
            'exact_text':u['text'],'carrier':src.get('role','unknown'),'memory_version':sha(src),
            'attributed_author':None,'subject':'unknown','time':src.get('recorded_at'),'modality':'unknown'})
    # A current reference is explicit, never counted as additional historical memory.
    task_request=case['query'].split('\n\nChoose the best option')[0]
    units.append({'unit_id':'Q0','source_id':'__current__','start':0,'end':len(task_request),
        'exact_text':task_request,'carrier':'user','memory_version':sha(case['query']),
        'attributed_author':None,'subject':'unknown','time':case.get('query_time'),'modality':'current_input'})
    source_table['__current__']={'carrier':'user','recorded_at':case.get('query_time'),'origin':'CURRENT_INPUT','message_ordinal':None}
    for sid,meta in source_table.items():
        meta['unit_ids']=['Q0'] if sid in duplicates or sid=='__current__' else list(by_source.get(sid,[]))
    navigation=[]
    for f in profile:
        refs=list(f.get('source_refs',[]));known=[s for s in refs if s in source_table]
        current=bool(refs)and all(s in duplicates for s in refs)
        ids=[uid for sid in known for uid in (['Q0'] if sid in duplicates else by_source.get(sid,[]))]
        if current:continue
        navigation.append({'facet_ref':f'F{len(navigation)+1}','value':f.get('value'),
            'predicted_subject':f.get('subject'),'attribute':f.get('attribute'),'predicted_scope':f.get('scope'),
            'predicted_semantic_type':f.get('semantic_type'),'stored_pool':f.get('pool'),
            'stored_status_reason':f.get('status_reason'),'valid_from':f.get('valid_from'),'valid_to':f.get('valid_to'),
            'source_kind':f.get('source_kind'),'source_ids':known,
            'source_coverage':'COMPLETE_IN_R'if len(known)==len(refs)else'PARTIAL_IN_R',
            'origin':'CURRENT_INPUT_ONLY'if current else'FROZEN_DERIVED_PROFILE'})
    p={'query':case['query'],'current_context':deepcopy(case.get('current_context',[])),
        'query_time':case.get('query_time'),'units':units,'source_metadata':source_table,
        'profile_navigation':navigation,'annotation_legend':LEGEND}
    return {'payload':p,'input_hash':sha(p),'source_hash':sha(sources),'candidate_hash':sha(candidates),
        'profile_hash':sha(shared.get('profile',[])),'retrieved_ids':retrieved,'detailed_k':len(retrieved),
        'unit_aliases':aliases,'official_profile_complete':case['benchmark']=='benchpres'}


def wire(value):
    """Reduce repeated per-unit metadata without dropping any source text."""
    if isinstance(value,list):return [wire(v)for v in value]
    if not isinstance(value,dict):return value
    if {'unit_id','source_id','exact_text','start','end'}<=value.keys():
        return {k:deepcopy(value[k])for k in ['unit_id','source_id','start','end','exact_text']}
    return {k:wire(v)for k,v in value.items()}


def actor_view(payload,scope,decisions,gaps):
    view=raw_actor_view(payload,scope,decisions,gaps)
    view['source_evidence']=[u for u in view['source_evidence']if u['source_id']!='__current__']
    selected={u['source_id']for u in view['source_evidence']}
    view['source_metadata']={sid:v for sid,v in payload['source_metadata'].items()if sid in selected}
    annotations=[]
    for f in payload['profile_navigation']:
        if set(f['source_ids'])&selected:
            # Do not re-inject excluded facet value text through annotations.
            annotations.append({k:deepcopy(f[k])for k in ['facet_ref','predicted_subject','attribute','predicted_scope','predicted_semantic_type','stored_pool','stored_status_reason','valid_from','valid_to','source_kind','source_ids','origin']})
    view['selected_record_annotations']=annotations
    view['scopes']=deepcopy(scope['scopes']);view['annotation_legend']=payload['annotation_legend']
    return view
