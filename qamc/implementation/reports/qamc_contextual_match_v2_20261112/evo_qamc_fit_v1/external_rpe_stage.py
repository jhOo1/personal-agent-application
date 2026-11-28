"""Replay a completed RPEval scoring stage during the joint run."""
from argparse import ArgumentParser
from collections import Counter
import json

from qamc_rpeval_terminal_judge_sensitivity import inspect
from rpe_stage import read
from summarize import metrics
from trial import HERE, RUN, archive, engine, probe, sha

OUT = RUN.with_name(RUN.name+'_self_recheck')
METHOD = 'SELF_RECHECK'
RUNS = {'SELF_RECHECK':OUT, 'TASK_ONLY':RUN.with_name(RUN.name+'_task_only'),
        'TASK_PLAN_SELECTED':RUN.with_name(RUN.name+'_crossover')}


def replay(method=METHOD):
    out = RUNS[method]
    plan = read(RUN/'private/FROZEN.json')
    pin = read(out/'private/FROZEN.json')
    manifest_file = out/'private'/f'{engine.RPE}_MANIFEST.json'
    if not manifest_file.exists():
        raise SystemExit('The RPEval scoring manifest has not been dispatched')
    manifest = read(manifest_file)
    receipts = [read(p) for p in (out/engine.RPE/'visible').glob('*/record.json')]
    if len(receipts)!=len(manifest['units']) or any(r['status']=='PENDING_DELIVERY_UNKNOWN' for r in receipts):
        raise SystemExit('The RPEval scoring stage is still live')
    cards = [r for r in plan['rows'] if r['domain']=='RPEval']
    saved = {}
    for path in (out/'Actor/visible').glob('*/record.json'):
        rec = read(path)
        if rec['status']=='OK':
            saved[rec['unit']['root_id']] = read(path.with_name('response.json'))['answer']
    rows = [dict(uid=c['uid'],method=method,actor_status='OK' if c['uid'] in saved else 'ABSENT',
                 answer=saved.get(c['uid']),score=None) for c in cards]
    metadata = {r['uid']:r for r in read(archive.v41.OUT/'FROZEN.json')['roots']}
    roots = {card['uid']:dict(original_sources=card['payload']['source_evidence'],
              archived=metadata.get(card['uid'],{}).get('archived',{})) for card in cards}
    ledger=[]
    probe.RUN,probe.OUT,engine.OUT = out,out/'private',out/'private'
    engine.CAP={engine.RPE:len(cards)}
    identity = dict(experiment_sha256=sha(pin),service_reference_sha256=pin['service_reference_sha256'])

    def stage(name,jobs,cache=None):
        return engine.stage(name,jobs,identity,False,ledger,cache) if jobs else {}

    engine.grade_rpe(roots,rows,stage)
    labels = {r['uid']:r['labels'] for r in read(HERE.parent/'ipe_c_two_endpoint_completion_v1'/'RESULTS.json')['rows']}
    seeds = {(r['uid'],r['method']):r for r in read(RUN/'RESULTS.json')['rows']}
    comparators = ('GENERIC','TASK_ACTIONS')
    if method=='TASK_PLAN_SELECTED':
        seeds.update({(r['uid'],r['method']):r for r in read(RUNS['TASK_ONLY']/'RESULTS.json')['rows']})
        comparators += ('TASK_ONLY',)
    tally = {k:{a:Counter() for a in ('BASE',*comparators,method)}
             for k in ('all','all_A','B_only','contains_C','unflagged')}
    common=Counter()
    fixed_plan={a:Counter() for a in ('TASK_ONLY',method)}
    fixed_count=0
    for card,row in zip(cards,rows,strict=True):
        uid=card['uid']
        companions = {a:seeds[uid,a] for a in comparators}
        grades = {'BASE':card['base_score'],method:row['score']}
        grades.update({a:cell['score'] for a,cell in companions.items()})
        values = {a:metrics(card,grade) for a,grade in grades.items()}
        if method=='TASK_PLAN_SELECTED' and values[method] is not None and values['TASK_ONLY'] is not None:
            assert values[method]['positions']==values['TASK_ONLY']['positions']
            fixed_count+=1
            for arm in fixed_plan:
                fixed_plan[arm].update(values[arm])
        if not all(values.values()):
            continue
        assert len({v['positions'] for v in values.values()})==1
        flags = inspect({**row,'native_fields':row['score'],
                        'raw_scores':{archive.v41.NATIVE:row['judge']['answer']}},labels[uid])['flags']
        buckets = ('all',card['stratum'])
        if flags==[] and card['base_flags']==[] and all(s.get('score_flags')==[] for s in companions.values()):
            buckets += ('unflagged',)
        for bucket in buckets:
            common[bucket]+=1
            for name,value in values.items():
                tally[bucket][name].update(value)
    report = dict(assigned=len(cards),common=common,paired=tally,
                successful_actors=len(saved.keys() & {r['uid'] for r in cards}),
                usable_direct_grades=sum(metrics(card,row['score']) is not None for card,row in zip(cards,rows,strict=True)),
                physical_scoring=len(ledger),status=Counter(r['status'] for r in ledger),
                reported_tokens=sum((r.get('usage') or {}).get('total_tokens') or 0 for r in ledger))

    if method=='TASK_PLAN_SELECTED':
        report['fixed_plan_pair']={'common':fixed_count,'scores':fixed_plan}
    return report


if __name__=='__main__':
    cli = ArgumentParser(description=__doc__)
    cli.add_argument('--method',choices=RUNS,default=METHOD)
    options = cli.parse_args()
    print(json.dumps(replay(options.method),indent=2))
