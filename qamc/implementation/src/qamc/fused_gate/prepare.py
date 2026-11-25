"""Deterministic development inputs; labels never enter public adapters."""
import json,hashlib,re
from collections import Counter
from dataclasses import asdict
from difflib import SequenceMatcher
from pathlib import Path
from qamc.common import sha
from qamc.pa.core import digest,rpeval_public
from qamc.pa.adapters import benchpres_public,prefeval_public
from qamc.pa.prepare import write_once
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'reports/qamc_fused_gate';RUN=ROOT/'runs/qamc_fused_gate'
def filehash(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def norm(s):return ''.join(re.findall(r'\w',s.casefold()))
def similar(a,b):
    a,b=norm(a),norm(b)
    sm=SequenceMatcher(None,a,b,autojunk=False)
    if sm.real_quick_ratio()<.72 or sm.quick_ratio()<.72:return 0.
    return sm.ratio()

def prepare():
    import pyarrow.parquet as pq
    OUT.mkdir(exist_ok=True);cases=[];reserved=[];historical_strings=set();historical_queries=set();scanned={};errors=[]
    # Scan metadata rather than repeatedly importing potentially private raw streams.
    paths=[p for p in (ROOT/'reports').rglob('*.json') if 'manifest' in p.name.lower() and 'qamc_fused_gate' not in str(p)]
    paths += [ROOT/'reports/qamc_pa_v1/SMOKE_PLAN.json',ROOT/'reports/qamc_pa_v2/PLAN.json']
    def visit(v):
        if isinstance(v,str):historical_strings.add(v)
        elif isinstance(v,list):
            for x in v:visit(x)
        elif isinstance(v,dict):
            for k,x in v.items():
                if k in ('query','question') and isinstance(x,str):historical_queries.add(x)
                visit(x)
    for path in sorted(set(paths)):
        try:visit(json.loads(path.read_text()));scanned[str(path.relative_to(ROOT))]=filehash(path)
        except (ValueError,UnicodeError) as e:errors.append({'path':str(path.relative_to(ROOT)),'error':str(e)})
    prior_cases=[]
    for p in (ROOT/'reports/qamc_pa_v1/SMOKE_PLAN.json',ROOT/'reports/qamc_pa_v2/PLAN.json'):
        prior_cases+=json.loads(p.read_text())['cases']
    for c in prior_cases:historical_queries.add(json.loads((ROOT/c['public_path']).read_text())['query'])
    chosen_queries=[]
    def nearest(q,others):return max((similar(q,x) for x in others),default=0.)
    def add(bench,path,index,task,ref,metadata,split='dev'):
        qhash=digest(norm(task.query));item={'uid':task.uid,'benchmark':bench,'source_file':str(path.relative_to(ROOT)),'source_sha256':filehash(path),'row_index':index,'query_lineage_hash':qhash,**metadata}
        if split=='reserved':reserved.append(item);return
        token=digest(task.uid)[:24];pub=RUN/'public'/(token+'.json');ev=RUN/'evaluation_only'/(token+'.json')
        write_once(pub,asdict(task));write_once(ev,ref)
        item.update(public_path=str(pub.relative_to(ROOT)),public_hash=digest(asdict(task)),evaluation_path=str(ev.relative_to(ROOT)),evaluation_hash=digest(ref),exposure='DEVELOPMENT_ONLY')
        cases.append(item)
    # Official RPEval records preserve their original joint persona/label structure.
    rp=ROOT/'literature/qamc_pa_v1/RPEval/benchmark_dataset'
    for split in ('dev','reserved'):
        for mode,kind in [('explicit_preference','single'),('implicit_preference','single'),('explicit_preference','multi'),('implicit_preference','multi')]:
            path=rp/mode/(kind+'_testset.json');rows=json.loads(path.read_text());n=0
            for i,row in sorted(enumerate(rows),key=lambda z:digest(['fused-prefix-v1',split,mode,kind,z[0]])):
                q=row['question'];near=nearest(q,historical_queries|set(chosen_queries))
                if near>=.72:continue
                task=rpeval_public(row,f'rpeval/fused/{mode}/{kind}/{i}',implicit=mode.startswith('implicit'))
                add('rpeval',path,i,task,row,{'track':mode+'/'+kind,'nearest_detected_historical_or_selected_similarity':near,'independent_confirmation':False},split)
                chosen_queries.append(q);n+=1
                if n==2:break
            if n<2:raise ValueError('Insufficient original RPEval query roots for '+mode+'/'+kind)
    # BenchPreS deliberately reuses historical development profiles, never claims new users.
    path=ROOT/'literature/bace_20261105/benchpres_test-00000-of-00001.parquet';rows=pq.read_table(path).to_pylist()
    old=json.loads((ROOT/'reports/qamc_bace_v2/DATA_MANIFEST_V2.json').read_text())
    excluded={c['row_index'] for c in prior_cases if c['benchmark']=='benchpres'}
    source=[x for x in old['phases']['opt'] if x['benchmark']=='benchpres' and x['row_index'] not in excluded]
    counts=Counter();picked=[]
    for ceiling in (1,2,3):
        for x in sorted(source,key=lambda x:digest(['fused-bench-v1',x['uid']])):
            if x in picked or counts[x['profile_root']]>=ceiling:continue
            picked.append(x);counts[x['profile_root']]+=1
            if len(picked)==8:break
        if len(picked)==8:break
    if len(picked)!=8:raise ValueError('Insufficient old development tasks')
    for x in picked:
        row=rows[x['row_index']];task=benchpres_public(row['prompt'],x['uid'])
        add('benchpres',path,x['row_index'],task,{k:row[k] for k in ('preference_attribute','preference_label')},{'track':'full_public_profile','profile_root':x['profile_root'],'context_root':x.get('context_root'),'prior_exposure':'KNOWN_OLD_DEVELOPMENT_PROFILE_AND_TASK','independent_confirmation':False})
    # Reserve identifiers from the prior selection split; no answers are loaded/run.
    reserved += [{'uid':x['uid'],'benchmark':'benchpres','row_index':x['row_index'],'profile_root':x['profile_root'],'prior_exposure':'KNOWN_HISTORICALLY_EXPOSED_NOT_UNSEEN_USER'} for x in old['phases'].get('select',[]) if x['benchmark']=='benchpres'][:8]
    # PrefEval intentionally uses the old development allocation. Manifest-wide
    # planning is not equated with fresh unseen data or actual prior dispatch.
    upstream=ROOT/'vendor/PrefEval'
    prior_pa_queries={json.loads((ROOT/c['public_path']).read_text())['query'] for c in prior_cases if c['benchmark']=='prefeval'}
    old_pref=[x for x in old['phases']['opt'] if x['benchmark']=='prefeval']
    topics=set();count=0
    for x in sorted(old_pref,key=lambda x:digest(['fused-pref-olddev-v1',x['uid']])):
        if x['topic'] in topics:continue
        path=upstream/'benchmark_dataset/implicit_preference/persona-driven'/(x['topic']+'.json')
        rows=json.loads(path.read_text());i=x['index'];row=rows[i];q=row['question']
        if digest(q.strip())!=x['question_hash']:raise ValueError('PrefEval original query identity mismatch')
        near=nearest(q,prior_pa_queries|set(chosen_queries))
        if near>=.72:continue
        task,native=prefeval_public(row,f"prefeval/fused/persona/{x['topic']}/{i}",upstream)
        add('prefeval',path,i,task,{'question':q,'preference':row['preference']},{'track':'implicit_persona_generation_0_interturn_300_words','base_question_hash':digest(q.strip()),'base_pair_id':x['pair_id'],'root_group':x['root_group'],'topic':path.stem,'native_messages_hash':digest(native),'nearest_detected_pa_or_selected_similarity':near,'prior_exposure':'KNOWN_OLD_DEVELOPMENT_ALLOCATION','independent_confirmation':False})
        chosen_queries.append(q);topics.add(x['topic']);count+=1
        if count==8:break
    if count!=8:raise ValueError('Insufficient old PrefEval development roots')
    reserved += [{'uid':x['uid'],'benchmark':'prefeval','base_question_hash':x['question_hash'],'base_pair_id':x['pair_id'],'root_group':x['root_group'],'prior_exposure':x.get('exposure_status','UNKNOWN'),'independent_confirmation':False} for x in old['phases'].get('select',[]) if x['benchmark']=='prefeval'][:8]
    if len(cases)!=24:raise ValueError('Manifest size')
    audit={'scanned_manifest_files':scanned,'scan_errors':errors,'historical_query_strings':len(historical_queries),'historical_metadata_strings':len(historical_strings),'scope':'repository report manifests and previous PA public inputs; not a proof of complete global historical exposure','normalization':'Unicode word characters casefold','near_duplicate_rule':'SequenceMatcher>=0.72; no semantic independence certificate','human_review':0,'new_calls':0}
    write_once(OUT/'EXPOSURE_AUDIT.json',audit);write_once(OUT/'RESERVED_IDENTITIES.json',reserved)
    result={'cases':cases,'arms':['G0','R0','S0','V0','F0'],'nominal_requests':680,'user_request_count_ceiling':None,'old_cumulative_limit_applies':False,'finite_dispatch_guard':1360,'guard_reason':'maximum two physical attempts per nominal operation for existing content-free 429 handling; not a spending quota','no_automatic_confirmation':True,'selection_uses_model_results':False,'data_selection_seed':'fused-prefix-v1'}
    write_once(OUT/'INPUTS.json',result);return result
if __name__=='__main__':print(json.dumps({'cases':len(prepare()['cases']),'new_calls':0}))
