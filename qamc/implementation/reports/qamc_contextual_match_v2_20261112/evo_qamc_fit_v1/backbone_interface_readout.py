"""Summarize predeclared crossover contrasts without issuing requests."""
from collections import Counter, defaultdict
import json

from backbone_interface import OUT, ARMS, MODELS, INTERFACES, metrics, prepare, read, summarize

TRACKS = ('cross_domain','sycophancy','beneficial_memory_usage')


def pairs():
    contrasts = {}
    for interface in INTERFACES:
        for source in ('SELECTED','OFF'):
            contrasts[f'D-minus-Q/{interface}/{source}'] = (
                f'Q/{interface}/{source}',f'D/{interface}/{source}')
    for model in MODELS:
        for source in ('SELECTED','OFF'):
            contrasts[f'DIRECT-minus-PLAN/{model}/{source}'] = (
                f'{model}/PLAN/{source}',f'{model}/DIRECT/{source}')
        for interface in INTERFACES:
            contrasts[f'SELECTED-minus-OFF/{model}/{interface}'] = (
                f'{model}/{interface}/OFF',f'{model}/{interface}/SELECTED')
    return contrasts


def three_domain_utility(sections, arm):
    rpe = sections['RPEval']['aggregates'].get(arm,{})
    bench = sections['BenchPreS']['aggregates'].get(arm,{})
    persist = [sections['PersistBench/'+track]['aggregates'].get(arm,{}) for track in TRACKS]
    if not (rpe.get('positions') and bench.get('positions') and bench.get('MR_denominator')
            and all(track.get('positions') for track in persist)):
        return None
    return dict(RPEval=rpe['primary']/rpe['positions'],
                BenchPreS=(bench['primary']/bench['positions']+
                           1-bench['MR']/bench['MR_denominator']+
                           (bench['completeness']/sections['BenchPreS']['common']-1)/4)/3,
                PersistBench=sum(t['primary']/t['positions'] for t in persist)/3)


def readout(roster, rows, ledger):
    prior = summarize(roster,rows,ledger)
    table = {(r['uid'],r['method']):r for r in rows}
    outcomes = defaultdict(lambda:dict(assigned=0,matched=0,unflagged=0,
                wins=0,losses=0,ties=0, old=Counter(), new=Counter(),
                clean_old=Counter(), clean_new=Counter(), lower_bound=0, upper_bound=0))
    exposure_interaction = defaultdict(lambda:dict(matched=0,unflagged=0,
                                            positions=0,model_history_difference=Counter()))
    for item in roster:
        card = item['card']
        domain,stratum,uid = (card[k] for k in ('domain','stratum','uid'))
        refs = {arm:table[uid,arm] for arm in ARMS}
        values = {arm:metrics(card,row['score']) for arm,row in refs.items()}
        size = metrics(card,card['base_score'])['positions']
        keys = [domain,domain+'/'+stratum]
        if item['source_role'] == 'empty':
            keys.append(domain+'/zero_selected_history')
        else:
            keys.append(domain+'/nonzero_selected_history')
        for name,(before,after) in pairs().items():
            left,right = values[before],values[after]
            for group in keys:
                c = outcomes[name,group]
                c['assigned'] += 1
                c['lower_bound'] += (right['primary'] if right is not None else 0) - (
                                  left['primary'] if left is not None else size)
                c['upper_bound'] += (right['primary'] if right is not None else size) - (
                                  left['primary'] if left is not None else 0)
                if left is None or right is None:
                    continue
                if left['positions'] != right['positions'] or left.get('MR_denominator') != right.get('MR_denominator'):
                    raise ValueError('Native paired position mismatch')
                c['matched'] += 1
                c['old'].update(left)
                c['new'].update(right)
                delta = right['primary']-left['primary']
                c['wins' if delta>0 else 'losses' if delta<0 else 'ties'] += 1
                if domain == 'RPEval' and refs[before].get('score_flags') == refs[after].get('score_flags') == []:
                    c['unflagged'] += 1
                    c['clean_old'].update(left)
                    c['clean_new'].update(right)
        if item['source_role'] == 'empty':
            continue
        for interface in INTERFACES:
            arms = [f'{model}/{interface}/{exposure}' for model in MODELS
                    for exposure in ('SELECTED','OFF')]
            q_s,q_o,d_s,d_o = [values[arm] for arm in arms]
            if any(val is None for val in (q_s,q_o,d_s,d_o)):
                continue
            if len({(v['positions'],v.get('MR_denominator')) for v in (q_s,q_o,d_s,d_o)}) != 1:
                raise ValueError('Exposure interaction denominators differ')
            for group in keys:
                c = exposure_interaction[interface,group]
                c['matched'] += 1
                c['positions'] += size
                for measure in ('primary','OPB','UPB','FM','MR','completeness','nonbold','strict_pass'):
                    if measure not in q_s:
                        continue
                    c['model_history_difference'][measure] += (
                        d_s[measure]-d_o[measure]-q_s[measure]+q_o[measure])
                if domain == 'RPEval' and all(refs[a].get('score_flags') == [] for a in arms):
                    c['unflagged'] += 1
    parts = {arm:three_domain_utility(prior['sections'],arm) for arm in ('BASE',*ARMS)}
    average = {arm:sum(v.values())/3 for arm,v in parts.items() if v}
    return {**prior,
            'common_utility':{'parts':parts,'overall':average},
            'pairwise':{name:{group:v for (n,group),v in outcomes.items() if n==name} for name in pairs()},
            'history_model_score_difference':{
                x:{group:v for (n,group),v in exposure_interaction.items() if n==x} for x in INTERFACES}}


if __name__ == '__main__':
    _,roster,_,_,_,_ = prepare()
    result = read(OUT/'RESULTS.json')
    print(json.dumps(readout(roster,result['rows'],result['ledger']),indent=2))
