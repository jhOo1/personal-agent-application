"""Prepare public inputs and private references in distinct files."""
import argparse
import json
import random
from qamc.common import ROOT, sha
from qamc.bace.audit import write_new, digest
from qamc.bace.prepare import small_bundle
from qamc.bace.prefeval_adapter import official_functions
from .prefeval_history import implicit_history
from .audit import OUT

RUN = ROOT / 'runs/qamc_bace_v2'


def prepare_case(row, bench_rows=None):
    if row['benchmark']=='benchpres':
        native=bench_rows[row['row_index']]
        profile, tail=native['prompt'].split('\n\nWrite a complete message to recipient',1)
        query='Write a complete message to recipient'+tail
        history=[{'id':f'h{i:04d}','role':'user','content':line}
                 for i,line in enumerate(profile.splitlines()) if line.strip()]
        reference={k:native[k] for k in ('preference_attribute','preference_label')}
        preparation={'acknowledgement_required':False,'track':'official_profile_text'}
    else:
        path=ROOT/'vendor/PrefEval/benchmark_dataset/mcq_options'/(row['topic']+'.json')
        native=json.loads(path.read_text())[row['index']]
        options=native['classification_task_options']
        if len(options)!=4 or len(set(options))!=4: raise ValueError('Ambiguous official options')
        seed=int(sha(['bace-v2-option-order',row['uid']])[:8],16)
        shuffled=random.Random(seed).sample(options,len(options))
        query=native['question']+official_functions()['get_mcq_question_format'](shuffled)
        reference={'correct_choice':'ABCD'[shuffled.index(options[0])],
                   'explicit_preference_for_generation_evaluation_only':native['preference']}
        form=row['history_form']
        if form=='explicit':
            history=[{'id':'pref0','role':'user','content':native['preference']}]
        else:
            source=ROOT/'vendor/PrefEval/benchmark_dataset/implicit_preference'/form/(row['topic']+'.json')
            # Match the public question, not a presumed shared row number.
            matches=[v for v in json.loads(source.read_text()) if v['question']==native['question']]
            if len(matches)>1:
                # Dataset identity disambiguation only. This explicit field is
                # never serialized into the implicit inference history.
                matches=[v for v in matches if v['preference']==native['preference']]
            if len(matches)!=1: raise ValueError('Implicit dialogue alignment is not unique')
            messages=implicit_history(matches[0]['conversation'],form)
            history=[{'id':f'h{i:04d}',**m} for i,m in enumerate(messages)]
        preparation={'acknowledgement_required':form=='explicit','track':form+'_classification',
                     'inter_turns':0,'formatter_sha256':digest(ROOT/'vendor/PrefEval/utils/utils_mcq.py'),
                     'preference_identification_history_not_unrelated_filler':True}
    bundle=small_bundle(query,history)
    public={'uid':row['uid'],'benchmark':row['benchmark'],'root':row['root'],
            'query':query,'history':history,'bundle':bundle,'preparation':preparation,
            'public_manifest_sha256':sha(row)}
    return public,reference


def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['smoke','opt'])
    args=parser.parse_args()
    manifest=json.loads((OUT/'DATA_MANIFEST_V2.json').read_text())
    import pyarrow.parquet as pq
    bench=pq.read_table(ROOT/'literature/bace_20261105/benchpres_test-00000-of-00001.parquet').to_pylist()
    outputs=[]
    for row in manifest['phases'][args.phase]:
        public,private=prepare_case(row,bench)
        paths={}
        for category,obj in [('inputs',public),('evaluation_references',private)]:
            path=RUN/category/(sha(row['uid'])[:24]+'.json');path.parent.mkdir(parents=True,exist_ok=True)
            if path.exists():
                if json.loads(path.read_text())!=obj:raise ValueError('Prepared input drift')
            else:write_new(path,obj)
            paths[category]={'path':str(path.relative_to(ROOT)),'sha256':digest(path)}
        outputs.append({'uid':row['uid'],**paths})
    target=OUT/(args.phase.upper()+'_INPUTS.json')
    if target.exists():
        if json.loads(target.read_text())!=outputs:raise ValueError('Input manifest drift')
    else:write_new(target,outputs)
    print(json.dumps({'phase':args.phase,'prepared':len(outputs),'new_model_calls':0}))


if __name__=='__main__':main()
