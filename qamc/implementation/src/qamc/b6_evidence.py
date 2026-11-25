"""B6 canonical provenance and deterministic evidence selection; no store mutation.
Coverage and applicability are model predictions, not semantic truth.
"""
import re
from .common import sha
MODES=set('OBJECTIVE_FACT USER_HISTORY PERSONAL_RECOMMENDATION PERSONAL_PLANNING THIRD_PARTY_WRITING MULTI_SUBJECT_PLANNING OPTION_SELECTION'.split())
KINDS=set('USER_FACT USER_PREFERENCE USER_BELIEF THIRD_PARTY_FACT TASK_CONTEXT HISTORICAL_STATE PLAN_OR_INTENTION ASSISTANT_SUGGESTION WORLD_EVIDENCE UNKNOWN'.split())
USES=set('SUPPORT_USER_FACT SUPPORT_HISTORICAL_FACT SUPPORT_WORLD_FACT RANK_PERSONAL_OPTIONS ADAPT_PERSONAL_PLAN ADAPT_OUTPUT_STYLE SUPPORT_TASK_CONTEXT'.split())
STRATEGIES={'A_task':(0,0,0,0),'B_dual':(1,0,0,0),'C_discriminative':(1,1,0,0),'D_routed':(1,1,1,0),'E_full':(1,1,1,1),'F_adaptive':(1,0,'adaptive',0)}

def query_body(query):return query.split('\n\nChoose the best option')[0].removeprefix('User: ').strip()

def canonical_index(sources,candidates,query):
    units=[];aliases={};body=query_body(query)
    for source in sources:
        text=source['content'];bounds={0,len(text)};duplicate=[]
        if body and (len(body)>=24 or text.strip().removeprefix('User: ')==body):
            for m in re.finditer(re.escape(body),text):duplicate.append((m.start(),m.end()));bounds.update((m.start(),m.end()))
        bounds.update(m.end() for m in re.finditer(r'(?<=[.!?。！？])\s+|\n+',text))
        points=sorted(bounds);local=[]
        for start,end in zip(points,points[1:]):
            if not text[start:end].strip():continue
            uid=f"{source['id']}@{start}:{end}:{sha(text[start:end])[:8]}";dup=any(start>=a and end<=b for a,b in duplicate);role=source.get('role','unknown')
            origin='DUPLICATE_OF_CURRENT_INPUT' if dup else 'SYSTEM_PERSONA_CONTEXT' if role=='system' else 'ASSISTANT_SUGGESTION' if role=='assistant' else 'HISTORICAL_MEMORY'
            units.append({'id':uid,'source_id':source['id'],'start':start,'end':end,'text':text[start:end],'origin':origin,'metadata':{k:v for k,v in source.items() if k not in {'id','content'}}});local.append(uid)
        for i,uid in enumerate(local):
            for alias in (f"{source['id']}:U{i}",f"{source['id']}:{i}"):aliases.setdefault(alias,[]).append(uid)
    by_source={}
    for u in units:by_source.setdefault(u['source_id'],[]).append(u['id'])
    return {'units':units,'candidate_to_units':{c['id']:[uid for sid in c.get('source_ids',[]) for uid in by_source.get(sid,[])] for c in candidates},'unique_aliases':{k:v[0] for k,v in aliases.items() if len(v)==1}}

def normalize_refs(obj,index):
    corrections=[]
    def refs(items):
        for i,value in enumerate(items):
            if value in index['unique_aliases']:items[i]=index['unique_aliases'][value];corrections.append({'from':value,'to':items[i]})
    refs(obj.get('contract',{}).get('recovered_context_units',[]))
    for e in obj.get('evidence',[]):refs(e.get('unit_ids',[]))
    for r in obj.get('source_relations',[]):refs(r.get('unit_ids',[]))
    return corrections

def fields(obj,keys):
    if not isinstance(obj,dict) or set(obj)!=set(keys.split()):raise ValueError('expected fields '+keys)

