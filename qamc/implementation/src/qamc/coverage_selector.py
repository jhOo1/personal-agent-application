"""Source-unit selection and coverage metadata for B5; no storage mutation."""
import re
from .common import ROOT, token_estimate

KINDS={'REQUIRED','USEFUL_PERSONALIZATION'}
ATTR={'PERSONAL_FACT','SELF_PREFERENCE','USER_BELIEF','TASK_EVIDENCE','OTHER'}
REASONS={'UNRELATED','SUBJECT_MISMATCH','WRONG_ENTITY','SUPERSEDED','UNSUPPORTED_WORLD_CLAIM'}


def source_units(sources, query):
    """Split into exact sentence/paragraph slices; do not turn current query into history."""
    units=[]
    query_head=query.split('\n\nChoose the best option')[0].removeprefix('User: ').strip()
    for source in sources:
        content=source['content']
        if len(query_head)>100 and query_head in content:
            continue
        start=0; index=0
        for match in re.finditer(r'(?<=[.!?。！？])\s+|\n+',content):
            end=match.end()
            if content[start:end].strip():
                units.append({'id':f"{source['id']}:U{index}",'source_id':source['id'],'start':start,'end':end,'text':content[start:end]});index+=1
            start=end
        if content[start:].strip():units.append({'id':f"{source['id']}:U{index}",'source_id':source['id'],'start':start,'end':len(content),'text':content[start:]})
    return units


def check(result,query,candidates,units):
    if not isinstance(result,dict) or set(result)!={'task_frame','needs','selected','excluded','coverage'}:raise ValueError('invalid top-level fields')
    frame=result['task_frame']
    if not isinstance(frame,dict) or set(frame)!={'target','target_anchor','recipient_anchor'} or frame['target'] not in {'user','group','other','world','unknown'} or not isinstance(frame['target_anchor'],str) or not frame['target_anchor'].strip() or frame['target_anchor'] not in query:raise ValueError('invalid frame')
    if frame['recipient_anchor'] is not None and (not isinstance(frame['recipient_anchor'],str) or frame['recipient_anchor'] not in query):raise ValueError('invalid recipient anchor')
    if not all(isinstance(result[k],list) for k in ('needs','selected','excluded','coverage')):raise ValueError('expected lists')
    needs={}
    for n in result['needs']:
        if not isinstance(n,dict) or set(n)!={'id','kind','description','anchor'} or n['kind'] not in KINDS or not isinstance(n['id'],str) or n['id'] in needs or not isinstance(n['description'],str) or len(n['description'])>180 or not isinstance(n['anchor'],str) or not n['anchor'].strip() or n['anchor'] not in query:raise ValueError('invalid need')
        needs[n['id']]=n
    lookup={c['id']:c for c in candidates};umap={u['id']:u for u in units};selected={}
    for e in result['selected']:
        required={'candidate_id','channel','need_ids','source_units','related_units','attribution','scope_status','temporal_relation','recipient_applicable'}
        if not isinstance(e,dict) or set(e)!=required or e['candidate_id'] not in lookup or e['candidate_id'] in selected:raise ValueError('invalid candidate')
        if e['channel'] not in {'TASK_SUPPORT','PERSONALIZATION'} or e['attribution'] not in ATTR or e['scope_status'] not in {'APPLICABLE','LIMITED','UNCERTAIN'} or e['temporal_relation'] not in {'CURRENT','HISTORICAL','PLANNED','UNRESOLVED'} or not isinstance(e['recipient_applicable'],bool):raise ValueError('invalid attribution')
        if not isinstance(e['need_ids'],list) or not e['need_ids'] or any(x not in needs for x in e['need_ids']):raise ValueError('invalid need reference')
        if not isinstance(e['source_units'],list) or not e['source_units'] or not isinstance(e['related_units'],list):raise ValueError('missing units')
        for u in e['source_units']+e['related_units']:
            if u not in umap or umap[u]['source_id'] not in lookup[e['candidate_id']].get('source_ids',[]):raise ValueError('unlinked unit')
        selected[e['candidate_id']]=e
    for e in result['excluded']:
        if not isinstance(e,dict) or set(e)!={'candidate_id','reason_code'} or e['candidate_id'] not in lookup or e['candidate_id'] in selected or e['reason_code'] not in REASONS:raise ValueError('invalid exclusion')
    seen=set()
    for c in result['coverage']:
        if not isinstance(c,dict) or set(c)!={'need_id','selected_ids','status'} or c['need_id'] not in needs or c['need_id'] in seen or c['status'] not in {'SUPPORTED','PARTIAL','MISSING'} or not isinstance(c['selected_ids'],list) or any(i not in selected or c['need_id'] not in selected[i]['need_ids'] for i in c['selected_ids']) or (c['status']=='MISSING' and c['selected_ids']) or (c['status']!='MISSING' and not c['selected_ids']):raise ValueError('invalid coverage')
        seen.add(c['need_id'])
    if seen!=set(needs):raise ValueError('coverage incomplete')
    return result


