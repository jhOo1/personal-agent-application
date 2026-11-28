"""Compute equal-domain Actor fit objectives and direct paired comparisons."""
import json
from collections import Counter

from first_pass_fit import OUT, METHODS, MODES, metrics, prepare, read, summarize

DOMAINS = ('RPEval','BenchPreS','PersistBench')
PB = tuple('PersistBench/'+tag for tag in (
    'sycophancy','cross_domain','beneficial_memory_usage'))


def components(data, name):
    rpe = data['RPEval']['metrics'][name]
    bench = data['BenchPreS']['metrics'][name]
    pb = [data[tag]['metrics'][name] for tag in PB]
    if (not rpe or not bench or not all(pb)
            or not bench['positions'] or not bench['MR_denominator']):
        return None
    return {
        'RPEval': rpe['primary']/rpe['positions'],
        'BenchPreS': (bench['primary']/bench['positions'] + 1 -
                     bench['MR']/bench['MR_denominator'] +
                     (bench['completeness']/data['BenchPreS']['common'] - 1)/4) / 3,
        'PersistBench': sum(x['primary']/x['positions'] for x in pb)/3,
    }


def paired(cards, rows, archive):
    indexed = {(r['uid'],r['method']):r for r in rows}
    result = {}
    for route in MODES:
        result[route] = {}
        for arm in METHODS:
            domains = {}
            for card in cards:
                uid, domain = card['uid'], card['domain']
                old = archive[uid,route]
                new = indexed[uid,route+'/'+arm]
                cell = domains.setdefault(domain, dict(assigned=0, common=0, clean=0,
                    parent=Counter(), candidate=Counter(), clean_parent=Counter(),
                    clean_candidate=Counter(), direction=Counter(), minimum=0, maximum=0))
                cell['assigned'] += 1
                a,b = (metrics(card,row['score']) for row in (old,new))
                count = metrics(card,card['base_score'])['positions']
                cell['minimum'] += (b['primary'] if b is not None else 0) - (
                                    a['primary'] if a is not None else count)
                cell['maximum'] += (b['primary'] if b is not None else count) - (
                                    a['primary'] if a is not None else 0)
                if a is None or b is None:
                    continue
                if a['positions'] != b['positions']:
                    raise ValueError('Paired denominator mismatch')
                cell['common'] += 1
                cell['parent'].update(a)
                cell['candidate'].update(b)
                delta = b['primary'] - a['primary']
                cell['direction']['win' if delta>0 else 'loss' if delta<0 else 'tie'] += 1
                if domain == 'RPEval' and old.get('score_flags') == [] and new.get('score_flags') == []:
                    cell['clean'] += 1
                    cell['clean_parent'].update(a)
                    cell['clean_candidate'].update(b)
            result[route][arm] = domains
    return result


def score(cards, result, archive):
    data = summarize(cards,result['rows'],archive,result['ledger'])
    data['pairwise_scope'] = paired(cards,result['rows'],archive)
    data['common_macro'] = {}
    for route, rows in data['rollups'].items():
        energies = {arm:components(rows,arm) for arm in ('BASE','SCOPE',*METHODS)}
        data['common_macro'][route] = {'domain_utilities':energies,
            'overall':{arm:sum(vals.values())/len(DOMAINS) for arm,vals in energies.items() if vals}}
    return data


if __name__ == '__main__':
    _, cards, _, _, _, archive = prepare()
    print(json.dumps(score(cards,read(OUT/'RESULTS.json'),archive),indent=2))
