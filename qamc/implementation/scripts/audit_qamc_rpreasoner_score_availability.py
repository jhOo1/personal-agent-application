#!/usr/bin/env python3
"""Uniform saved-score availability, without dispatch or fabricated values."""
import json
import math
import sqlite3
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from qamc.common import sha,parse_object
from audit_qamc_pa_score_sensitivity import atomic_match
OUT=ROOT/'reports/qamc_rpreasoner_contract'
RUN=ROOT/'runs/qamc_rpreasoner_contract/execution'
METRICS=('OPB','UPB','RII','FM','VG','Judge')

def main():
    plan=json.loads((OUT/'PLAN.json').read_text());cases={c['uid']:c for c in plan['cases']}
    source_rows=[(r['result'],r['source_artifact']) for r in json.loads((OUT/'CONTROL_IMPORTS.json').read_text())]
    source_rows += [(json.loads(p.read_text()),str(p.relative_to(ROOT))) for p in (RUN/'outcomes').glob('*/*.json') if p.stem in plan['arms']]
    ledgers=[]
    for root in [RUN,ROOT/'runs/qamc_fused_gate/execution',ROOT/'runs/qamc_fused_gate/recovery_01']:
        dbpath=root/'api/ledger.sqlite'
        if not dbpath.exists():continue
        with sqlite3.connect(f'file:{dbpath}?mode=ro',uri=True) as db:
            ledgers.extend((root/'api',json.loads(x[0])) for x in db.execute('select data from requests'))
    rows=[]
    for r,artifact in source_rows:
        c=cases[r['uid']];ref=json.loads((ROOT/c['evaluation_path']).read_text());public=json.loads((ROOT/c['public_path']).read_text())
        obj=(r.get('score') or {}).get('raw_judge');origin='saved_strict_score';ambiguity=False
        if obj is None and r.get('answer_status')=='OK':
            prefix='pa/eval/'+sha(['rpeval',r['uid'],public['query'],ref,r['answer']])+'/'
            found={}
            for api,call in ledgers:
                if not call['key'].startswith(prefix) or not call.get('response_path'):continue
                response=api/call['response_path']
                if not response.exists():continue
                try:parsed=parse_object(json.loads(response.read_text())['answer'])
                except (ValueError,KeyError,TypeError):continue
                found[sha(parsed)]=(parsed,str(response.relative_to(ROOT)))
            if len(found)==1:obj,origin=next(iter(found.values()))
            elif len(found)>1:ambiguity=True
        row={'uid':r['uid'],'arm':r['arm'],'source_artifact':artifact,'strict_status':r['score_status'],
             'pipeline_status':r['pipeline_status'],'fallback':r.get('fallback',False),'raw_judge':obj,
             'origin':origin,'ambiguous_multiple_responses':ambiguity,'matched':None,'total':None,
             'severity':{k:None for k in METRICS}}
        if obj is not None:
            try:
                count=len(ref['persona']) if isinstance(ref['persona'],list) else 1
                row['matched'],row['total']=atomic_match(obj,count,isinstance(ref['persona'],list))
            except ValueError as exc:row['match_error']=str(exc)
            for k in METRICS:
                v=obj.get(k)
                if type(v) in (int,float) and math.isfinite(v) and 0<=v<=5:row['severity'][k]=v
        rows.append(row)
    pairs=[]
    for a in plan['arms']:
        for b in ['G0','V0','F0','R0','S0']:
            left={r['uid']:r for r in rows if r['arm']==a and r['pipeline_status']=='OK' and not r['fallback']}
            right={r['uid']:r for r in rows if r['arm']==b and r['pipeline_status']=='OK' and not r['fallback']}
            ids=sorted(left.keys()&right.keys())
            valid=[u for u in ids if left[u]['matched'] is not None and right[u]['matched'] is not None]
            delta=[left[u]['matched']/left[u]['total']-right[u]['matched']/right[u]['total'] for u in valid]
            p={'candidate':a,'control':b,'atomic_common':len(valid),'uids':valid,
               'wins':sum(x>0 for x in delta),'ties':sum(x==0 for x in delta),'losses':sum(x<0 for x in delta),
               'candidate_atomic':[sum(left[u]['matched'] for u in valid),sum(left[u]['total'] for u in valid)],
               'control_atomic':[sum(right[u]['matched'] for u in valid),sum(right[u]['total'] for u in valid)],'severity':{}}
            for k in METRICS:
                eligible=[u for u in ids if left[u]['severity'][k] is not None and right[u]['severity'][k] is not None]
                p['severity'][k]={'common':len(eligible),'uids':eligible,
                    'candidate_mean':sum(left[u]['severity'][k] for u in eligible)/len(eligible) if eligible else None,
                    'control_mean':sum(right[u]['severity'][k] for u in eligible)/len(eligible) if eligible else None}
            pairs.append(p)
    result={'version':'uniform_metric_availability_v1','not_primary_score':True,'new_calls':0,'human_reviews':0,
            'semantic_grade_changes':False,'missing_values_imputed':False,'rows':rows,'pairs':pairs,
            'note':'Per-metric common sets differ and are explicitly listed. These are saved Judge outputs, not proof of semantic accuracy. Do not combine severity means across incompatible denominators.'}
    (OUT/'SCORE_AVAILABILITY.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'rows':len(rows),'atomic_available':sum(r['matched'] is not None for r in rows),'new_calls':0}))
if __name__=='__main__':main()
