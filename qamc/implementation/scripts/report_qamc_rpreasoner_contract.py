#!/usr/bin/env python3
"""Read-only score, prediction, cache and generation-mode comparisons."""
import json
import sqlite3
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT),str(ROOT/'scripts')]
import run_qamc_rpreasoner as base
import run_qamc_rpreasoner_contract as current
import diagnose_qamc_rpreasoner as diagnostic
from qamc.pa.report import metrics

def main():
    current.configure()
    plan=base.read(current.OUT/'PLAN.json')
    result=base.report(plan)
    diagnostic.OUT=current.OUT;diagnostic.RUN=current.RUN;diagnostic.main()
    rows=base.outcomes();lookup={(r['uid'],r['arm']):r for r in rows}
    controls=[x['result'] for x in base.read(current.OUT/'CONTROL_IMPORTS.json')]
    mode_rows=[]
    for c in plan['cases']:
        a=lookup.get((c['uid'],'RP_PAPER_ADAPTED'));b=lookup.get((c['uid'],'RP_SHARED_ACTOR'))
        if a and b and a.get('selection') and b.get('selection'):
            assert a['selection']==b['selection'], 'Generation modes changed estimator output'
            mode_rows.append({'uid':c['uid'],'same_prediction':True,'paper_answer':a.get('answer'),
                 'shared_answer':b.get('answer'),'paper_score':a.get('score'),'shared_score':b.get('score'),
                 'predicted_policy':a['selection']['aggregation']['policy'],
                 'paper_score_status':a['score_status'],'shared_score_status':b['score_status']})
    with sqlite3.connect(f'file:{current.RUN}/api/ledger.sqlite?mode=ro',uri=True) as db:
        imports=[json.loads(x[0]) for x in db.execute('select data from cache_imports')]
    result['cache_imports']=len(imports)
    result['shared_prediction_pairs']=len(mode_rows)
    result['no_new_calls_by_report']=True
    result['unique_completed_predictions']=len({r['uid'] for r in rows if r.get('selection')})
    result['failure_rows']=[{k:r.get(k) for k in ['uid','arm','pipeline_status','score_status','error','score_error']} for r in rows if not base.valid(r)]
    (current.OUT/'ANALYSIS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    (current.OUT/'GENERATION_MODE_PAIRS.json').write_text(json.dumps(mode_rows,ensure_ascii=False,indent=2)+'\n')
    (current.OUT/'CACHE_PROVENANCE.json').write_text(json.dumps(imports,ensure_ascii=False,indent=2)+'\n')
    lines=['# RPReasoner cardinality-adapted development results','',
           f"Status: {result['status']}; saved {result['saved_cells']}/16; strict valid {result['normal_scored']}.",'',
           'Historically exposed development roots. Adapted paper templates, Qwen scoring, human reviews0. Neither SOTA nor an exact author reproduction.','',
           '| Candidate | Control | Common roots | Label match | Control match |','|---|---|---:|---:|---:|']
    for p in result['paired']:
        lines.append(f"| {p['arm']} | {p['baseline']} | {p['common_valid']} | {p['candidate'].get('atomic_match','NA')} | {p['control'].get('atomic_match','NA')} |")
    lines += ['', 'Full severity, verbosity, full-query correctness and IDs are in ANALYSIS.json. Intent prediction is separately evaluated in INTENT_DIAGNOSTIC.json; generation-mode pairs share predictions and are not independent prediction trials.',
              '', f"Physical requests: {result['physical_requests']}; states: {result['request_status']}; cache imports: {len(imports)}. Unknown usage: {result['unknown_usage']}. Tokens: {result['tokens']}.",
              '', 'Parent format-failure records remain in qamc_rpreasoner. Failed or unavailable scores are excluded symmetrically from strict paired comparisons, never treated as semantic zeros. No judge backfill, model retry, inference change or new dispatch occurs in this report.']
    (current.OUT/'RESULTS.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({k:result[k] for k in ['status','saved_cells','normal_scored','physical_requests','cache_imports','shared_prediction_pairs']}))
if __name__=='__main__':main()
