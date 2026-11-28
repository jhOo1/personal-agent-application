"""Measure fit conclusions after removing each observed source group from a paired contrast."""
from argparse import ArgumentParser
from collections import Counter,defaultdict
import json
from pathlib import Path

from evolution_feedback import ARTIFACTS, read
from paired_macro import DOMAINS, interval
from summarize import metrics
from summarize_reassembly import aligned
from trial import RUN


def outcome_index(extra):
    paths=[RUN.with_name(RUN.name+suffix)/file for suffix,file in ARTIFACTS]
    known={}
    for path in [*paths,*extra]:
        if path.exists():
            for row in read(path)['rows']:
                key=row['uid'],row['method']
                if key in known:
                    raise ValueError(f'Duplicate scored policy name {key[1]}')
                known[key]=row
    return known


def prepare(left,right,extra):
    cards=read(RUN/'private/FROZEN.json')['rows']
    scored=outcome_index(extra)
    paired=defaultdict(list)
    available=defaultdict(Counter)
    assigned=Counter()
    for card in cards:
        uid=card['uid']
        domain=card['domain']
        assigned[domain]+=1
        values={'BASE':metrics(card,card['base_score'])}
        for arm in (left,right):
            row=scored.get((uid,arm))
            values[arm]=metrics(card,row['score']) if row else None
            available[domain][arm]+=values[arm] is not None
        if aligned(values,('BASE',left,right)):
            paired[domain].append((card,None,values))
    return paired,assigned,available


def change(domain, rows, a,b):
    result=interval(domain,rows,a,b)
    return result[0] if result is not None else None


def evaluate(left,right,extra):
    paired,assigned,available=prepare(left,right,extra)
    original={d:change(d,paired[d],left,right) for d in DOMAINS}
    if None in original.values():
        raise ValueError('A domain has no complete support for a common macro score')
    by_domain={}
    overall=[]
    for domain,rows in sorted(paired.items()):
        changes=[]
        groups={card['group'] for card,_,_ in rows}
        for group in sorted(groups):
            remaining=[r for r in rows if r[0]['group']!=group]
            score=change(domain,remaining,left,right)
            if score is not None:
                changes.append(score)
                overall.append((sum(original.values())-original[domain]+score)/3)
        by_domain[domain]=dict(assigned=assigned[domain],available=available[domain],common=len(rows),
                              groups=len(groups),original_gain=original[domain],defined_removals=len(changes),
                              positive=sum(v>1e-12 for v in changes),negative=sum(v<(-1e-12) for v in changes),
                              range=[min(changes),max(changes)] if changes else None)
    return dict(left=left,right=right,domains=by_domain,common_macro_gain=sum(original.values())/3,
                removed_group_macro_count=len(overall),positive=sum(v>1e-12 for v in overall),
                negative=sum(v<(-1e-12) for v in overall),
                removed_group_macro_range=[min(overall),max(overall)] if overall else None)


if __name__=='__main__':
    cli=ArgumentParser(description=__doc__)
    cli.add_argument('left')
    cli.add_argument('right')
    cli.add_argument('--extra',type=Path,action='append',default=[])
    args=cli.parse_args()
    print(json.dumps(evaluate(args.left,args.right,args.extra),indent=2))
