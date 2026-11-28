"""Compare the frozen scope edit, its fixed-pipeline parent, and released direct selection."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path

from expansion_inventory import qualify
from self_recheck import released, input_for, exact_selector_cache
from task_only import PLAN
from trial import ACTOR, HERE, RUN, engine, grading, probe, sha, wire

OUT=RUN.with_name(RUN.name+'_expansion')
MUTATION=RUN.with_name(RUN.name+'_actor_mutation_e72109af950a')
ARMS=('PLAN_SELECTED','SCOPE','DIRECT')


def read(path):
    return json.loads(path.read_text())


def freeze_inputs():
    eligible,banks,audit=qualify()
    assert audit==read(HERE/'EXPANSION_INVENTORY.json')
    revision,prompt,parser=released()
    edit=read(MUTATION/'private/INSTRUCTIONS.json')['scope_of_influence']
    assert edit==read(HERE/'ACTOR_MUTATION_CONTRACT.json')['added_instructions']['scope_of_influence']
    rows=[]
    for item in sorted(eligible,key=lambda r:sha(['expansion_fixed_v1',r['uid']])):
        root=banks[item['domain']][item['uid']]['root']
        card=banks[item['domain']][item['uid']]
        payload={'task':root['public_task'],'source_evidence':root['original_sources']}
        records={**item,'payload':payload,'base_score':card['base_score'],'base_flags':card['base_flags']}
        records['plan_sha']=sha(wire(PLAN,{'task':payload['task']},4096))
        records['selection_sha']=sha(wire(prompt,input_for(records),8192))
        rows.append(records)
    assert len(rows)==162
    # Interleave benchmark slices. BenchPreS shares one profile and stays visible as a small descriptive arm.
    quotas={'RPEval':(42,42,42),'PersistBench':(11,11,10),'BenchPreS':(4,0,0)}
    batches=[[] for _ in range(3)]
    for domain,counts in quotas.items():
        domain_rows=[r for r in rows if r['domain']==domain]
        offset=0
        for i,n in enumerate(counts):
            batches[i]+=domain_rows[offset:offset+n]
            offset+=n
        assert offset==len(domain_rows)
    pin=dict(batches=batches,selector_revision=revision,scope_edit=edit,
             inventory_sha=sha(audit),code_sha=sha(Path(__file__).read_bytes()),
             service_reference_sha256=probe.read_reference()[1])
    return pin,prompt,parser


def run_batch(pin,prompt,parser,index):
    cards=pin['batches'][index-1]
    directory=OUT/f'batch_{index}'
    (directory/'private').mkdir(parents=True,exist_ok=True)
    probe.RUN,probe.OUT,engine.OUT=directory,directory/'private',directory/'private'
    counts=Counter(c['domain'] for c in cards)
    engine.CAP={'Plan':len(cards),'Select':len(cards),'Actor':3*len(cards),
                engine.RPE:3*counts['RPEval'],'BenchAttrs':18*counts['BenchPreS'],
                'PersistNative':3*counts['PersistBench']}
    ledger=[]
    identity=dict(experiment_sha256=sha([pin,index]),service_reference_sha256=pin['service_reference_sha256'])
    with probe.runner_lock(directory/'runner.lock'):
        def stage(name,jobs,cache=None):
            return engine.stage(name,jobs,identity,True,ledger,cache) if jobs else {}

        requests_plan={}
        requests_select={}
        for card in cards:
            uid=card['uid']
            plan=wire(PLAN,{'task':card['payload']['task']},4096)
            select=wire(prompt,input_for(card),8192)
            assert sha(plan)==card['plan_sha'] and sha(select)==card['selection_sha']
            requests_plan[uid,'shared']=plan
            requests_select[uid,'shared']=select
        planned=stage('Plan',requests_plan)
        decisions=stage('Select',requests_select,exact_selector_cache())
        requests,targets={},{}
        direct_prompt=ACTOR.replace('Use the plan as guidance. Verify any suggestion in it against the current task and supplied original memory. ',
                        'Use the selected historical evidence where it is applicable. ')
        scope_prompt=ACTOR+'\n\n'+pin['scope_edit']['instruction']
        for card in cards:
            uid=card['uid']
            selection=decisions[uid,'shared']
            plan=planned[uid,'shared']
            for arm in ARMS:
                targets[uid,arm]=dict(uid=uid,method=arm,benchmark=card['domain'],group=card['group'],
                     stratum=card['stratum'],sources=card['payload']['source_evidence'],
                     actor_status='NOT_DISPATCHED',score=None,answer=None,
                     plan_status=plan['status'],selection_status=selection['status'],
                     selection_origin=selection['origin'])
            if selection['status']!='OK':
                continue
            numbered=input_for(card)['retrieved_memories']
            try:
                chosen=parser(selection['answer'],numbered,partition=False)
            except (ValueError,TypeError,KeyError,AttributeError):
                for arm in ARMS:
                    targets[uid,arm]['selection_status']='INVALID_ID_RESPONSE'
                continue
            selected=[original for mem,original in zip(numbered,card['payload']['source_evidence'],strict=True)
                      if mem['memory_id'] in chosen]
            context={'task':card['payload']['task'],'source_evidence':selected}
            for arm in ARMS:
                row=targets[uid,arm]
                row['selected_sources']=len(selected)
                try:
                    if arm=='DIRECT':
                        requests[uid,arm]=wire(direct_prompt,context,8192)
                    elif plan['status']=='OK':
                        requests[uid,arm]=wire(scope_prompt if arm=='SCOPE' else ACTOR,{**context,'plan':plan['answer']},8192)
                except ValueError as error:
                    row['input_error']=str(error)
        for key,reply in stage('Actor',requests).items():
            targets[key].update(actor_status=reply['status'],answer=reply.get('answer'))
        results=list(targets.values())
        grading(results,stage)
        probe.freeze(directory/'RESULTS.json',dict(rows=results,ledger=ledger))
        print('Settled expansion',index,counts,Counter((r['unit']['stage'],r['status']) for r in ledger),flush=True)


if __name__=='__main__':
    cli=ArgumentParser(description=__doc__)
    cli.add_argument('action',choices=('freeze','check','run'))
    cli.add_argument('--batch',type=int,choices=(1,2,3))
    args=cli.parse_args()
    configuration=freeze_inputs()
    path=OUT/'private/FROZEN.json'
    if args.action=='freeze':
        path.parent.mkdir(parents=True,exist_ok=True)
        probe.freeze(path,configuration[0])
    else:
        assert read(path)==configuration[0]
        if args.action=='run':
            if args.batch is None:
                cli.error('Specify the frozen batch to run')
            run_batch(*configuration,args.batch)
    print([Counter(c['domain'] for c in b) for b in configuration[0]['batches']],flush=True)
