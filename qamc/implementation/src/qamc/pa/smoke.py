"""Deterministic development-only Smoke manifest. No model requests."""
from dataclasses import asdict
from difflib import SequenceMatcher
from pathlib import Path
import json
import hashlib
import re
from .core import rpeval_public, digest
from .adapters import benchpres_public, prefeval_public
from .prepare import ROOT, OUT, RUN, write_once, prepare_regression


def normalized(s): return ''.join(re.findall(r'\w',s.casefold()))


def near_score(a,b):
    a,b=normalized(a),normalized(b)
    if a==b:return 1.0
    return SequenceMatcher(None,a,b,autojunk=False).ratio()


def prepare_smoke():
    import pyarrow.parquet as pq
    regression=prepare_regression();cases=list(regression['cases'])
    old=json.loads((ROOT/'reports/qamc_bace_v2/DATA_MANIFEST_V2.json').read_text())
    development=[]; diagnostics=[]
    def add(benchmark,path,index,task,reference,track,extra=None):
        token=digest(task.uid)[:24]
        pub=RUN/'smoke/public'/(token+'.json');ev=RUN/'smoke/evaluation_only'/(token+'.json')
        write_once(pub,asdict(task));write_once(ev,reference)
        item={'uid':task.uid,'benchmark':benchmark,'source_file':str(path.relative_to(ROOT)),
              'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'row_index':index,
              'public_path':str(pub.relative_to(ROOT)),'public_hash':digest(asdict(task)),
              'evaluation_path':str(ev.relative_to(ROOT)),'evaluation_hash':digest(reference),
              'exposure':'DEVELOPMENT_ONLY','independent_confirmation':False,'track':track}
        if extra:item.update(extra)
        development.append(item)

    # Two additional old development BenchPreS contexts, no label-based choice.
    benchpath=ROOT/'literature/bace_20261105/benchpres_test-00000-of-00001.parquet'
    rows=pq.read_table(benchpath).to_pylist();excluded={r['row_index'] for r in cases if r['benchmark']=='benchpres'}
    chosen=sorted([r for r in old['phases']['opt'] if r['benchmark']=='benchpres' and r['row_index'] not in excluded],key=lambda r:digest(['pa-smoke',r['uid']]))[:2]
    for item in chosen:
        i=item['row_index'];row=rows[i];task=benchpres_public(row['prompt'],item['uid'])
        add('benchpres',benchpath,i,task,{k:row[k] for k in ('preference_attribute','preference_label')},'full_public_profile',{'profile_root':item['profile_root']})

    # Three generation-pool roots outside exact/near official query overlaps.
    rp=ROOT/'literature/qamc_pa_v1/RPEval';poolpath=rp/'data_generation/data.json'
    pool=json.loads(poolpath.read_text())
    official_questions=sorted({r['question'] for p in (rp/'benchmark_dataset').glob('*/*.json') for r in json.loads(p.read_text())})
    selected_q=[]
    for i in sorted(range(len(pool)),key=lambda i:digest(['pa-smoke-rp',i])):
        row=pool[i];nearest=max(near_score(row['question'],q) for q in official_questions+selected_q)
        if nearest>=0.72:continue
        candidates=[(text,label) for field,label in [('ignore','A'),('supportive','B'),('dominant','C')] for text in row[field]]
        if not candidates or {label for _,label in candidates}!={'A','B','C'}:continue
        # Pool labels only create the evaluation reference; source order is hash
        # based on original text, never label order or a predicted decision.
        candidates.sort(key=lambda v:digest(['pa-source-order',v[0]]))
        record={'question':row['question'],'persona':[t for t,_ in candidates],
                'intent_type':''.join(label for _,label in candidates)}
        record['intent']=record['intent_type']
        task=rpeval_public(record,f'rpeval/pool/{i}')
        add('rpeval',poolpath,i,task,record,'generation_pool_derived_explicit_multi',
            {'max_query_similarity_to_official_or_selected':nearest,'source_order':'text_hash','not_official_test_track':True})
        selected_q.append(row['question'])
        if len(selected_q)==3:break
    if len(selected_q)!=3:raise ValueError('Insufficient eligible RPEval roots')

    # Three persona-driven generation roots; avoid previously used question IDs.
    # All forms are bound by question; this remains development, not proof of no
    # historical exposure in every experiment in this large repository.
    used_hashes={r['question_hash'] for phase in ('opt','select','smoke') for r in old['phases'][phase] if r['benchmark']=='prefeval'}
    from qamc.common import sha
    upstream=ROOT/'vendor/PrefEval';candidates=[]
    for path in sorted((upstream/'benchmark_dataset/implicit_preference/persona-driven').glob('*.json')):
        for i,row in enumerate(json.loads(path.read_text())):
            if sha(row['question']) not in used_hashes:candidates.append((path,i,row))
    topics=set();questions=[]
    for path,i,row in sorted(candidates,key=lambda v:digest(['pa-smoke-pref',v[0].stem,v[1]])):
        if path.stem in topics or any(near_score(row['question'],q)>=0.72 for q in questions):continue
        task,native=prefeval_public(row,f'prefeval/persona/{path.stem}/{i}',upstream)
        add('prefeval',path,i,task,{'question':row['question'],'preference':row['preference']},
            'implicit_persona_generation_0_interturn_300_words',{'native_messages_hash':digest(native),'topic':path.stem})
        topics.add(path.stem);questions.append(row['question'])
        if len(topics)==3:break
    if len(topics)!=3:raise ValueError('Insufficient PrefEval roots')
    cases += development
    judge_calls={'benchpres':6,'rpeval':1,'prefeval':4}
    nominal=sum(12+6*judge_calls[c['benchmark']] for c in cases)
    nolevel=sum(1+judge_calls[c['benchmark']] for c in cases)
    data={'version':'pa-smoke-inputs-v1','regression_roots':len(regression['cases']),
          'additional_development_roots':len(development),'cases':cases,'arms':['R0','G0','S0','V0','V1','V2'],
          'nominal_main_requests':nominal,'nominal_no_level_requests':nolevel,
          'nominal_total_requests':nominal+nolevel,'repair_policy':'deterministic parsing only; no semantic regeneration',
          'near_duplicate_threshold':0.72,'near_duplicate_method':'normalized character SequenceMatcher ratio',
          'semantic_independence_certified':False,'selection_uses_model_results':False,
          'new_model_calls':0,'status':'INPUTS_FROZEN_DISPATCH_PLAN_PENDING'}
    write_once(OUT/'SMOKE_INPUTS.json',data)
    return data

if __name__=='__main__':
    p=prepare_smoke();print(json.dumps({k:v for k,v in p.items() if k!='cases'}))