def validate_annotation(obj,query,index):
    fields(obj,'contract evidence source_relations option_map profile_errors');c=obj['contract']
    fields(c,'modes requester factual_subjects beneficiaries recipient output_regions query_anchors recovered_context_units task_needs preference_needs unresolved_references')
    if not isinstance(c['modes'],list) or not c['modes'] or not set(c['modes'])<=MODES:raise ValueError('invalid task modes')
    for k in ('factual_subjects','beneficiaries','output_regions','query_anchors','recovered_context_units','unresolved_references'):
        if not isinstance(c[k],list) or any(not isinstance(x,str) for x in c[k]):raise ValueError('invalid contract list '+k)
    if not c['query_anchors'] or any(not a.strip() or a not in query for a in c['query_anchors']):raise ValueError('ungrounded contract')
    if not isinstance(c['requester'],str) or (c['recipient'] is not None and not isinstance(c['recipient'],str)) or not c['output_regions']:raise ValueError('invalid participants/regions')
    umap={u['id']:u for u in index['units']}
    if any(x not in umap for x in c['recovered_context_units']):raise ValueError('unproven recovered context')
    needs={}
    for group in ('task_needs','preference_needs'):
        if not isinstance(c[group],list):raise ValueError('invalid needs')
        for n in c[group]:
            fields(n,'id description anchor current_input')
            if not isinstance(n['id'],str) or n['id'] in needs or not isinstance(n['description'],str) or not isinstance(n['current_input'],bool) or not isinstance(n['anchor'],str) or not n['anchor'].strip() or n['anchor'] not in query:raise ValueError('invalid need anchor/ID')
            needs[n['id']]=n
    if not isinstance(obj['evidence'],list):raise ValueError('invalid evidence')
    emap={}
    for e in obj['evidence']:
        fields(e,'id unit_ids kind subject authority temporal scope explicit confidence allowed_uses prohibited_inferences needs applicable_regions beneficiary disclosure interference')
        if not isinstance(e['id'],str) or e['id'] in emap:raise ValueError('duplicate evidence ID')
        if not isinstance(e['unit_ids'],list) or not e['unit_ids'] or any(u not in umap for u in e['unit_ids']):raise ValueError('missing/unknown units')
        if e['kind'] not in KINDS or e['temporal'] not in {'CURRENT','HISTORICAL','PLANNED','UNKNOWN'} or e['confidence'] not in {'HIGH','UNCERTAIN'} or e['authority'] not in {'SELF_REPORT','THIRD_PARTY_REPORT','ASSISTANT','EXTERNAL','UNKNOWN'}:raise ValueError('invalid evidence type')
        if not isinstance(e['explicit'],bool) or type(e['interference']) is not int or e['interference'] not in range(3):raise ValueError('invalid risk')
        if any(not isinstance(e[k],str) for k in ('subject','scope','beneficiary')):raise ValueError('invalid scope')
        if any(not isinstance(e[k],list) for k in ('allowed_uses','prohibited_inferences','applicable_regions','needs')):raise ValueError('invalid evidence list')
        if not set(e['allowed_uses'])<=USES or not set(e['applicable_regions'])<=set(c['output_regions']):raise ValueError('invalid use/region')
        if any(not isinstance(x,str) for x in e['prohibited_inferences']) or e['disclosure'] not in {'NECESSARY','USEFUL','UNNECESSARY','SENSITIVE_UNNECESSARY'}:raise ValueError('invalid disclosure/restriction')
        seen=set()
        for n in e['needs']:
            fields(n,'need_id strength')
            if n['need_id'] not in needs or n['need_id'] in seen or n['strength'] not in {'FULL','PARTIAL'}:raise ValueError('invalid coverage link')
            seen.add(n['need_id'])
        emap[e['id']]=e
    if any(not isinstance(obj[k],list) for k in ('source_relations','option_map','profile_errors')):raise ValueError('invalid relations')
    for r in obj['source_relations']:
        fields(r,'unit_ids relation')
        if len(r['unit_ids'])<2 or any(u not in umap for u in r['unit_ids']) or r['relation'] not in {'CONDITION','COREFERENCE','UPDATE','CONFLICT','CONTRAST'}:raise ValueError('invalid source relation')
    options=set(re.findall(r'\(([a-d])\)',query.lower()));seen=set()
    for m in obj['option_map']:
        fields(m,'option support conflict context unsupported_claims')
        if m['option'] not in options or m['option'] in seen:raise ValueError('mapping absent/duplicate option')
        seen.add(m['option'])
        for k in ('support','conflict','context'):
            if not isinstance(m[k],list) or any(x not in emap for x in m[k]):raise ValueError('invalid option evidence')
        if not isinstance(m['unsupported_claims'],list) or any(not isinstance(s,str) or not s.strip() or s not in query for s in m['unsupported_claims']):raise ValueError('unsupported claim must quote option')
    for p in obj['profile_errors']:
        fields(p,'candidate_id unit_ids')
        if p['candidate_id'] not in index['candidate_to_units'] or not p['unit_ids'] or any(u not in index['candidate_to_units'][p['candidate_id']] for u in p['unit_ids']):raise ValueError('invalid profile error provenance')
    return obj

