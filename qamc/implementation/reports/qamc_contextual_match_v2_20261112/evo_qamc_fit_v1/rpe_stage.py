"""Replay the complete RPEval scoring stage before the other benchmark calls finish."""
from argparse import ArgumentParser
from collections import Counter
import json

from qamc_rpeval_terminal_judge_sensitivity import inspect
from summarize import metrics
from summarize_reassembly import aligned
from trial import CAP, POLICIES, HERE, RUN, archive, engine, probe, sha
from baselines import rpe

METHODS = ('BASE',*POLICIES)


def read(path):
    return json.loads(path.read_text())


def ready():
    manifest = RUN/f'{engine.RPE}_MANIFEST.json'
    if not manifest.exists():
        return False
    units = read(manifest)['units']
    receipts = [read(p) for p in (RUN/engine.RPE/'visible').glob('*/record.json')]
    return (len(receipts)==len(units) and
            all(r['status']!='PENDING_DELIVERY_UNKNOWN' for r in receipts))


def replay(include_private=False):
    plan = read(RUN/'private/FROZEN.json')
    cards = {c['uid']:c for c in plan['rows'] if c['domain']=='RPEval'}
    actors = {}
    for path in (RUN/'Actor/visible').glob('*/record.json'):
        receipt = read(path)
        uid, arm = (receipt['unit'][k] for k in ('root_id','method'))
        if uid not in cards or receipt['status']!='OK':
            continue
        answer = read(path.with_name('response.json'))['answer']
        actors[uid,arm] = answer
    pairs = [(uid,arm) for uid in cards for arm in POLICIES]
    pairs.sort(key=lambda pair:sha(['fit_seed_order',*pair]))
    outputs = dict((key,dict(uid=key[0],method=key[1],actor_status='OK' if key in actors else 'ABSENT',
                             answer=actors.get(key),score=None)) for key in pairs)
    source = read(archive.v41.OUT/'FROZEN.json')
    old = {r['uid']:r.get('archived',{}) for r in source['roots']}
    roots = {uid:{'original_sources':card['payload']['source_evidence'],'archived':old.get(uid,{})}
             for uid,card in cards.items()}
    plan_identity = {'experiment_sha256':sha(plan),'service_reference_sha256':plan['service_reference_sha256']}
    probe.RUN,probe.OUT,engine.OUT,engine.CAP = RUN,RUN,RUN,CAP
    ledger=[]
    def stage(name,jobs,cache=None):
        return engine.stage(name,jobs,plan_identity,False,ledger,cache)
    engine.grade_rpe(roots,list(outputs.values()),stage)

    labels = {r['uid']:r['labels'] for r in read(HERE.parent/'ipe_c_two_endpoint_completion_v1'/'RESULTS.json')['rows']}
    flags = {}
    for key,row in outputs.items():
        if row['score'] and row['score'].get('match'):
            flags[key] = inspect({**row,'native_fields':row['score'],
                      'raw_scores':{archive.v41.NATIVE:row['judge']['answer']}},labels[row['uid']])['flags']
    coverage = Counter()
    scores = {k:{a:Counter() for a in METHODS} for k in ('all','all_A','B_only','contains_C','without_known_flags')}
    count = Counter()
    direction = {k:{a:Counter() for a in POLICIES} for k in scores}
    private = []
    baselines = rpe() if include_private else {}
    for uid,card in cards.items():
        buckets = ('all',card['stratum'])
        values = {'BASE':metrics(card,card['base_score'])}
        for arm in POLICIES:
            values[arm] = metrics(card,outputs[uid,arm]['score'])
            coverage[arm] += values[arm] is not None
        if not aligned(values,METHODS):
            continue
        if include_private and any(values[a]['primary']!=values['BASE']['primary'] for a in POLICIES):
            summary = dict(uid=uid,group=card['group'],stratum=card['stratum'],task=card['payload']['task'],
                           histories=card['payload']['source_evidence'],baseline=baselines[uid]['base_answer'],
                           answers={a:actors[uid,a] for a in POLICIES},metrics=values,
                           score_flags={'BASE':card['base_flags'],**{a:flags.get((uid,a)) for a in POLICIES}},
                           judge_reason={a:outputs[uid,a]['score'].get('Judge') for a in POLICIES})
            private.append(summary)
        if card['base_flags']==[] and all(flags.get((uid,a))==[] for a in POLICIES):
            buckets += ('without_known_flags',)
        for bucket in buckets:
            count[bucket] += 1
            for arm in METHODS:
                scores[bucket][arm].update(values[arm])
            for arm in POLICIES:
                delta = values[arm]['primary'] - values['BASE']['primary']
                direction[bucket][arm]['wins' if delta>0 else 'losses' if delta<0 else 'ties'] += 1
    if include_private:
        path = RUN/'private/RPE_SCORE_CONTRASTS.json'
        path.write_text(json.dumps(private,ensure_ascii=False,indent=2))
    return dict(assigned=len(cards),native_scores=scores,common=count,valid_by_arm=coverage,paired_vs_ipe_c=direction,
                physical_score_requests=len(ledger),status=Counter(x['status'] for x in ledger),
                reported_tokens=sum((x.get('usage') or {}).get('total_tokens') or 0 for x in ledger),
                usage_unknown=sum((x.get('usage') or {}).get('total_tokens') is None for x in ledger))


if __name__=='__main__':
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--private',action='store_true')
    args = parser.parse_args()
    if not ready():
        raise SystemExit('RPEval score stage is not terminal yet')
    print(json.dumps(replay(args.private),indent=2))