def admitted_view(result,candidates,sources,units):
    """Apply predicted attributes locally; keep only source-backed units."""
    umap={u['id']:u for u in units}; smap={s['id']:s for s in sources};cmap={c['id']:c for c in candidates}; table=[];lookup={}; excluded=[]; admitted=set()
    frame=result['task_frame']
    for e in result['selected']:
        reason=None
        if frame['target']=='world' and e['attribution'] in {'USER_BELIEF','SELF_PREFERENCE'}:reason='world_fact_not_personal_opinion'
        elif frame['target'] in {'group','other'} and e['attribution']=='SELF_PREFERENCE' and e['scope_status']!='APPLICABLE':reason='target_scope_unproven'
        elif frame['recipient_anchor'] is not None and e['channel']=='PERSONALIZATION' and not e['recipient_applicable']:reason='recipient_scope_unproven'
        if reason:excluded.append({'candidate_id':e['candidate_id'],'reason':reason});continue
        admitted.add(e['candidate_id'])
        for uid in e['source_units']+e['related_units']:
            u=umap[uid];sid=u['source_id']
            if sid not in lookup:
                lookup[sid]=len(table);src=smap[sid];table.append({'source_id':sid,'quotes':[],'source_metadata':{k:src[k] for k in ('role','speaker','recorded_at','session_id') if k in src},'memory_metadata':[]})
            entry=table[lookup[sid]]
            if u['text'] not in entry['quotes']:entry['quotes'].append(u['text'])
            if not any(x['memory_id']==e['candidate_id'] for x in entry['memory_metadata']):
                meta=cmap[e['candidate_id']].get('metadata') or {};entry['memory_metadata'].append({'memory_id':e['candidate_id'],**{k:meta[k] for k in ('subject','scope','recorded_at','valid_from','valid_to','pool','status_reason') if k in meta}})
    coverage=[]
    for c in result['coverage']:
        ids=[i for i in c['selected_ids'] if i in admitted];coverage.append({**c,'selected_ids':ids,'status':c['status'] if ids else 'MISSING'})
    return {'source_evidence':table},{'program_excluded':excluded,'admitted_coverage':coverage,'units':[{**u,'original_span':u['text'],'final_span':u['text'],'expansion_reason':'full source unit preserves local sentence','added_tokens_estimate':0} for u in units if any(u['id'] in e['source_units']+e['related_units'] for e in result['selected'] if e['candidate_id'] in admitted)]}


class CoverageSelector:
    def __init__(self,gateway):self.gateway=gateway;self.prompt=(ROOT/'prompts/coverage_selector.md').read_text()
    def select(self,query,context,profile,candidates,sources,key):
        units=source_units(sources,query)
        # Do not present source text twice: all quotes are represented by exact units.
        payload={'query':query,'current_context':context,'profile':profile,'candidates':[{'id':c['id'],'kind':c['kind'],'text':c['text'],'source_ids':c['source_ids'],'metadata':c.get('metadata',{})} for c in candidates],'source_units':units}
        result=self.gateway.object(key,self.prompt,payload,lambda x:check(x,query,candidates,units),8192)
        view,detail=admitted_view(result,candidates,sources,units)
        return result,view,detail
