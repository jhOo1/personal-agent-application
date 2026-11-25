"""Frozen PersistBench author-prompt controls on the existing 60 development cases.

No new samples, source encoders, embeddings or Store writes. Real dispatch waits
for terminal P2 and holds its process lock; complete systems and shared Actor
filtering remain separate table tracks. prepare/report are zero-call.
"""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT),str(ROOT/'scripts')]
import qamc_contextual_match_development as parent
import qamc_contextual_match_external_run as ext
from qamc.common import sha
from qamc.bace.runtime import runner_lock
from qamc.contextual_match.persist_author_bridge import PersistAuthorBridge,METHODS,COMMIT
from qamc.contextual_match.phase_runtime import PhaseDispatcher,model_block
from qamc.transport_helpers import atomic_json,read_reference
from proposals.qamc_protocol_alignment.sampling import sampling_key

OUT=parent.audit.OUT/'persist_author_controls_v1'
RUN=ROOT/'runs'/parent.audit.OUT.name/OUT.name
STAGES={'Selector':8192,'Actor':4096}
frozen,read=parent.frozen,parent.audit.read


def unit(plan,uid,method,stage):
    return {'protocol_sha256':sha(plan['protocols'][model_block(stage)]),'root_id':uid,
        'method':method,'stage':stage,'replicate':0}


def job(plan,uid,method,stage,body):return {'unit':unit(plan,uid,method,stage),'request':body}


def check(plan,service=True):
    if service and read_reference()[1]!=plan['service_reference_sha256']:
        raise ValueError('Persist author service block changed')
    if (plan['methods']!=list(METHODS) or len(plan['cases'])!=60
            or {c['benchmark'] for c in plan['cases']}!={'persistbench'}
            or len(set(plan['allowed_unit_keys']))!=plan['logical_guard']):
        raise ValueError('Frozen Persist author scope/allocation changed')
    if any(parent.audit.file_sha(ROOT/p)!=h for p,h in plan['files'].items()):
        raise ValueError('Frozen Persist author dependency changed')


def prepare():
    path=OUT/'PLAN.json'
    if path.exists():plan=read(path);check(plan);return plan
    prior=read(parent.OUT/'PLAN.json');cases=[c for c in prior['cases'] if c['benchmark']=='persistbench']
    ids={c['uid'] for c in cases};bridge=PersistAuthorBridge(parent.persist.UP)
    protocols={key:{'namespace':parent.audit.OUT.name+'/'+OUT.name+'/'+key,'model':model,
        'concurrency':8,'spacing_seconds':3.1,'stream_cooldown_seconds':300,'automatic_retries':0,
        'schema_repairs':0,'stages':{s:{'temperature':0,'max_tokens':cap} for s,cap in stages.items()}}
        for key,model,stages in (('qwen','qwen3.8-flash',STAGES),('gpt41','gpt-4.1',{'PersistJudge':4096}))}
    for case in cases:bridge.require_public(parent.smoke.task_for(case))
    plan={'cases':cases,'waves':[[u for u in w if u in ids] for w in prior['waves']],
        'methods':list(METHODS),'protocols':protocols,'parent_plan_sha256':sha(prior),
        'service_reference_sha256':prior['service_reference_sha256'],'rpeval_scorer':prior['rpeval_scorer'],
        'author_manifest':bridge.manifest(),'new_samples':0,'source_encoder_calls':0,
        'not_confirmation':True,'semantic_revision_cycle':0,'parent_terminal_required':True,
        'native_protocol_parity_proven':False,'persist_track':prior['persist_track'],
        'table_tracks':{'shared_actor':['PB_FILTER_COMMON'],
            'author_generator_adapted_model':[m for m in METHODS if m!='PB_FILTER_COMMON']}}
    keys=set()
    for case in cases:
        uid=case['uid'];keys.add(sampling_key(unit(plan,uid,'PB_FILTER_SHARED','Selector')))
        for method in METHODS:
            for stage in ('Actor','PersistJudge'):keys.add(sampling_key(unit(plan,uid,method,stage)))
    plan['allowed_unit_keys']=sorted(keys);plan['logical_guard']=len(keys)
    pins=[Path(__file__),parent.OUT/'PLAN.json',parent.audit.OUT/'PROMPTS.json',
        *[ROOT/p for p in prior['files']]]
    for module in list(sys.modules.values()):
        file=getattr(module,'__file__',None)
        if file:
            p=Path(file).resolve()
            if p.is_relative_to(ROOT) and p.suffix=='.py':pins.append(p)
    plan['files']=parent.audit.pins(pins);check(plan);frozen(path,plan)
    frozen(OUT/'AUTHOR_SOURCE_LOCK.json',bridge.manifest())
    frozen(OUT/'COST_FORECAST.json',{'maximum_logical_positions':len(keys),'selector_positions':60,
        'actor_positions':360,'judge_positions':360,'source_or_task_encoder_positions':0,
        'model_calls_from_prepare':0,'new_global_budget_created':False,'currency_cost':'UNKNOWN',
        'repeated_native_3_1_sampling_is_not_in_this_development_block':True})
    print(json.dumps({'methods':list(METHODS),'cases':len(cases),'logical_guard':len(keys),'new_model_calls':0}))
    return plan