def allowed_record(e,c,umap,routed):
    uses=set(e['allowed_uses']);reasons=[];units=[umap[u] for u in e['unit_ids']]
    if all(u['origin']=='DUPLICATE_OF_CURRENT_INPUT' for u in units):return set(),['duplicate_current_input']
    if 'SUPPORT_WORLD_FACT' in uses and (e['kind']!='WORLD_EVIDENCE' or e['authority']!='EXTERNAL' or any(u['metadata'].get('role') not in {'tool','external'} for u in units)):
        uses.remove('SUPPORT_WORLD_FACT');reasons.append('no_independent_world_authority')
    if e['kind']=='ASSISTANT_SUGGESTION' or all(u['metadata'].get('role')=='assistant' for u in units):
        removed=uses & {'RANK_PERSONAL_OPTIONS','ADAPT_PERSONAL_PLAN','ADAPT_OUTPUT_STYLE','SUPPORT_USER_FACT'};uses-=removed
        if removed:reasons.append('assistant_not_user_endorsement')
    if 'OBJECTIVE_FACT' in c['modes'] and 'SUPPORT_WORLD_FACT' not in uses:return set(),reasons+['objective_no_historical_proof']
    if routed:
        personal=uses & {'RANK_PERSONAL_OPTIONS','ADAPT_PERSONAL_PLAN'}
        if personal and e['beneficiary'] not in c['beneficiaries']:uses-=personal;reasons.append('beneficiary_mismatch')
        if e['kind']=='USER_PREFERENCE' and e['subject']=='user' and 'user' not in c['beneficiaries']:
            removed=uses & {'RANK_PERSONAL_OPTIONS','ADAPT_PERSONAL_PLAN'};uses-=removed
            if removed:reasons.append('personal_preference_not_group_rule')
        if e['temporal']=='PLANNED':
            removed=uses & {'SUPPORT_USER_FACT','SUPPORT_HISTORICAL_FACT'};uses-=removed
            if removed:reasons.append('intention_not_completed_state')
        if 'THIRD_PARTY_WRITING' in c['modes'] and e['disclosure'] in {'UNNECESSARY','SENSITIVE_UNNECESSARY'}:return set(),reasons+['unnecessary_disclosure']
        if not e['applicable_regions']:return set(),reasons+['no_applicable_region']
        removed={use for use in uses if not use_regions(e,use)}
        uses-=removed
        if removed:reasons.append('no_region_for_personal_use')
    return uses,reasons

def use_regions(e,use):
    regions=list(e['applicable_regions'])
    if e['subject']=='user' and e['kind']=='USER_PREFERENCE' and use in {'RANK_PERSONAL_OPTIONS','ADAPT_PERSONAL_PLAN'}:
        regions=[r for r in regions if r!='group_plan']
    return regions

def routing_triggers(annotation):
    """Original task-contract requirement; no benchmark IDs or outcome labels."""
    c=annotation['contract'];reasons=[]
    if 'OBJECTIVE_FACT' in c['modes']:reasons.append('objective_authority_boundary')
    if 'THIRD_PARTY_WRITING' in c['modes']:reasons.append('recipient_output_boundary')
    if 'MULTI_SUBJECT_PLANNING' in c['modes'] or len(set(c['beneficiaries']))>1:reasons.append('multiple_beneficiaries')
    if len(set(c['output_regions']))>1:reasons.append('multiple_output_regions')
    if any('SUPPORT_WORLD_FACT' in e['allowed_uses'] and (e['kind']!='WORLD_EVIDENCE' or e['authority']!='EXTERNAL') for e in annotation['evidence']):reasons.append('predicted_world_authority_conflict')
    return sorted(set(reasons))

