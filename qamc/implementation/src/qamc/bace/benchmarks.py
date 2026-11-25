"""Inspect published benchmark protocols and freeze metadata-only group splits.

No gold is supplied to generation. These are internal splits, not a complete
official leaderboard evaluation. BenchPreS has no untouched profile holdout.
"""
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from .audit import ROOT, OUT, digest, write_new


def hashed(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def build():
    import pyarrow.parquet as pq
    vendor=ROOT/'vendor/PrefEval'
    data=vendor/'benchmark_dataset'
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=vendor,text=True).strip()
    records=[]; mismatches=[]; provenance=[]; preference_aliases={}
    for path in sorted((data/'explicit_preference').glob('*.json')):
        topic=path.stem; explicit=json.loads(path.read_text())
        paths=[path,data/'implicit_preference/choice-based'/path.name,
               data/'implicit_preference/persona-driven'/path.name,data/'mcq_options'/path.name]
        variants=[json.loads(p.read_text()) for p in paths]
        provenance.extend({'path':str(p.relative_to(ROOT)),'sha256':digest(p)} for p in paths)
        if any(len(v)!=len(explicit) for v in variants):
            mismatches.append({'topic':topic,'reason':'variant_length_mismatch'})
            continue
        for i,row in enumerate(variants[3]):
            # Alignment uses only public preference/question identity, never an
            # answer option or an evaluation explanation.
            pair=(row['preference'],row['question'])
            if any(v[i]['question']!=row['question'] for v in variants):
                mismatches.append({'topic':topic,'index':i,'reason':'question_mismatch_quarantined'})
                continue
            if any(v[i]['preference']!=row['preference'] for v in variants):
                mismatches.append({'topic':topic,'index':i,'reason':'preference_text_differs_use_official_mcq',
                                   'grouped_together':True,'excluded':False})
            uid=f'prefeval/{topic}/{i}'
            preference_aliases[uid]={hashed(v[i]['preference'].strip()) for v in variants}
            records.append({'uid':uid,'topic':topic,'index':i,
                            'pair_id':hashed(pair),'question_hash':hashed(row['question'].strip()),
                            'preference_hash':hashed(row['preference'].strip())})
    # Connected components conservatively co-locate exact shared questions OR
    # preferences, in addition to every expression/length of the base pair.
    parent=list(range(len(records)))
    def find(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    seen={}
    for i,r in enumerate(records):
        identities=[(field,r[field]) for field in ('pair_id','question_hash','preference_hash')]
        identities += [('preference_hash',h) for h in preference_aliases[r['uid']]]
        for key in identities:
            if key in seen: parent[find(i)]=find(seen[key])
            else: seen[key]=i
    groups={}
    for i,r in enumerate(records):groups.setdefault(find(i),[]).append(r['pair_id'])
    for i,r in enumerate(records):
        r['root_group']=hashed(sorted(set(groups[find(i)])))
        bucket=int(hashed(['bace-20261105-split-v1',r['root_group']])[:8],16)%100
        r['split']='cal' if bucket<20 else 'select' if bucket<40 else 'test'
        r['all_forms_and_lengths_bound_to_split']=True
    bench_path=ROOT/'literature/bace_20261105/benchpres_test-00000-of-00001.parquet'
    bench=pq.read_table(bench_path).to_pylist(); names=sorted({r['name'] for r in bench},key=hashed)
    bench_records=[]
    for i,r in enumerate(bench):
        profile,query=r['prompt'].split('\n\nWrite a complete message to recipient',1)
        bench_records.append({'uid':'benchpres/'+hashed([r['name'],r['task'],r['recipient']])[:20],
            'row_index':i,'profile_root':hashed(r['name']),'profile_content_hash':hashed(profile),
            'context_root':hashed([r['task'],r['recipient']]),'domain':r['domain'],
            'split':'cal' if r['name'] in names[:6] else 'select',
            'prior_exposure':'EXPOSED_PROFILE','eligible_unseen_test':False})
    regression=[json.loads(x) for x in (ROOT/'reports/qamc_preference_policy/profile_input_v2/EXPOSURE_MANIFEST.jsonl').read_text().splitlines()]
    registry={
        'version':'bace-phase0-v2','status':'protocol_audit_pending_runtime_adapters',
        'benchpres':{'venue':'EMNLP 2026 Main','acceptance_verified':True,
            'official_url':'https://aclanthology.org/2026.emnlp-main.1040/',
            'dataset':'sangyon/BenchPreS','revision':'301031ab04f13bb45559389fddccff79e85ea27a',
            'sha256':digest(bench_path),'published_splits':{'test':len(bench)},'profiles':len(names),
            'license':'CC-BY-NC-4.0','canary_preserved':True,'training_or_public_policy_export':False,
            'visible_fields':['prompt'],'evaluation_only_fields':['preference_attribute','preference_label'],
            'official_judge':'DeepSeek-R1','local_judge':'qwen3.8-flash variant, uncalibrated',
            'labels':'attribute x context applicability; NOT exact UseKey truth',
            'untouched_profile_test_available':False,'profile_is_complete_not_top24':True},
        'prefeval':{'venue':'ICLR 2025','acceptance_verified':True,
            'official_url':'https://proceedings.iclr.cc/paper_files/paper/2025/hash/28a46044775d97a4efcbcf14e7f13209-Abstract-Conference.html',
            'repository':'https://github.com/amazon-science/PrefEval','revision':revision,
            'license':'CC-BY-NC-4.0','license_sha256':digest(vendor/'LICENSE'),
            'hf_revision':'1b20e0f944d7665f435e24eb8b76f4d45d83c419',
            'hf_published_splits':{'train':1000},'official_cal_select_test':False,
            'aligned_base_pairs':len(records),'alignment_discrepancies':mismatches,
            'classification_input_authority':'mcq_options file, as official load_files_mcq; not HF preference text',
            'classification':'official options shuffle; first original option is key, retained only in evaluator',
            'official_parser':'utils/utils_mcq.py extract_choice; XML choice tag',
            'visible_fields':['preference (explicit only)','question','shuffled classification_task_options','legal conversation'],
            'evaluation_only_fields':['explanation','violation_probability','correct_idx','aligned_op'],
            'generation_track':'not executed; official four checks require separately verified adapter',
            'length_conditions':'bind all lengths to root; no outcome-selected length',
            'source_files':provenance},
        'regression_only':['personamem'], 'not_admitted_to_main':['memsyco'],
        'conditional_external_only':['op-bench'],'human_review':0}
    manifest={'version':'bace-internal-group-split-v2','frozen_before_model_calls':True,
              'protocol':'internal split, not untouched full official test',
              'prefeval':records,'benchpres':bench_records,
              'regression':[{'uid':r['uid'],'input':r['input'],'input_hash':r['input_hash'],
                             'source_family':r['source_family']} for r in regression],
              'limitations':['BenchPreS all profiles already exposed; no untouched profile test.',
                 'Exact connected components do not prove absence of semantic near duplicates.',
                 'PrefEval grouped split still needs historical payload exposure scan before test authorization.',
                 'Numeric calibration requires reliable UseGold; native task labels are not exact-use labels.']}
    registry['supersedes']=digest(OUT/'BENCHMARK_REGISTRY.json')
    manifest['supersedes']=digest(OUT/'SPLITS_MANIFEST.json')
    write_new(OUT/'BENCHMARK_REGISTRY_V2.json',registry)
    write_new(OUT/'SPLITS_MANIFEST_V2.json',manifest)
    print(json.dumps({'prefeval':dict(Counter(r['split'] for r in records)),
        'prefeval_roots':len(groups),'quarantine':len(mismatches),'benchpres':dict(Counter(r['split'] for r in bench_records))}))


if __name__=='__main__':build()