def observed(runtimes,j):
    value=runtimes[model_block(j['unit']['stage'])].output(j['unit'])
    if value and value['request_sha256']!=sha(j['request']):raise ValueError('Persist author saved wire drift')
    return value


def collect_wave(plan,wave,runtimes,dispatch,bridge):
    ids=set(plan['waves'][wave]);cases=[c for c in plan['cases'] if c['uid'] in ids]
    tasks={c['uid']:parent.smoke.task_for(c) for c in cases}
    base=read(parent.audit.OUT/'PROMPTS.json')['base'];readers=[];rows=[];actors=[]
    for c in cases:
        task=tasks[c['uid']]
        readers.append(job(plan,task.uid,'PB_FILTER_SHARED','Selector',bridge.filter_request(task)))
    dispatch(f'w{wave:02d}_selectors',readers)
    for c in cases:
        task=tasks[c['uid']];j=next(j for j in readers if j['unit']['root_id']==task.uid)
        value=observed(runtimes,j);selected=None;error=None
        if value and value['status']=='OK':
            try:selected=bridge.parse_filter(task,value['response']['answer'])
            except (ValueError,TypeError,KeyError) as exc:error={'error_type':type(exc).__name__,'error':str(exc)}
        for method in METHODS:
            filtering=method.startswith('PB_FILTER_')
            row={'uid':task.uid,'benchmark':'persistbench','group_id':c['group_id'],'method':method,
                'read_status':value['status'] if filtering and value else 'UNISSUED' if filtering else 'NOT_REQUIRED',
                'actor_status':'UNISSUED','score':None}
            rows.append(row)
            if filtering and selected is None:
                if error:row.update(read_status='INVALID',read_error=error)
                continue
            built=bridge.actor(task,method,base['actor'],selected)
            row.update(read_status='VALID' if filtering else 'NOT_REQUIRED',view=built['view'],
                actor_request=built['request'],actor_request_sha256=sha(built['request']),
                table_track=built['table_track'])
            if filtering:row['filter_selected_ids']=selected
            actors.append(job(plan,task.uid,method,'Actor',built['request']))
    dispatch(f'w{wave:02d}_actors',actors)
    # This helper reads labels/rubrics only after saved Actor outputs exist.
    ext.grade_rows(plan,cases,tasks,rows,actors,runtimes,dispatch,wave)
    return {'wave':wave,'rows':rows,'representations':[]}


def main(action,max_waves=None):
    plan=read(OUT/'PLAN.json') if action=='report' else prepare()
    if action=='prepare':return
    check(plan,service=action!='report');bridge=PersistAuthorBridge(parent.persist.UP)
    if bridge.manifest()!=plan['author_manifest']:raise ValueError('Pinned author asset identity drift')
    executor=PhaseDispatcher(ROOT,OUT,RUN,plan,check,parent.audit.OUT.name)
    def dispatch(name,jobs):
        if action=='run':executor.dispatch(name,jobs)
    from contextlib import nullcontext
    if action=='run':ext.assert_parent_terminal()
    parent_context=runner_lock(parent.RUN/'runner.lock') if action=='run' else nullcontext()
    with parent_context,runner_lock(RUN/'runner.lock'):
        completed=[]
        for wave in range(len(plan['waves'])):
            path=OUT/'waves'/f'{wave:02d}.json'
            if path.exists():
                completed.append(wave)
                if action=='report' and collect_wave(plan,wave,executor.runtimes,lambda *_:None,bridge)!=read(path):
                    raise ValueError('Persist author read-only replay changed')
                continue
            if action=='report':continue
            frozen(path,collect_wave(plan,wave,executor.runtimes,dispatch,bridge));completed.append(wave)
            if max_waves is not None and len(completed)>=max_waves:break
        result={'completed_waves':completed,'expected_waves':len(plan['waves']),
            'logical_guard':plan['logical_guard'],'report_model_calls':0 if action=='report' else None,
            'goal_complete':False}
        atomic_json(OUT/'RUN_STATE.json',{'phase':'AUTHOR_CONTROLS_TERMINAL' if len(completed)==len(plan['waves']) else 'AUTHOR_CONTROLS_CHECKPOINT',
            **result,'active_process':None})
        print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run','report'));parser.add_argument('--max-waves',type=int)
    args=parser.parse_args();main(args.action,args.max_waves)