def optimize(annotation,index,strategy='F_adaptive'):
    dual,disc,routed,_=STRATEGIES[strategy];adaptive=(routed=='adaptive');adaptive_reasons=routing_triggers(annotation) if adaptive else [];routed=bool(adaptive_reasons) if adaptive else bool(routed);guarded=adaptive or routed;c=annotation['contract'];umap={u['id']:u for u in index['units']}
    needs=c['task_needs']+(c['preference_needs'] if dual else []);nmap={n['id']:n for n in needs};task={n['id'] for n in c['task_needs']}
    weights={n['id']:3 if n['id'] in task else 2 for n in needs};levels={n['id']:1. if n['current_input'] else 0. for n in needs}
    selected=[];decisions=[];eligible={};tags={};denied_units=set();allowed_units=set()
    if disc:
        for m in annotation['option_map']:
            for role in ('support','conflict'):
                for eid in m[role]:tags.setdefault(eid,set()).add((m['option'],role))
    for e in annotation['evidence']:
        uses,reasons=allowed_record(e,c,umap,guarded);links=[n for n in e['needs'] if n['need_id'] in nmap and (n['need_id'] in task or uses & {'RANK_PERSONAL_OPTIONS','ADAPT_PERSONAL_PLAN','ADAPT_OUTPUT_STYLE'})]
        if not uses or (not links and e['id'] not in tags):
            decisions.append({'evidence_id':e['id'],'action':'EXCLUDE','reasons':reasons or ['no_active_need']})
            if not uses:denied_units.update(e['unit_ids'])
            continue
        allowed_units.update(e['unit_ids'])
        eligible[e['id']]={**e,'effective_uses':sorted(uses),'links':links}
        if reasons:decisions.append({'evidence_id':e['id'],'action':'RESTRICT','reasons':reasons})
    seen_units=set();seen_tags=set()
    while eligible:
        scores=[]
        for eid,e in eligible.items():
            gain=sum(weights[n['need_id']]*max(0,(1. if n['strength']=='FULL' else .5)-levels[n['need_id']]) for n in e['links'])+.6*len(tags.get(eid,set())-seen_tags)
            cost=.04*e['interference']+.00001*sum(len(umap[u]['text']) for u in set(e['unit_ids'])-seen_units)
            scores.append((gain-cost,gain,eid))
        score,gain,eid=sorted(scores,key=lambda x:(-x[0],x[2]))[0]
        if gain<=0:break
        e=eligible.pop(eid);selected.append(e);seen_units.update(e['unit_ids']);seen_tags.update(tags.get(eid,set()))
        for n in e['links']:levels[n['need_id']]=max(levels[n['need_id']],1. if n['strength']=='FULL' else .5)
    selected_units=set(seen_units);relations=[];changed=True;denied_units-=allowed_units;incomplete_units=set()
    while changed:
        changed=False
        for r in annotation['source_relations']:
            refs=set(r['unit_ids'])
            if refs & selected_units:
                if r not in relations:relations.append(r)
                if refs & denied_units:incomplete_units.update(refs & selected_units)
                additions=refs-selected_units-denied_units
                if additions:selected_units|=additions;changed=True
    selected_units={u for u in selected_units if umap[u]['origin']!='DUPLICATE_OF_CURRENT_INPUT'}
    coverage=[]
    for n in needs:
        refs=sorted({u for e in selected for link in e['links'] if link['need_id']==n['id'] for u in e['unit_ids'] if u in selected_units})
        full=any(link['strength']=='FULL' and all(u in selected_units and u not in incomplete_units for u in e['unit_ids']) for e in selected for link in e['links'] if link['need_id']==n['id'])
        status='CURRENT_INPUT' if n['current_input'] else 'SUPPORTED' if full else 'PARTIAL' if refs else 'MISSING'
        coverage.append({'need_id':n['id'],'status':status,'unit_ids':refs,'semantic_status':'predicted_not_verified'})
    evidence=[]
    for u in index['units']:
        if u['id'] not in selected_units:continue
        entry=dict(u)
        if routed:entry['bindings']=[{'kind':e['kind'],'subject':e['subject'],'beneficiary':e['beneficiary'],'uses':[use],'regions':use_regions(e,use),'temporal':e['temporal'],'scope':e['scope'],'prohibited_inferences':e['prohibited_inferences']} for e in selected if u['id'] in e['unit_ids'] for use in e['effective_uses']] or [{'uses':['SUPPORT_TASK_CONTEXT'],'scope':'qualifier only; no independent claim authority'}]
        evidence.append(entry)
    view={'source_evidence':evidence}
    if routed:view['task_scope']={k:c[k] for k in ('modes','beneficiaries','recipient','output_regions')}
    if disc and annotation['option_map']:
        ids={e['id'] for e in selected}
        view['option_evidence']=[{'option':m['option'],**{role:sorted({u for eid in m[role] if eid in ids for e in selected if e['id']==eid for u in e['unit_ids'] if u in selected_units}) for role in ('support','conflict','context')},'unsupported_claims':m['unsupported_claims']} for m in annotation['option_map']]
    triggers=[]
    if any(x['status'] in {'MISSING','PARTIAL'} and x['need_id'] in task for x in coverage):triggers.append('task_evidence_gap')
    if any(r['relation'] in {'UPDATE','CONFLICT'} for r in relations):triggers.append('time_or_preference_conflict')
    if any(x['action']=='RESTRICT' or any('scope' in r or 'group' in r or 'objective' in r for r in x['reasons']) for x in decisions):triggers.append('authority_or_subject_risk')
    if len(view.get('option_evidence',[]))>1:
        signatures=[(tuple(m['support']),tuple(m['conflict'])) for m in view['option_evidence']]
        if len(set(signatures))<len(signatures):triggers.append('ambiguous_option_evidence')
    return view,{'coverage':coverage,'selected_ids':[e['id'] for e in selected],'decisions':decisions,'relations':relations,'verification_triggers':sorted(set(triggers)),'strategy':strategy,'routing_enabled':routed,'scope_guards_enabled':guarded,'routing_triggers':adaptive_reasons,'candidate_units':len(index['units']),'selected_units':len(selected_units)}
