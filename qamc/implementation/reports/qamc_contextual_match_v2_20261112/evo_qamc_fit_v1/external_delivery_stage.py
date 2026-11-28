"""Replay a completed BenchPreS or PersistBench grading stage."""
from argparse import ArgumentParser
from collections import Counter
import json

from external_rpe_stage import RUNS, METHOD
from rpe_stage import read
from summarize import metrics
from summarize_reassembly import aligned
from trial import RUN, engine, grading, probe, sha

STAGES={'BenchPreS':'BenchAttrs','PersistBench':'PersistNative'}


def terminal(out,stage):
    manifest=out/'private'/f'{stage}_MANIFEST.json'
    if not manifest.exists():
        return False
    physical=[read(p) for p in (out/stage/'visible').glob('*/record.json')]
    return len(physical)==len(read(manifest)['units']) and all(
        r['status']!='PENDING_DELIVERY_UNKNOWN' for r in physical)


def replay(domain, private=False, method=METHOD):
    out = RUNS[method]
    methods = ('BASE','GENERIC','TASK_ACTIONS',method)
    name=STAGES[domain]
    if not terminal(out,name):
        raise SystemExit(f'{domain} scoring is still live')
    pin=read(out/'private/FROZEN.json')
    cards=[c for c in read(RUN/'private/FROZEN.json')['rows'] if c['domain']==domain]
    actor={}
    for path in (out/'Actor/visible').glob('*/record.json'):
        receipt=read(path)
        if receipt['status']=='OK':
            actor[receipt['unit']['root_id']]=read(path.with_name('response.json'))['answer']
    rows=[dict(uid=c['uid'],method=method,benchmark=domain,stratum=c['stratum'],score=None,
               actor_status='OK' if c['uid'] in actor else 'ABSENT',answer=actor.get(c['uid']))
          for c in cards]
    identity=dict(experiment_sha256=sha(pin),service_reference_sha256=pin['service_reference_sha256'])
    probe.RUN,probe.OUT,engine.OUT=out,out/'private',out/'private'
    engine.CAP={name:72 if domain=='BenchPreS' else 12}
    ledger=[]
    def stage(stage_name,jobs,cache=None):
        return engine.stage(stage_name,jobs,identity,False,ledger,cache) if jobs else {}
    grading(rows,stage)
    archives={(r['uid'],r['method']):r for r in read(RUN/'RESULTS.json')['rows']}
    table={arm:Counter() for arm in methods}
    by_track={}
    common=0
    available=0
    private_rows=[]
    if private:
        exposure={u['unit']['root_id']:json.loads(u['request']['messages'][1]['content'])['source_evidence']
                  for u in read(out/'private/Actor_MANIFEST.json')['units']}
    for c,row in zip(cards,rows,strict=True):
        uid=c['uid']
        grades={'BASE':c['base_score'],method:row['score']}
        grades.update({a:archives[uid,a]['score'] for a in ('GENERIC','TASK_ACTIONS')})
        values={a:metrics(c,s) for a,s in grades.items()}
        available+=values[method] is not None
        if not aligned(values,methods):
            continue
        common+=1
        track=by_track.setdefault(c['stratum'],{a:Counter() for a in methods})
        for a,v in values.items():
            table[a].update(v)
            track[a].update(v)
        if private:
            private_rows.append(dict(uid=uid,task=c['payload']['task'],actual_sources=exposure.get(uid),
               answer=row['answer'],scores=grades,plan_answers={a:archives[uid,a]['answer'] for a in ('GENERIC','TASK_ACTIONS')}))
    if private:
        (out/'private'/f'{domain}_CONTRASTS.json').write_text(json.dumps(private_rows,ensure_ascii=False,indent=2))
    return dict(benchmark=domain,assigned=len(cards),common=common,usable_direct_grades=available,
                paired=table,by_track=by_track,physical_score_requests=len(ledger),
                transport_status=Counter(r['status'] for r in ledger),
                reported_tokens=sum((r.get('usage') or {}).get('total_tokens') or 0 for r in ledger),
                unknown_usage=sum((r.get('usage') or {}).get('total_tokens') is None for r in ledger))


if __name__=='__main__':
    cli=ArgumentParser(description=__doc__)
    cli.add_argument('domain',choices=STAGES)
    cli.add_argument('--private',action='store_true')
    cli.add_argument('--method',choices=RUNS,default=METHOD)
    args=cli.parse_args()
    print(json.dumps(replay(args.domain,args.private,args.method),indent=2))
