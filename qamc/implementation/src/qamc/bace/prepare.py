"""Freeze a bounded score pilot without opening evaluation labels."""
import json
from collections import defaultdict
from .audit import ROOT,OUT,digest,write_new
from .contract import generation_input
from qamc.common import sha

RUN=ROOT/'runs/qamc_bace_20261105'


def small_bundle(query,sources):
    units=[];metadata={}
    for i,s in enumerate(sources):
        uid=f'U{i+1}'
        units.append({'unit_id':uid,'source_id':s['id'],'start':0,'end':len(s['content']),
            'exact_text':s['content'],'carrier':s.get('role','user'),'memory_version':sha(s),
            'attributed_author':None,'subject':'unknown','time':None,'modality':'unknown'})
        metadata[s['id']]={'carrier':s.get('role','user'),'recorded_at':None,
                          'origin':'OFFICIAL_SUPPLIED_SOURCE','unit_ids':[uid]}
    units.append({'unit_id':'Q0','source_id':'__current__','start':0,'end':len(query),
                  'exact_text':query,'modality':'current_input'})
    payload={'query':query,'current_context':[],'query_time':None,'units':units,
             'source_metadata':metadata,'profile_navigation':[],
             'annotation_legend':'Source text only; unknown dates and attribution are not invented.'}
    generation_input(payload)
    return {'payload':payload,'input_hash':sha(payload),'source_hash':sha(sources)}


def main():
    import pyarrow.parquet as pq
    RUN.mkdir(exist_ok=True);(RUN/'inputs').mkdir(exist_ok=True)
    split=json.loads((OUT/'SPLITS_MANIFEST_V3.json').read_text())
    selected=[]
    for row in split['regression']:
        bundle=json.loads((ROOT/row['input']).read_text())
        old_scope=ROOT/'runs/qamc_preference_policy/profile_input_v2/cases'/sha(row['uid'])[:24]/'scope.json'
        scoped=json.loads(old_scope.read_text())
        if scoped['status']!='ok':raise ValueError('Existing scope unavailable')
        selected.append({'uid':row['uid'],'phase':'regression','bundle':row['input'],
                         'bundle_sha256':digest(ROOT/row['input']),'scopes':scoped['result']['scopes'],
                         'scope_source':str(old_scope.relative_to(ROOT)),'scope_sha256':digest(old_scope),
                         'source_root':row['source_family'],'old_answers_readonly':True})
    bench=pq.read_table(ROOT/'literature/bace_20261105/benchpres_test-00000-of-00001.parquet').to_pylist()
    # Round-robin profile roots and topics, then stable UID hash. No labels read.
    for benchmark in ('benchpres','prefeval'):
        groups=defaultdict(list)
        for row in split[benchmark]:
            if row['split']=='cal':groups[row.get('profile_root',row.get('topic'))].append(row)
        for values in groups.values():values.sort(key=lambda r:sha(['bace-pilot-v1',r['uid']]))
        chosen=[]
        while len(chosen)<8:
            for group in sorted(groups):
                if groups[group]:chosen.append(groups[group].pop(0))
                if len(chosen)==8:break
        for row in chosen:
            if benchmark=='benchpres':
                raw=bench[row['row_index']]
                profile,tail=raw['prompt'].split('\n\nWrite a complete message to recipient',1)
                query='Write a complete message to recipient'+tail
                sources=[{'id':f'h{i:04d}','role':'user','content':line} for i,line in enumerate(profile.splitlines()) if line.strip()]
                root=row['profile_root']
            else:
                path=ROOT/'vendor/PrefEval/benchmark_dataset/mcq_options'/(row['topic']+'.json')
                raw=json.loads(path.read_text())[row['index']]
                # This phase assesses sources/uses only. No task answer or native
                # accuracy is produced; acknowledgement/MCQ preparation is later.
                from .prefeval_adapter import official_functions
                import random
                seed=int(sha(['bace-option-order-v1',row['uid']])[:8],16)
                options=random.Random(seed).sample(raw['classification_task_options'],4)
                query=raw['question']+official_functions()['get_mcq_question_format'](options)
                sources=[{'id':'pref0','role':'user','content':raw['preference']}]
                root=row['root_group']
            bundle=small_bundle(query,sources);path=RUN/'inputs'/(sha(row['uid'])[:24]+'.json')
            if path.exists():
                if json.loads(path.read_text())!=bundle:raise ValueError('Existing prepared input differs')
            else:write_new(path,bundle)
            selected.append({'uid':row['uid'],'phase':'score-pilot','bundle':str(path.relative_to(ROOT)),
                'bundle_sha256':digest(path),'scopes':[{'scope_id':'S1','query_anchor':(raw['question'] if benchmark=='prefeval' else query[:180])}],
                'source_root':root,'split':'cal','task_answer_generated':False,
                'official_track_score_claimed':False})
    files=list((ROOT/'src/qamc/bace').glob('*.py'))+list((ROOT/'prompts/bace').glob('*.md'))
    files += [ROOT/'src/qamc/b7_api.py',ROOT/'src/qamc/rate_limit.py',ROOT/'src/qamc/preference_policy/profile_input.py']
    plan={'version':'bace-score-pilot-v1','model':'qwen3.8-flash','temperature':0,
          'regression_cases':32,'new_development_cases':16,'nominal_requests':192,
          'request_cap':400,'concurrency':8,'case_workers':4,'spacing_seconds':6.1,
          'max_output_tokens':8192,'max_uses_per_case':12,
          'repair':'at most one schema repair per logical call; one existing precontent 429 recovery',
          'stop':'existing gateway circuit on repeated 429; two unknown transport failures stop new cases; no unknown retries',
          'human_review':0,'score_diagnostics_not_task_benchmark_results':True,
          'selection_used_gold':False,'raw_scores_not_probabilities':True,
          'calibration_gate':'No numeric fitting unless independent source-qualified binary labels have both classes and discrimination; benchmark labels alone are not all-use truth.',
          'formal_test_dispatch':False,'cases':selected,
          'frozen_files':{str(p.relative_to(ROOT)):digest(p) for p in files},
          'split_manifest_sha256':digest(OUT/'SPLITS_MANIFEST_V3.json')}
    write_new(OUT/'SCORE_PILOT_PLAN.json',plan)
    print(json.dumps({'regression':32,'new_cal':16,'nominal_requests':192,'cap':400}))


if __name__=='__main__':main()
