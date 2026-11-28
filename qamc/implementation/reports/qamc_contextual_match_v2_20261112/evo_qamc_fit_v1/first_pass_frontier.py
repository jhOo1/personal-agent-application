"""Measure the optimistic answer-inventory frontier for whole-Actor fit rounds."""
from collections import Counter, defaultdict
import json

from first_pass_fit import MODES, OUT as ROUND1, metrics, prepare, read
from first_pass_iteration import OUT as ROUND2


def protected(domain, candidate, incumbent):
    if domain == 'RPEval':
        return all(candidate[key] <= incumbent[key] for key in ('OPB','UPB','FM'))
    if domain == 'BenchPreS':
        return (candidate['MR'] <= incumbent['MR']
                and candidate['nonbold'] >= incumbent['nonbold']
                and candidate['completeness'] >= incumbent['completeness'])
    return candidate['strict_pass'] >= incumbent['strict_pass']


def summarize(cards, requests, baselines, rounds):
    data = defaultdict(Counter)
    for c in cards:
        uid, domain, stratum = (c[k] for k in ('uid','domain','stratum'))
        for mode in MODES:
            incumbent = baselines[uid,mode]
            base = metrics(c,incumbent['score'])
            compare = [r for row_map in rounds for (key,method),r in row_map.items()
                       if key == uid and method.startswith(mode+'/')]
            options = [r for r in compare if r.get('answer') and r['answer'] != incumbent['answer']]
            scored = [(metrics(c,r['score']),r.get('score_flags')) for r in options]
            graded = [(val,flag) for val,flag in scored if val is not None]
            if any(val['positions'] != base['positions'] for val,_ in graded):
                raise ValueError('Different author-position denominator')
            base_score_flag = incumbent.get('score_flags')
            stat_keys = [domain,domain+'/'+stratum]
            empty = not json.loads(requests[uid,mode]['messages'][1]['content'])['source_evidence']
            if domain == 'RPEval' and empty and stratum == 'all_A':
                stat_keys.append('RPEval/all_A_zero_visible_history')
            if domain == 'RPEval' and not (empty and stratum == 'all_A'):
                stat_keys.append('RPEval/exclude_all_A_zero_visible_history')
            for stat in stat_keys:
                count = data[mode,stat]
                count['assigned'] += 1
                count['baseline_positions'] += base['positions']
                count['baseline_primary'] += base['primary']
                count['gradable_different_answer'] += bool(graded)
                count['distinct_graded_answers'] += len({r['answer'] for r in options
                                                         if metrics(c,r['score']) is not None})
                gains = [max(0,val['primary']-base['primary']) for val,_ in graded]
                safe = [gain for (val,_),gain in zip(graded,gains) if protected(domain,val,base)]
                clean = [gain for (val,flag),gain in zip(graded,gains)
                         if protected(domain,val,base)
                         and (domain != 'RPEval' or flag == base_score_flag == [])]
                if stat == 'RPEval/all_A_zero_visible_history':
                    count['scope_nonzero_opb'] += base['OPB'] > 0
                    count['round_answers_nonzero_opb'] += sum(val['OPB'] > 0 for val,_ in graded)
                    count['maximum_match_spread'] = max(count['maximum_match_spread'],
                        max([base['primary'],*(val['primary'] for val,_ in graded)]) -
                        min([base['primary'],*(val['primary'] for val,_ in graded)]))
                count['oracle_gain'] += max([0,*gains])
                count['protected_oracle_gain'] += max([0,*safe])
                count['protected_no_known_flags_gain'] += max([0,*clean])
                count['protected_no_known_flags_gain_tasks'] += any(clean)
    return {mode: {stat:dict(val) for (which,stat),val in data.items() if which==mode}
            for mode in MODES}


if __name__ == '__main__':
    _, cards, requests, _, _, baselines = prepare()
    rounds = []
    for area in (ROUND1, ROUND2):
        path = area/'RESULTS.json'
        if not path.exists():
            break
        rounds.append({(r['uid'],r['method']):r for r in read(path)['rows']})
    if not rounds:
        raise ValueError('No settled score inventory')
    print(json.dumps(dict(settled_rounds=len(rounds),frontier=summarize(cards,requests,baselines,rounds)),indent=2))
