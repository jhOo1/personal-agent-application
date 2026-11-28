"""Export real paired outcome evidence for the next offline search iteration."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path

from feedback import pair_feedback, select as choose_examples
from select_parents import select as choose_parents
from summarize import metrics
from trial import RUN, sha

ARTIFACTS = (
    ('','RESULTS.json'),('_self_recheck','RESULTS.json'),('_task_only','RESULTS.json'),
    ('_crossover','RESULTS.json'),('_selected_planning','COMBINED.json'),
)
METRICS_BY_DOMAIN = {
    'RPEval': ('RPEval','rpe_less_opb','rpe_less_upb','rpe_less_fm'),
    'BenchPreS': ('BenchPreS','bench_appropriate','bench_less_misuse','bench_completeness'),
    'PersistBench': ('PersistBench','persist_utility','persist_less_cross_domain','persist_less_sycophancy'),
}


def read(path):
    return json.loads(path.read_text())


def shared_persist_failures(left, right, rows, cards):
    examples = []
    for card in cards:
        if card['stratum']!='sycophancy':
            continue
        a, b = (rows.get((card['uid'],method)) for method in (left,right))
        if not a or not b:
            continue
        v, w = (metrics(card,r['score']) for r in (a,b))
        if not v or not w or v['primary']!=0 or w['primary']!=0:
            continue
        examples.append(dict(domain=card['domain'],stratum=card['stratum'],uid=card['uid'],
                             group=card['group'],purpose='shared_failed_outcome',
                             task=card['payload']['task'],history=card['payload']['source_evidence'],
                             parent_answer=a['answer'],comparison_answer=b['answer'],
                             parent_rating=a['score']['rating'],comparison_rating=b['score']['rating']))
    retval=[]
    groups=set()
    for row in sorted(examples,key=lambda r:sha(r['uid'])):
        if row['group'] not in groups:
            retval.append(row)
            groups.add(row['group'])
    return retval[:2]


def evidence(summary):
    parents=choose_parents(summary)
    leader=parents['best_balanced_parent']
    ranked=list(parents['frontier'])
    allowed=set(ranked)
    rows={}
    for suffix,filename in ARTIFACTS:
        path=RUN.with_name(RUN.name+suffix)/filename
        if not path.exists():
            continue
        for row in read(path)['rows']:
            if row['method'] not in allowed:
                continue
            key=row['uid'],row['method']
            assert key not in rows
            rows[key]=row
    if set(r['method'] for r in rows.values())!=allowed:
        raise ValueError('The summary lacks matching settled policy receipts')
    cards=read(RUN/'private/FROZEN.json')['rows']
    proposals={}
    for domain,dims in METRICS_BY_DOMAIN.items():
        alternatives=[parents['best_by_objective'][measure] for measure in dims]
        rivals=list(dict.fromkeys(a for a in alternatives if a!=leader))
        if not rivals and len(ranked)>1:
            rivals=[ranked[1]]
        domain_cards=[c for c in cards if c['domain']==domain]
        for rival in rivals:
            pair=pair_feedback(leader,rival,rows,domain_cards)
            examples=choose_examples(pair,3)
            if not examples and domain=='PersistBench':
                examples=shared_persist_failures(leader,rival,rows,domain_cards)
            if examples:
                proposals[domain+'/'+rival]=examples
    identities = {f'{uid}/{method}':sha(row['answer'])
                  for (uid,method),row in sorted(rows.items()) if row.get('answer')}
    return dict(development_only=True, balanced_parent=leader, frontier=ranked,
                scored_common=parents['common'],examples=proposals,
                settled_actor_answers_sha256=sha(identities))


if __name__=='__main__':
    cli=ArgumentParser(description=__doc__)
    cli.add_argument('summary',type=Path)
    args=cli.parse_args()
    result=evidence(read(args.summary))
    path=RUN/'private'/f'SEARCH_FEEDBACK_{sha(args.summary.read_bytes())[:16]}.json'
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    totals=Counter()
    for key,examples in result['examples'].items():
        totals[key.split('/')[0]]+=len(examples)
    print(json.dumps({k:v for k,v in result.items() if k!='examples'} | {'example_counts':totals},indent=2))
