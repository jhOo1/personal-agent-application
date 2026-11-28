"""Fix the Scope Actor and vary only which original memories it actually sees."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path

from expansion_audit import manifest
from expansion_run import OUT as EXPANSION,read
from qamc.common import parse_object
from trial import engine,grading,probe,sha,wire


OUT=EXPANSION.with_name('evo_qamc_fit_v1_exposure_controls_v1')
ARMS=('OFF','SELECTED','FULL')
GATE_PROMPT="""Choose the actual historical evidence to show the final assistant for this task.
The current task, supplied current facts, and task-only plan are already visible to the assistant.
Compare these actions: OFF (no history); SELECTED (only the original records in selected_ids);
FULL (all original records). Consider the usefulness of applicable soft preferences and necessary
constraints as well as the risk of introducing a new aim, affecting the wrong person, disclosing
irrelevant history, or reinforcing an unsupported assumption. Choose OFF when the task can be
served as well without this history. Choose SELECTED when its subset is sufficient and use FULL
when it provides important usable information absent from the selected subset and the benefit
justifies the extra exposure. Do not answer the task or return a rationale.
Return a JSON object with exactly one field, exposure, whose value is OFF, SELECTED, or FULL."""


def replace_sources(request,sources):
    original=json.loads(request['messages'][1]['content'])
    altered=wire(request['messages'][0]['content'],{**original,'source_evidence':sources},
                 request['max_tokens'])
    messages=altered['messages']
    if (altered!={**request,'messages':[request['messages'][0],messages[1]]}
            or json.loads(messages[1]['content'])!={**original,'source_evidence':sources}):
        raise ValueError('Exposure edit changed something other than source evidence')
    return altered


def assemble():
    prior=read(EXPANSION/'private/FROZEN.json')
    service=probe.read_reference()[1]
    if prior['service_reference_sha256']!=service:
        raise ValueError('The generation/scoring service reference changed')
    batches=[]
    cache={}
    for index,cards in enumerate(prior['batches'],1):
        folder=EXPANSION/f'batch_{index}'
        scores=read(folder/'RESULTS.json')['rows']
        actor=manifest(folder,'Actor')
        records={(r['unit']['root_id'],r['unit']['method']):(r,p)
                 for p in (folder/'Actor/visible').glob('*/record.json')
                 if (r:=read(p))['unit']['method']=='SCOPE'}
        planned={r['request_sha256']:read(p.with_name('response.json'))['answer']
                 for p in (folder/'Plan/visible').glob('*/record.json')
                 if (r:=read(p))['status']=='OK'}
        for request in manifest(folder,'Plan').values():
            if set(json.loads(request['messages'][1]['content']))!={'task'}:
                raise ValueError('Archived plan request exposed history')
        selected={r['uid']:r for r in scores if r['method']=='SCOPE'}
        batch=[]
        for card in cards:
            uid=card['uid']
            row=selected[uid]
            bundle=dict(card=card,selected=row,actors={},gate=None)
            batch.append(bundle)
            if row['actor_status']!='OK':
                continue
            key=uid,'SCOPE'
            orig=actor[key]
            receipt,path=records[key]
            previous=read(path.with_name('response.json'))['answer']
            if (receipt['status']!='OK' or receipt['request_sha256']!=sha(orig)
                    or previous!=row['answer']):
                raise ValueError('Previous successful Scope answer is not bound to its request')
            full=card['payload']['source_evidence']
            original=json.loads(orig['messages'][1]['content'])
            chosen=original['source_evidence']
            ids=[entry['memory_id'] for entry in chosen]
            if (set(original)!={'task','plan','source_evidence'}
                    or original['task']!=card['payload']['task']
                    or chosen!=[source for source in full if source['memory_id'] in ids]
                    or len(chosen)!=row['selected_sources']):
                raise ValueError('Frozen Scope input or source order changed')
            if original['plan']!=planned[card['plan_sha']]:
                raise ValueError('Scope Actor did not use the frozen no-history plan')
            bundle['actors']=dict(OFF=replace_sources(orig,[]),SELECTED=orig,
                                  FULL=replace_sources(orig,full))
            bundle['gate']=wire(GATE_PROMPT,dict(task=original['task'],plan=original['plan'],
                                source_evidence=full,selected_ids=ids),4096)
            if cache.setdefault(sha(orig),previous)!=previous:
                raise ValueError('Conflicting successful cached answer')
        batches.append(batch)
    return batches,cache,service


def fingerprint(batches,service):
    return dict(code_sha=sha(Path(__file__).read_bytes()),service_reference_sha256=service,
                batches=[[dict(uid=b['card']['uid'],domain=b['card']['domain'],
                               actor={arm:sha(w) for arm,w in b['actors'].items()},
                               selected_grade_sha=sha(b['selected']['score']),
                               gate=sha(b['gate']) if b['gate'] else None) for b in batch]
                         for batch in batches])


def scope_counts(batches,cache):
    totals={}
    wires=set()
    for batch in batches:
        for row in batch:
            c=totals.setdefault(row['card']['domain'],Counter())
            c['assigned']+=1
            c['no_scope_actor']+=not row['actors']
            if row['actors']:
                for arm in ('OFF','FULL'):
                    digest=sha(row['actors'][arm])
                    c[arm+'_exact_cache']+=digest in cache
                    if digest not in cache:
                        wires.add(digest)
    return dict(by_domain=totals,new_unique_actor_requests=len(wires))


def gate_choices(batches,pin,live):
    folder=OUT/'gate'
    folder.mkdir(parents=True,exist_ok=True)
    probe.RUN,probe.OUT,engine.OUT=folder,folder,folder
    jobs={(r['card']['uid'],'GATE'):r['gate'] for batch in batches for r in batch if r['gate']}
    engine.CAP={'Gate':162}
    identity=dict(experiment_sha256=sha(pin),service_reference_sha256=pin['service_reference_sha256'])
    ledger=[]
    with probe.runner_lock(folder/'runner.lock'):
        received=engine.stage('Gate',jobs,identity,live,ledger)
        chosen={}
        for (uid,_),reply in received.items():
            decision=None
            status=reply['status']
            if status=='OK':
                try:
                    value=parse_object(reply['answer'])
                    if set(value)=={'exposure'} and value['exposure'] in ARMS:
                        decision=value['exposure']
                except (ValueError,TypeError):
                    pass
                if decision is None:
                    status='INVALID_GATE_RESPONSE'
            chosen[uid]=dict(decision=decision,status=status,request_sha256=reply['request_sha256'])
        probe.freeze(OUT/'GATE_CHOICES.json',dict(frozen=sha(pin),choices=chosen,ledger=ledger))
    return chosen


def previous_receipts(index,name):
    """Carry exact success and terminal failure across frozen batch boundaries."""
    attempts={}
    for earlier in range(1,index):
        folder=OUT/f'batch_{earlier}'
        if not (folder/'RESULTS.json').exists():
            raise ValueError('Earlier exposure control batch has not settled')
        requests=manifest(folder,name)
        for path in (folder/name/'visible').glob('*/record.json'):
            rec=read(path)
            key=rec['unit']['root_id'],rec['unit']['method']
            digest=sha(requests[key])
            if rec['request_sha256']!=digest or rec['status']=='PENDING_DELIVERY_UNKNOWN':
                raise ValueError('Earlier exposure receipt is inconsistent or unsettled')
            answer=read(path.with_name('response.json'))['answer'] if rec['status']=='OK' else None
            result=dict(status=rec['status'],answer=answer,request_sha256=digest,
                        origin='EARLIER_EXPOSURE_BATCH')
            if attempts.setdefault(digest,result)!=result:
                raise ValueError('Earlier exposure batches contain conflicting exact attempts')
    return attempts


def batch_run(batches,cache,pin,index):
    choices=read(OUT/'GATE_CHOICES.json')
    if choices['frozen']!=sha(pin):
        raise ValueError('Gate choices do not match the frozen panel')
    folder=OUT/f'batch_{index}'
    folder.mkdir(parents=True,exist_ok=True)
    probe.RUN,probe.OUT,engine.OUT=folder,folder,folder
    rows=[]
    batch=batches[index-1]
    budget=Counter(r['card']['domain'] for r in batch)
    engine.CAP={'Actor':len(batch)*2, engine.RPE:budget['RPEval']*2,
                'BenchAttrs':budget['BenchPreS']*12, 'PersistNative':budget['PersistBench']*2}
    identity=dict(experiment_sha256=sha([pin,index]),service_reference_sha256=pin['service_reference_sha256'])
    ledger=[]
    with probe.runner_lock(folder/'runner.lock'):
        jobs={(b['card']['uid'],arm):b['actors'][arm] for b in batch if b['actors']
              for arm in ('OFF','FULL')}

        def stage(name,requests,cached=None):
            attempts=previous_receipts(index,name)
            reuse=dict(cached or {})
            reuse.update({digest:reply['answer'] for digest,reply in attempts.items() if reply['status']=='OK'})
            pending,prior_failures={},{}
            for key,request in requests.items():
                earlier=attempts.get(sha(request))
                if earlier and earlier['status']!='OK':
                    prior_failures[key]=earlier
                else:
                    pending[key]=request
            results=engine.stage(name,pending,identity,True,ledger,reuse) if pending else {}
            return {**results,**prior_failures}

        replies=stage('Actor',jobs,cache)
        for b in batch:
            card=b['card']
            uid=card['uid']
            for arm in ('OFF','FULL'):
                reply=replies.get((uid,arm),{})
                same_scope=reply.get('status')=='OK' and reply['answer']==b['selected']['answer']
                row=dict(uid=uid,method=arm,benchmark=card['domain'],stratum=card['stratum'],
                         sources=card['payload']['source_evidence'],
                         actor_status=reply.get('status','NO_SCOPE_ACTOR'),answer=reply.get('answer'),
                         score=None,actor_request_sha256=reply.get('request_sha256'))
                if same_scope:
                    row.update(score=b['selected']['score'],score_flags=b['selected'].get('score_flags'),
                               exact_selected_response=True)
                rows.append(row)
        grading([row for row in rows if not row.get('exact_selected_response')],stage)
        probe.freeze(folder/'RESULTS.json',dict(rows=rows,ledger=ledger))


if __name__=='__main__':
    cli=ArgumentParser(description=__doc__)
    cli.add_argument('action',choices=('freeze','check','gate','batch'))
    cli.add_argument('--batch',type=int,choices=(1,2,3))
    args=cli.parse_args()
    batches,cache,service=assemble()
    actual=fingerprint(batches,service)
    path=OUT/'private/FROZEN.json'
    if args.action=='freeze':
        path.parent.mkdir(parents=True,exist_ok=True)
        probe.freeze(path,actual)
    elif read(path)!=actual:
        raise ValueError('Exposure control manifest drift')
    if args.action=='gate':
        print(Counter(r['decision'] for r in gate_choices(batches,actual,live=True).values()))
    if args.action=='batch':
        if args.batch is None:
            cli.error('--batch is required for batch execution')
        batch_run(batches,cache,actual,args.batch)
    print(json.dumps(scope_counts(batches,cache),indent=2))
