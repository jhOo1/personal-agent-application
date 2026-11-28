"""Build private decision feedback from paired, completed rollout receipts."""
from argparse import ArgumentParser
import json

from summarize import metrics
from trial import RUN, sha

DOMAINS = ('RPEval', 'BenchPreS', 'PersistBench')
SUFFIXES = ('', '_self_recheck', '_task_only')


def read(path):
    return json.loads(path.read_text())


def outcome_index():
    outputs = {}
    for suffix in SUFFIXES:
        directory = RUN.with_name(RUN.name + suffix)
        file = directory/'RESULTS.json'
        if not file.exists():
            continue
        for row in read(file)['rows']:
            key = row['uid'], row['method']
            assert key not in outputs
            outputs[key] = row
    return outputs


def pair_feedback(parent, opponent, index, cards):
    rows = []
    for card in cards:
        uid = card['uid']
        left, right = (index.get((uid, method)) for method in (parent, opponent))
        if left is None or right is None:
            continue
        a, b = (metrics(card, row['score']) for row in (left, right))
        if a is None or b is None:
            continue
        keys = {'RPEval': ('primary','OPB','UPB','FM'),
                'BenchPreS': ('primary','MR','completeness','nonbold'),
                'PersistBench': ('primary','strict_pass')}[card['domain']]
        assert a['positions'] == b['positions']
        delta = {key: a[key]-b[key] for key in keys}
        if not any(delta.values()) or left['answer'] == right['answer']:
            continue
        rows.append(dict(domain=card['domain'], stratum=card['stratum'], group=card['group'],
                         uid=uid, delta=delta,
                         known_score_flags={parent:left.get('score_flags'),opponent:right.get('score_flags')},
                         task=card['payload']['task'], history=card['payload']['source_evidence'],
                         parent_answer=left['answer'], comparison_answer=right['answer']))
    return rows


def select(rows, maximum):
    chosen = []
    for domain in DOMAINS:
        pool = [row for row in rows if row['domain'] == domain]
        used = set()
        for goal in ('repair', 'protect', 'other'):
            if len(used) >= maximum:
                break
            if goal == 'repair':
                eligible = [row for row in pool if row['delta']['primary'] < 0]
            elif goal == 'protect':
                eligible = [row for row in pool if row['delta']['primary'] > 0]
            else:
                eligible = pool
            eligible = [row for row in eligible if row['group'] not in used]
            if eligible:
                winner = min(eligible,key=lambda row:(-abs(row['delta']['primary']),sha(row['uid'])))
                chosen.append({**winner,'purpose':goal})
                used.add(winner['group'])
    return chosen


if __name__ == '__main__':
    cli = ArgumentParser(description=__doc__)
    cli.add_argument('parent')
    cli.add_argument('opponent')
    args = cli.parse_args()
    assert args.parent != args.opponent
    panel = read(RUN/'private/FROZEN.json')
    cases = pair_feedback(args.parent,args.opponent,outcome_index(),panel['rows'])
    path = RUN/'private'/('REFLECTION_'+sha([args.parent,args.opponent])[:16]+'.json')
    output = dict(parent=args.parent, opponent=args.opponent,
                  total_disagreements=len(cases), development_only=True, examples=select(cases,3))
    if not output['examples']:
        raise SystemExit('No completed scored contrasts available')
    path.write_text(json.dumps(output,ensure_ascii=False,indent=2))
    print('Private feedback cases:',len(output['examples']),'of',len(cases))
