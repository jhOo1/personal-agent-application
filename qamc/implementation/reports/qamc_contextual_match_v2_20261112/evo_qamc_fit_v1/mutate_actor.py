"""Create and evaluate two offline-feedback edits to an existing Actor instruction."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path

from evolution_feedback import evidence
from mutation_contract import MODES, candidate_hash, instruction_packet, validate
from trial import RUN, engine, grading, probe, sha, wire

OUT = RUN.with_name(RUN.name+'_actor_mutation')
METHODS = {
    'GENERIC':('', 'GENERIC'),
    'TASK_ACTIONS':('', 'TASK_ACTIONS'),
    'SELF_RECHECK':('_self_recheck', 'SELF_RECHECK'),
    'TASK_ONLY':('_task_only', 'TASK_ONLY'),
    'TASK_PLAN_SELECTED':('_crossover', 'TASK_PLAN_SELECTED'),
    'SELECTED_GENERIC':('_selected_planning', 'GENERIC'),
    'SELECTED_TASK_ACTIONS':('_selected_planning', 'TASK_ACTIONS'),
}
PROPOSER = """You revise the instruction for a personal assistant. Use offline scored answer contrasts solely to learn a general instruction, not to answer any example or reproduce its wording. Some scores or attributions may be inconsistent. Use textual differences to judge which changes really affect recipient, facts, decisions, appropriate expression, or disclosure. Produce two distinct English instructions, each a short addition to the actual existing Actor instruction. One must restrict the scope of historical influence to authorized decisions, including shared decisions and public assertions. The other must help realize legitimate historical requirements in the deliverable while protecting completeness and explicit constraints. Each should generalize to any task and avoid examples, field IDs, dataset names, evaluation terms and names. Return one JSON object with exactly the string keys scope_of_influence and realize_applicable_preference."""


def read(path):
    return json.loads(path.read_text())


def actors(directory, method):
    possible = [directory/'Actor_MANIFEST.json',directory/'private/Actor_MANIFEST.json']
    files = [p for p in possible if p.exists()]
    assert len(files)<=1
    if not files:
        return {}
    return {u['unit']['root_id']:u['request'] for u in read(files[0])['units'] if u['unit']['method']==method}


def inherited_wires(parent):
    suffix,name = METHODS[parent]
    directory = RUN.with_name(RUN.name+suffix)
    chosen=actors(directory,name)
    if parent=='TASK_PLAN_SELECTED':
        prior=read(directory/'RESULTS.json')
        from_task=actors(RUN.with_name(RUN.name+'_task_only'),'TASK_ONLY')
        for row in prior['rows']:
            if row.get('origin')=='EXACT_TASK_ONLY':
                chosen[row['uid']]=from_task[row['uid']]
    elif suffix=='_selected_planning':
        seed=actors(RUN,name)
        for row in read(directory/'private/FROZEN.json')['exact']:
            chosen[row['uid']]=seed[row['uid']]
    return chosen


def prepare(summary):
    feedback=evidence(summary)
    parent=feedback['balanced_parent']
    wires=inherited_wires(parent)
    if not wires or not feedback['examples']:
        raise ValueError('No verified parent request or scored outcome contrast')
    systems={v['messages'][0]['content'] for v in wires.values()}
    assert len(systems)==1
    current=systems.pop()
    packet=instruction_packet(feedback,current)
    # Bound the proposal so scored development traces fit the inherited gateway limit.
    for case in packet['offline_contrasts']:
        for field in ('current','alternative'):
            case[field]=case[field][:4500]
    while True:
        try:
            request=wire(PROPOSER,packet,2048)
            break
        except ValueError:
            if len(packet['offline_contrasts'])<=3:
                raise
            packet['offline_contrasts'].pop()
    original=read(RUN/'private/FROZEN.json')
    pin=dict(parent=parent,card_sha=sha(original),prompt_sha=sha(request),evidence_sha=sha(feedback),
             wires_sha=sha(wires),code_sha256=sha(Path(__file__).read_bytes()),
             contract_sha256=sha(Path(__file__).with_name('mutation_contract.py').read_bytes()),
             service_reference_sha256=probe.read_reference()[1])
    return pin,request,feedback,wires,original['rows']


def execute(pin,request,feedback,wires,cards):
    probe.RUN,probe.OUT,engine.OUT=OUT,OUT/'private',OUT/'private'
    engine.CAP={'Propose':1,'Actor':80,engine.RPE:32,'BenchAttrs':144,'PersistNative':24}
    ledger=[]
    identity=dict(experiment_sha256=sha(pin),service_reference_sha256=pin['service_reference_sha256'])
    with probe.runner_lock(OUT/'runner.lock'):
        def stage(name,jobs,cache=None):
            return engine.stage(name,jobs,identity,True,ledger,cache) if jobs else {}
        key=('offline_joint_feedback','actor_policy')
        proposal=stage('Propose',{key:request})[key]
        if proposal['status']!='OK':
            probe.freeze(OUT/'PROPOSER_FAILURE.json',dict(status=proposal['status'],ledger=ledger))
            return
        try:
            instructions=validate(proposal['answer'],feedback)
        except ValueError as error:
            probe.freeze(OUT/'PROPOSER_FAILURE.json',dict(status='REJECTED',reason=str(error),ledger=ledger))
            return
        probe.freeze(OUT/'private/INSTRUCTIONS.json',
                     {name:dict(instruction=text,sha256=candidate_hash(pin['parent'],text,name))
                      for name,text in instructions.items()})
        jobs,targets={},{}
        for card in cards:
            uid=card['uid']
            for name,text in instructions.items():
                key=(uid,'MUTATE_'+name)
                targets[key]=dict(uid=uid,method=key[1],benchmark=card['domain'],group=card['group'],
                             stratum=card['stratum'],sources=card['payload']['source_evidence'],
                             actor_status='PARENT_NOT_DISPATCHED',answer=None,score=None)
                if uid in wires:
                    parent=wires[uid]
                    messages=parent['messages']
                    jobs[key]=dict(parent,messages=[dict(messages[0],content=messages[0]['content']+'\n\n'+text),*messages[1:]])
        for key,receipt in stage('Actor',jobs).items():
            targets[key].update(actor_status=receipt['status'],answer=receipt.get('answer'))
        outcomes=list(targets.values())
        grading(outcomes,stage)
        probe.freeze(OUT/'RESULTS.json',dict(rows=outcomes,ledger=ledger,parent=pin['parent']))
        print(Counter((r['unit']['stage'],r['status']) for r in ledger),flush=True)


if __name__=='__main__':
    cli=ArgumentParser(description=__doc__)
    cli.add_argument('action',choices=('freeze','check','run'))
    cli.add_argument('summary',type=Path)
    args=cli.parse_args()
    trial=prepare(read(args.summary))
    OUT=OUT.with_name(OUT.name+'_'+sha(trial[0])[:12])
    path=OUT/'private/FROZEN.json'
    if args.action=='freeze':
        path.parent.mkdir(parents=True,exist_ok=True)
        probe.freeze(path,trial[0])
    else:
        assert read(path)==trial[0]
        if args.action=='run':
            execute(*trial)
    print(dict(parent=trial[0]['parent'],assigned=len(trial[-1]),inherited_requests=len(trial[-2]),run_directory=str(OUT)))
