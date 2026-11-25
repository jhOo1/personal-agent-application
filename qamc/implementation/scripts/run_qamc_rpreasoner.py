#!/usr/bin/env python3
"""Finite RPReasoner development comparison; preserve all previous controls."""
import argparse
import json
import sqlite3
import sys
import hashlib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT),str(ROOT/'scripts')]
from qamc.common import sha
from qamc.pa.core import digest
from qamc.pa.prepare import write_once
from qamc.pa.evaluate import Evaluator
from qamc.pa.report import metrics
from qamc.fused_gate.experiment import load_task
from qamc.bace.runtime import runner_lock
from qamc.transport_helpers import atomic_json
from qamc_stream_cooldown import CooldownGateway
from proposals.qamc_rpreasoner.adapter import load_templates
from proposals.qamc_rpreasoner.engine import RPReasonerEngine
OUT=ROOT/'reports/qamc_rpreasoner'
RUN=ROOT/'runs/qamc_rpreasoner/execution'
SOURCE=ROOT/'literature/qamc_pa_v1/paper_prompt_source/rpreasoner_figures_15_17.json'
ARMS=['RP_PAPER_ADAPTED','RP_SHARED_ACTOR']
STOP=ROOT/'runs/qamc_fused_gate/execution/api/STOP'

def filehash(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())

def freeze():
    old=read(ROOT/'reports/qamc_fused_gate/PLAN.json')
    cases=[c for c in old['cases'] if c['benchmark']=='rpeval']
    assert len(cases)==8
    templates,audit=load_templates(SOURCE)
    smoke=[next(c['uid'] for c in cases if c['track']==track) for track in ('explicit_preference/single','implicit_preference/multi')]
    overlay=read(ROOT/'reports/qamc_fused_gate/RECOVERY_OVERLAY.json')
    ids={c['uid'] for c in cases}
    controls=[r for r in overlay['rows'] if r['result']['uid'] in ids]
    for r in controls:
        c=next(c for c in cases if c['uid']==r['result']['uid'])
        assert r['result']['public_hash']==c['public_hash']
    paths=list((ROOT/'src/qamc').rglob('*.py'))+list((ROOT/'proposals/qamc_rpreasoner').glob('*.py'))
    paths += list((ROOT/'prompts/qamc_pa_v1').glob('*.md'))
    paths += [Path(__file__),ROOT/'scripts/qamc_stream_cooldown.py',SOURCE,
              ROOT/'literature/qamc_pa_v1/RPEval/prompts/prompts_715.py',OUT/'DECISION_RULES.md']
    paths += [ROOT/c[k] for c in cases for k in ('public_path','evaluation_path','source_file')]
    paths += [ROOT/r['source_artifact'] for r in controls]
    plan={'cases':cases,'arms':ARMS,'smoke_uids':smoke,'model':'qwen3.8-flash','temperature':0,
          'concurrency':8,'spacing_seconds':3.1,'input_estimate_token_cap':32768,'request_cap':96,
          'user_request_quota':None,'attempt_guard_not_budget':True,'nominal_calls':48,
          'actor_output_cap':4096,'estimator_output_cap':8192,'judge_output_cap':2048,
          'tie_seed':'qamc-rpreasoner-dev-20261107-v1','templates':audit,
          'exact_author_reproduction':False,'independent_confirmation':False,
          'original_memory_rebuilt':False,'frozen_files':{str(p.relative_to(ROOT)):filehash(p) for p in sorted(set(paths))}}
    policy=read(ROOT/'reports/qamc_message_units/DISPATCH_POLICY.json')
    policy['epoch_id']='qamc_rpreasoner_20261107_01'
    write_once(OUT/'CONTROL_IMPORTS.json',controls)
    write_once(OUT/'TEMPLATES.json',templates)
    write_once(OUT/'DISPATCH_POLICY.json',policy)
    write_once(OUT/'PLAN.json',plan)
    return plan

def check(plan):
    for p,h in plan['frozen_files'].items():
        if filehash(ROOT/p)!=h:raise ValueError('Frozen drift: '+p)
    for c in plan['cases']:
        task=load_task(ROOT,c)
        if task.current_context or task.fixed_facts:raise ValueError('Unsupported context')
        if digest(read(ROOT/c['evaluation_path']))!=c['evaluation_hash']:raise ValueError('Evaluation drift')

def outcomes():return [read(p) for p in (RUN/'outcomes').glob('*/*.json') if p.stem in ARMS]
def valid(r):return r.get('pipeline_status')=='OK' and r.get('score_status')=='OK' and not r.get('fallback')

