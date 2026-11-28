"""Replay a completed grading stage and compare both edits against their unchanged parent."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path

from mutate_actor import METHODS, MODES
from summarize import metrics
from summarize_reassembly import aligned
from trial import RUN, engine, grading, probe, sha

STAGES={'RPEval':engine.RPE,'BenchPreS':'BenchAttrs','PersistBench':'PersistNative'}
ARMS=tuple('MUTATE_'+mode for mode in MODES)


def read(path):
    return json.loads(path.read_text())


def graded(run, stage):
    manifest=run/'private'/f'{stage}_MANIFEST.json'
    if not manifest.exists():
        return False
    receipts=[read(p) for p in (run/stage/'visible').glob('*/record.json')]
    return len(receipts)==len(read(manifest)['units']) and all(
        r['status']!='PENDING_DELIVERY_UNKNOWN' for r in receipts)


def replay(run, domain, private=False):
    name=STAGES[domain]
    if not graded(run,name):
        raise SystemExit(f'{domain} score stage still pending')
    pin=read(run/'private/FROZEN.json')
    parent=pin['parent']
    suffix=METHODS[parent][0]
    parent_directory=RUN.with_name(RUN.name+suffix)
    file='COMBINED.json' if suffix=='_selected_planning' else 'RESULTS.json'
    unchanged={r['uid']:r for r in read(parent_directory/file)['rows'] if r['method']==parent}
    cards=[c for c in read(RUN/'private/FROZEN.json')['rows'] if c['domain']==domain]
    ids={c['uid'] for c in cards}
    current={}
    for file in (run/'Actor/visible').glob('*/record.json'):
        rec=read(file)
        uid,arm=(rec['unit'][k] for k in ('root_id','method'))
        if uid in ids and rec['status']=='OK':
            current[uid,arm]=read(file.with_name('response.json'))['answer']
    rows=[dict(uid=c['uid'],method=arm,benchmark=domain,stratum=c['stratum'],sources=c['payload']['source_evidence'],
               actor_status='OK' if (c['uid'],arm) in current else 'ABSENT',answer=current.get((c['uid'],arm)),score=None)
          for c in cards for arm in ARMS]
    probe.RUN,probe.OUT,engine.OUT=run,run/'private',run/'private'
    engine.CAP={name:{'RPEval':32,'BenchPreS':144,'PersistBench':24}[domain]}
    identity=dict(experiment_sha256=sha(pin),service_reference_sha256=pin['service_reference_sha256'])
    ledger=[]

    def stage(stage_name,batch,cache=None):
        return engine.stage(stage_name,batch,identity,False,ledger,cache) if batch else {}

    grading(rows,stage)
    indexed={(x['uid'],x['method']):x for x in rows}
    methods=(parent,*ARMS)
    table={arm:Counter() for arm in methods}
    strata={}
    availability=Counter()
    common=0
    unflagged={arm:Counter() for arm in methods}
    unflagged_count=0
    details=[]
    directions={arm:Counter() for arm in ARMS}
    for card in cards:
        u=card['uid']
        scores={a:indexed[u,a]['score'] for a in ARMS}
        scores[parent]=unchanged[u]['score']
        scores['BASE']=card['base_score']
        values={m:metrics(card,s) for m,s in scores.items()}
        for arm in methods:
            if values[arm] is not None:
                assert aligned(values,('BASE',arm))
                availability[arm]+=1
        if not aligned(values,methods):
            continue
        common+=1
        flags={a:indexed[u,a].get('score_flags') for a in ARMS}
        flags[parent]=unchanged[u].get('score_flags')
        if domain=='RPEval' and all(flags[arm]==[] for arm in methods):
            unflagged_count+=1
            for arm in methods:
                unflagged[arm].update(values[arm])
        if private and any(values[a]['primary']!=values[parent]['primary'] for a in ARMS):
            details.append(dict(uid=u,stratum=card['stratum'],task=card['payload']['task'],score_flags=flags,
                           metrics=values,answers={parent:unchanged[u]['answer'],
                                   **{a:indexed[u,a]['answer'] for a in ARMS}}))
        group=strata.setdefault(card['stratum'],{arm:Counter() for arm in methods})
        for arm in methods:
            table[arm].update(values[arm])
            group[arm].update(values[arm])
        for arm in ARMS:
            change=values[arm]['primary']-values[parent]['primary']
            directions[arm]['win' if change>0 else 'loss' if change<0 else 'tie']+=1
    if private:
        (run/'private'/f'{domain}_PAIRED_TRACES.json').write_text(json.dumps(details,ensure_ascii=False,indent=2))
    return dict(domain=domain,parent=parent,assigned=len(cards),common=common,
                without_known_flags={'common':unflagged_count,'scores':unflagged},
                available=availability,common_scores=table,strata=strata,paired_directions=directions,
                physical_scoring=len(ledger),statuses=Counter(r['status'] for r in ledger),
                tokens=sum((r.get('usage') or {}).get('total_tokens') or 0 for r in ledger))


if __name__=='__main__':
    cli=ArgumentParser(description=__doc__)
    cli.add_argument('directory',type=Path)
    cli.add_argument('domain',choices=STAGES)
    cli.add_argument('--private',action='store_true')
    args=cli.parse_args()
    print(json.dumps(replay(args.directory,args.domain,args.private),indent=2))
