"""Summarize predeclared crossover contrasts without issuing requests."""
from collections import Counter, defaultdict
import json

from backbone_interface import OUT, ARMS, MODELS, INTERFACES, metrics, prepare, read, summarize

TRACKS = ('cross_domain','sycophancy','beneficial_memory_usage')


def pairs():
    contrasts = {f"versus-archived-specialist/{arm}": ("BASE", arm) for arm in ARMS}
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


def interaction_bounds(values, positions):
    """Bound (D selected - D off) - (Q selected - Q off) on one root."""
    positive = (values[2], values[1])
    negative = (values[3], values[0])
    low = sum(v["primary"] if v is not None else 0 for v in positive) - sum(
        v["primary"] if v is not None else positions for v in negative)
    high = sum(v["primary"] if v is not None else positions for v in positive) - sum(
        v["primary"] if v is not None else 0 for v in negative)
    return low, high


def readout(roster, rows, ledger):
    prior = summarize(roster,rows,ledger)
    table = {(r['uid'],r['method']):r for r in rows}
    outcomes = defaultdict(lambda:dict(assigned=0,matched=0,unflagged=0,
                wins=0,losses=0,ties=0, old=Counter(), new=Counter(),
                clean_old=Counter(), clean_new=Counter(), lower_bound=0, upper_bound=0))
    exposure_interaction = defaultdict(lambda:dict(
        assigned=0, assigned_positions=0, matched=0, unflagged=0, positions=0,
        primary_lower_bound=0, primary_upper_bound=0,
        model_history_difference=Counter(), unflagged_history_difference=Counter()))
    for item in roster:
        card = item['card']
        domain,stratum,uid = (card[k] for k in ('domain','stratum','uid'))
        refs = {arm:table[uid,arm] for arm in ARMS}
        refs["BASE"] = {"score": card["base_score"], "score_flags": card["base_flags"]}
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
            measures = ('primary','OPB','UPB','FM','MR','completeness','nonbold','strict_pass')
            four = [values[arm] for arm in arms]
            low, high = interaction_bounds(four, size)
            matched = all(v is not None for v in four)
            clean = matched and domain == 'RPEval' and all(refs[a].get('score_flags') == [] for a in arms)
            if matched and len({(v["positions"], v.get("MR_denominator")) for v in four}) != 1:
                raise ValueError('Exposure interaction denominators differ')
            delta = {}
            if matched:
                q_s,q_o,d_s,d_o = four
                delta = {key: d_s[key]-d_o[key]-q_s[key]+q_o[key] for key in measures if key in q_s}
            for group in keys:
                c = exposure_interaction[interface,group]
                c['assigned'] += 1
                c['assigned_positions'] += size
                c['primary_lower_bound'] += low
                c['primary_upper_bound'] += high
                if matched:
                    c['matched'] += 1
                    c['positions'] += size
                    c['model_history_difference'].update(delta)
                if clean:
                    c['unflagged'] += 1
                    c['unflagged_history_difference'].update(delta)
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
