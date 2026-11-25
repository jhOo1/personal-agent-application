"""Offline frozen regression inputs and exact-lineage inventory; no model calls."""
from dataclasses import asdict
from pathlib import Path
import json
import hashlib
from .adapters import benchpres_public
from .core import rpeval_public, digest

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'reports/qamc_pa_v1'
RUN=ROOT/'runs/qamc_pa_v1'


def write_once(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if json.loads(path.read_text()) != json.loads(json.dumps(value)): raise ValueError('Frozen artifact drift: '+str(path))
        return
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2))


def prepare_regression():
    import pyarrow.parquet as pq
    benchpath=ROOT/'literature/bace_20261105/benchpres_test-00000-of-00001.parquet'
    bench=pq.read_table(benchpath).to_pylist()
    old=json.loads((ROOT/'reports/qamc_bace_v2/DATA_MANIFEST_V2.json').read_text())
    requested=['benchpres/551a56e874ca2a0a6e0a','benchpres/cbb72f8c0c7a28d20890','benchpres/e0fa9dd2fbc80104c182']
    cases=[]
    for uid in requested:
        row=next(r for r in old['phases']['opt'] if r['uid']==uid)
        cases.append(('benchpres',benchpath,row['row_index'],uid))
    # Real official bank-loan anchor: resolve public task/profile, not labels.
    bank=[i for i,r in enumerate(bench) if r['task']=='Apply for personal loan' and '"Nova"' in r['prompt']]
    if len(bank)!=1: raise ValueError('Bank anchor ambiguous')
    cases.append(('benchpres',benchpath,bank[0],'benchpres/public_bank_loan_anchor'))
    base=ROOT/'literature/qamc_pa_v1/RPEval/benchmark_dataset/explicit_preference'
    cases.extend([('rpeval',base/'single_testset.json',0,'rpeval/readme_dorm'),
                  ('rpeval',base/'multi_testset.json',0,'rpeval/readme_chengdu')])
    manifest=[]
    for benchmark,path,index,uid in cases:
        row=bench[index] if benchmark=='benchpres' else json.loads(path.read_text())[index]
        task=benchpres_public(row['prompt'],uid) if benchmark=='benchpres' else rpeval_public(row,uid)
        if benchmark=='benchpres': reference={k:row[k] for k in ('preference_attribute','preference_label')}
        else: reference={k:row[k] for k in ('persona','question','intent_type','intent','reason') if k in row}
        token=digest(uid)[:24];public_path=RUN/'regression/public'/(token+'.json')
        private_path=RUN/'regression/evaluation_only'/(token+'.json')
        write_once(public_path,asdict(task));write_once(private_path,reference)
        manifest.append({'uid':uid,'benchmark':benchmark,'source_file':str(path.relative_to(ROOT)),
                         'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'row_index':index,
                         'public_path':str(public_path.relative_to(ROOT)),'public_hash':digest(asdict(task)),
                         'evaluation_path':str(private_path.relative_to(ROOT)),'evaluation_hash':digest(reference),
                         'exposure':'ALREADY_EXPOSED_REGRESSION','independent_confirmation':False})
    nominal=sum(12+6*(6 if r['benchmark']=='benchpres' else 1) for r in manifest)
    control=sum(1+(6 if r['benchmark']=='benchpres' else 1) for r in manifest)
    plan={'status':'PREPARED_NOT_DISPATCH_AUTHORIZATION','cases':manifest,
          'arms':['R0','G0','S0','V0','V1','V2'],'normal_generation_calls_per_root':12,
          'nominal_calls':nominal,'v2_no_level_additional_nominal':control,
          'repairs_and_fallback_not_yet_budgeted':True,'new_model_calls':0}
    write_once(OUT/'REGRESSION_INPUTS.json',plan)
    return plan


def lineage_inventory():
    base=ROOT/'literature/qamc_pa_v1/RPEval'; groups={}
    normalize=lambda text:''.join(text.split()).casefold()
    official=set()
    for path in sorted((base/'benchmark_dataset').glob('*/*.json')):
        for index,row in enumerate(json.loads(path.read_text())):
            key=digest(normalize(row['question']));official.add(key)
            groups.setdefault(key,[]).append({'file':str(path.relative_to(base)),'row':index})
    pool=json.loads((base/'data_generation/data.json').read_text())
    poolgroups={}
    for index,row in enumerate(pool):poolgroups.setdefault(digest(normalize(row['question'])),[]).append(index)
    report={'official_records':sum(map(len,groups.values())),'official_exact_question_roots':len(groups),
            'pool_records':len(pool),'pool_exact_question_roots':len(poolgroups),
            'overlapping_exact_roots':len(set(poolgroups)&official),
            'pool_nonoverlap_exact_roots':len(set(poolgroups)-official),
            'grouping_rule':'normalized question only; not semantic independence proof',
            'official_groups':groups,'pool_groups':poolgroups,
            'exposure':'automated full-file audit; README anchors and old cases development-only',
            'confirm_manifest':'NOT_FROZEN','new_model_calls':0}
    write_once(OUT/'RPEVAL_EXACT_LINEAGE.json',report)
    return {k:v for k,v in report.items() if not k.endswith('_groups')}


if __name__=='__main__':
    plan=prepare_regression()
    print(json.dumps({'regression_cases':len(plan['cases']),'nominal':plan['nominal_calls'],
                      'control_additional':plan['v2_no_level_additional_nominal'],'lineage':lineage_inventory()}))
