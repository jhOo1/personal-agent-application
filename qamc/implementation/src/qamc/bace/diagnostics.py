"""Offline candidate label mapping; never feed references to inference.

Official context labels are narrowly projected to exact style units as PROXIES.
They require separate source/use review before probability calibration.
"""
import argparse
import json
import re
from collections import Counter
from .audit import ROOT,OUT
from .prepare import RUN
from .metrics import binary_metrics,root_auc_interval,score_distribution
from .coverage import coverage_counts
from .evaluation_roots import evaluation_root
from .benchmark_eval_match import benchpres_row
from qamc.common import sha
from qamc.transport_helpers import atomic_json


def norm(text):return re.sub(r'\s+',' ',text).strip().lower().rstrip('.')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--namespace',choices=['original','quote_space_v2','anchored_span_v3'],default='original')
    args=parser.parse_args()
    # Preserve original diagnostics and explicitly identify the recovered lineage.
    case_root=RUN if args.namespace=='original' else RUN/args.namespace
    suffix={'original':'','quote_space_v2':'_V2','anchored_span_v3':'_V3'}[args.namespace]
    import pyarrow.parquet as pq
    plan=json.loads((OUT/'SCORE_PILOT_PLAN.json').read_text())
    native=pq.read_table(ROOT/'literature/bace_20261105/benchpres_test-00000-of-00001.parquet').to_pylist()
    records=[];review=[];coverage=[]
    for case in plan['cases']:
        path=case_root/'cases'/sha(case['uid'])[:24]/'scores.json'
        if not path.exists():continue
        result=json.loads(path.read_text());bundle=json.loads((ROOT/case['bundle']).read_text())
        p=bundle['payload'];units={u['unit_id']:u for u in p['units']}
        root=evaluation_root(case,bundle)
        attributes={}
        if case['uid'].startswith('benchpres/'):
            # Context text alone is shared by ten profiles; use source identity too.
            _,row=benchpres_row(p,native)
            for attribute,label in zip(row['preference_attribute'],row['preference_label']):
                attributes.setdefault(norm(attribute),set()).add(label)
        maps={role:{(r['unit_id'],r['scope_id'],r['use_kind']):r for r in result['assessment'][role]['assessments']}
              for role in ('allow','deny')}
        both=0
        for use in result['inventory']:
            key=(use['unit_id'],use['scope_id'],use['use_kind']);unit=units[key[0]]
            assessed=all(maps[r][key]['status']=='ASSESSED' for r in maps);both+=assessed
            text=norm(unit['exact_text']);labels=attributes.get(text,set())
            is_proxy=(len(case['scopes'])==1 and key[2]=='STYLE_ADAPTATION' and len(labels)==1
                      and 'called' not in text and 'nickname' not in text)
            target=next(iter(labels)) if is_proxy else None
            review_id=sha([case['uid'],key])[:24]
            if is_proxy:
                review.append({'review_id':review_id,'uid':case['uid'],'phase':case['phase'],
                    'query':p['query'],'scopes':case['scopes'],'use_key':dict(zip(('unit_id','scope_id','use_kind'),key)),
                    'original_unit':unit,'selected_source_spans':use['source_spans'],
                    'official_attribute_context_label':target,'suggested_allow_label':target,
                    'suggested_deny_label':not target,'reviewed':False,'human_review':0,
                    'calibration_qualified':False,'qualification_needed':'Exact use is application of this attribute to this current output, not another lawful or historical purpose.'})
            for role in ('allow','deny'):
                a=maps[role][key]
                records.append({'uid':case['uid'],'phase':case['phase'],'root':root,
                    'frozen_manifest_source_root':case['source_root'],'review_id':review_id,
                    'role':role,'use_key':list(key),'status':a['status'],'score':a['raw_score'],
                    'label':(target if role=='allow' else not target) if is_proxy else None,
                    'label_provenance':'official_attribute_context_proxy' if is_proxy else 'UNKNOWN',
                    'calibration_qualified':False})
        coverage.append({'uid':case['uid'],'phase':case['phase'],'inventory':len(result['inventory']),
                         'both_assessed':both,'overflow':len(result['unassessed_overflow']),
                         'required_overflow':len(result.get('required_overflow',[])),
                         'denominators':coverage_counts(result)})
    summaries=[]
    for phase in ('regression','score-pilot'):
        for role in ('allow','deny'):
            rows=[r for r in records if r['phase']==phase and r['role']==role]
            summaries.append({'phase':phase,'role':role,'label_level':'proxy_not_exact_UseGold',
                **binary_metrics(rows),'clustered_auc':root_auc_interval(rows),
                'raw_distribution':score_distribution(rows)})
    atomic_json(OUT/('RAW_SCORE_DIAGNOSTICS'+suffix+'.json'),{'namespace':args.namespace,'summaries':summaries,'coverage':coverage,
        'records':records,'human_review':0,'calibrated':False,'native_task_scores_available':False})
    atomic_json(OUT/('USE_GOLD_REVIEW_CANDIDATES'+suffix+'.json'),{'namespace':args.namespace,'method_score_blinded':True,'human_review':0,'items':review})
    print(json.dumps({'completed_cases':len(coverage),'review_candidates':len(review),
                      'calibration_qualified_labels':0,'both_assessed':sum(c['both_assessed'] for c in coverage)}))


if __name__=='__main__':main()