def report(plan):
    rows=outcomes();controls=[x['result'] for x in read(OUT/'CONTROL_IMPORTS.json')]
    pairs=[]
    for arm in ARMS:
        for baseline in ['G0','V0','F0','R0','S0']:
            a={r['uid']:r for r in rows if r['arm']==arm and valid(r)}
            b={r['uid']:r for r in controls if r['arm']==baseline and valid(r)}
            ids=sorted(a.keys()&b.keys())
            pairs.append({'arm':arm,'baseline':baseline,'common_valid':len(ids),'uids':ids,
                          'candidate':metrics('rpeval',[a[u] for u in ids]),'control':metrics('rpeval',[b[u] for u in ids])})
    calls=[]
    if (RUN/'api/ledger.sqlite').exists():
        with sqlite3.connect(f'file:{RUN}/api/ledger.sqlite?mode=ro',uri=True) as db:
            calls=[json.loads(x[0]) for x in db.execute('select data from requests')]
    result={'saved_cells':len(rows),'expected_cells':16,'normal_scored':sum(map(valid,rows)),
            'status':'TERMINAL_GRID' if len(rows)==16 else 'PARTIAL','paired':pairs,
            'physical_requests':len(calls),'request_status':dict(Counter(r['status'] for r in calls)),
            'tokens':{k:sum((r.get('usage') or {}).get(k,0) or 0 for r in calls) for k in ('prompt_tokens','completion_tokens','total_tokens')},
            'unknown_usage':sum(r.get('usage') is None for r in calls),'human_reviews':0,'new_report_calls':0}
    atomic_json(OUT/'RESULTS.json',result)
    return result

def smoke_pass(plan):
    rows=[r for r in outcomes() if r['uid'] in plan['smoke_uids']]
    return len(rows)==4 and all(valid(r) for r in rows)

def execute(plan,cases):
    with runner_lock(ROOT/'runs/qamc_pa_v1/runner.lock'):
        g=CooldownGateway(RUN/'api',plan,read(OUT/'DISPATCH_POLICY.json'),STOP)
        templates,audit=load_templates(SOURCE)
        engine=RPReasonerEngine(g,RUN,templates,audit,plan['tie_seed']);evaluator=Evaluator(g,RUN)
        def run_case(c):
            task=load_task(ROOT,c);directory=RUN/'outcomes'/sha(task.uid)[:24]
            for arm in ARMS:
                path=directory/(arm+'.json')
                if path.exists():continue
                if g.disabled or (RUN/'api/STOP').exists():return
                generation=directory/(arm+'.generation.json')
                if generation.exists():row=read(generation)
                else:
                    row={'uid':task.uid,'benchmark':'rpeval','arm':arm,'public_hash':c['public_hash'],
                         'pipeline_status':'OK','answer_status':'NOT_RUN','score_status':'NOT_RUN','fallback':False}
                    try:row.update(engine.run(task,arm),answer_status='OK')
                    except Exception as exc:row.update(pipeline_status='FAILED',answer_status='FAILED',error_type=type(exc).__name__,error=str(exc))
                    atomic_json(generation,row)
                if row['answer_status']=='OK' and not g.disabled and not (RUN/'api/STOP').exists():
                    try:row.update(score=evaluator.score('rpeval',task.uid,task.query,read(ROOT/c['evaluation_path']),row['answer']),score_status='OK')
                    except Exception as exc:row.update(score_status='FAILED',score_error=str(exc))
                atomic_json(path,row)
        try:
            with ThreadPoolExecutor(max_workers=8) as pool:
                for f in as_completed([pool.submit(run_case,c) for c in cases]):f.result()
        finally:g.export();report(plan)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['freeze','test','smoke','pilot','report']);a=parser.parse_args().action
    if a=='freeze':print(json.dumps({'cases':len(freeze()['cases']),'new_calls':0}));return
    plan=read(OUT/'PLAN.json')
    if a=='report':print(json.dumps(report(plan)));return
    check(plan)
    if a=='test':print('Frozen public/reference/code/source/control checks passed; zero calls');return
    if a=='pilot' and not smoke_pass(plan):raise ValueError('Smoke has not passed')
    execute(plan,[c for c in plan['cases'] if a=='pilot' or c['uid'] in plan['smoke_uids']])
    if a=='smoke':atomic_json(OUT/'SMOKE_ACCEPTANCE.json',{'passed':smoke_pass(plan),'semantic_improvement_claimed':False})
if __name__=='__main__':main()
