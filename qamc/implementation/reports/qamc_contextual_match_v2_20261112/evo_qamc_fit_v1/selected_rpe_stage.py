"""Replay the selected-planning RPEval grades and calculate its four matched cells."""
from collections import Counter
import json

from qamc_rpeval_terminal_judge_sensitivity import inspect
from factorial import CELLS, collect, effects
from selected_planning import OUT
from summarize_reassembly import aligned
from trial import CAP, HERE, POLICIES, RUN, archive, engine, probe, sha


def read(path):
    return json.loads(path.read_text())


def main():
    manifest_file=OUT/f'{engine.RPE}_MANIFEST.json'
    if not manifest_file.exists():
        raise SystemExit('The selected RPEval scoring manifest is not available')
    statuses=[read(f)['status'] for f in (OUT/engine.RPE/'visible').glob('*/record.json')]
    if len(statuses)!=len(read(manifest_file)['units']) or 'PENDING_DELIVERY_UNKNOWN' in statuses:
        raise SystemExit('The selected RPEval scoring stage is still live')
    selected=read(OUT/'private/FROZEN.json')
    cards=[r for r in read(RUN/'private/FROZEN.json')['rows'] if r['domain']=='RPEval']
    new_cards={r['uid']:r for r in selected['rows'] if r['domain']=='RPEval'}
    seeds=[r for r in read(RUN/'RESULTS.json')['rows'] if r['benchmark']=='RPEval']
    frozen_archive={r['uid']:r for r in read(archive.v41.OUT/'FROZEN.json')['roots']}
    labels={r['uid']:r['labels'] for r in read(HERE.parent/'ipe_c_two_endpoint_completion_v1/RESULTS.json')['rows']}
    actors={}
    for p in (OUT/'Actor/visible').glob('*/record.json'):
        receipt=read(p)
        key=receipt['unit']['root_id'],receipt['unit']['method']
        if key[0] in new_cards and receipt['status']=='OK':
            actors[key]=read(p.with_name('response.json'))['answer']
    ordered=sorted(((u,a) for u in new_cards for a in POLICIES),
                   key=lambda key:sha(['fit_seed_order',*key]))
    targets={(u,a):dict(uid=u,method=a,actor_status='OK' if (u,a) in actors else 'ABSENT',
                        answer=actors.get((u,a)),score=None) for u,a in ordered}
    roots={u:dict(original_sources=row['evaluation_sources'],archived=frozen_archive.get(u,{}).get('archived',{}))
           for u,row in new_cards.items()}
    pin_identity=dict(experiment_sha256=sha(selected),service_reference_sha256=selected['service_reference_sha256'])
    probe.RUN,probe.OUT,engine.OUT,engine.CAP=OUT,OUT,OUT,CAP
    ledger=[]

    def execute(name,jobs,cache=None):
        return engine.stage(name,jobs,pin_identity,False,ledger,cache) if jobs else {}

    engine.grade_rpe(roots,list(targets.values()),execute)
    for card in selected['exact']:
        if card['domain']=='RPEval':
            for row in seeds:
                if row['uid']==card['uid']:
                    targets[row['uid'],row['method']]=row.copy()
    for card in selected['absent']:
        if card['domain']=='RPEval':
            for name in POLICIES:
                targets[card['uid'],name]=dict(uid=card['uid'],method=name,score=None)
    new=[]
    for (uid,name),row in targets.items():
        if uid in new_cards and row['score'] and row['score'].get('match'):
            row['score_flags']=inspect({**row,'native_fields':row['score'],
                             'raw_scores':{archive.v41.NATIVE:row['judge']['answer']}},labels[uid])['flags']
        new.append({**row,'method':'SELECTED_'+name})
    score_flags={(r['uid'],r['method']):r.get('score_flags') for r in [*seeds,*new]}
    groups=collect(cards,[*seeds,*new])['RPEval']
    native={key:{a:Counter() for a in ('BASE',*CELLS)}
            for key in ('all','all_A','B_only','contains_C','unflagged')}
    counts=Counter()
    paired=[r for r in groups if aligned(r[2],('BASE',*CELLS))]
    for card,_,values in paired:
        buckets=('all',card['stratum'])
        if card['base_flags']==[] and all(score_flags[card['uid'],arm]==[] for arm in CELLS):
            buckets+=('unflagged',)
        for name in buckets:
            counts[name]+=1
            for method,v in values.items():
                native[name][method].update(v)
    print(json.dumps(dict(assigned=len(cards),common=counts,paired=native,
        common_effects=effects('RPEval',paired),assigned_effect_bounds=effects('RPEval',groups),
        native_score_coverage={a:sum(v[a] is not None for _,_,v in groups) for a in CELLS},
        physical_scoring=len(ledger),transport=Counter(r['status'] for r in ledger),
        reported_tokens=sum((r.get('usage') or {}).get('total_tokens') or 0 for r in ledger)),indent=2))


if __name__=='__main__':
    main()
