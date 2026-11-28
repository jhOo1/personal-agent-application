"""Report settled expansion batches on their common and fully assigned denominators."""
from collections import Counter,defaultdict
import json

from summarize import metrics
from summarize_reassembly import aligned
from paired_macro import pairwise
from rpe_use_bounds import paired_degree_bounds
from trial import HERE,sha
from expansion_run import ARMS,OUT,read

METHODS=('BASE',*ARMS)


def collect():
    pin=read(OUT/'private/FROZEN.json')
    groups=defaultdict(list)
    finished=[]
    ledger=[]
    delivery=defaultdict(Counter)
    for index,batch in enumerate(pin['batches'],1):
        path=OUT/f'batch_{index}'/'RESULTS.json'
        if not path.exists():
            continue
        result=read(path)
        finished.append(index)
        ledger.extend(result['ledger'])
        outcomes={(r['uid'],r['method']):r for r in result['rows']}
        assert len(outcomes)==len(result['rows'])==len(batch)*len(ARMS)
        for c in batch:
            uid=c['uid']
            moved={a:outcomes[uid,a] for a in ARMS}
            grades={'BASE':c['base_score'],**{a:r['score'] for a,r in moved.items()}}
            values={a:metrics(c,s) for a,s in grades.items()}
            assert values['BASE']
            for a,row in moved.items():
                delivery[a][row['actor_status']]+=1
                delivery[a]['grade_available']+=values[a] is not None
                if row['actor_status']=='OK' and values[a] is None:
                    delivery[a]['successful_actor_without_usable_grade']+=1
                if values[a] is not None:
                    assert aligned(values,('BASE',a))
            if c['domain']=='RPEval':
                for a,score in grades.items():
                    if values[a] and score.get('full_match') is not None:
                        values[a]['full_match']=int(score['full_match'])
            for key in (c['domain'],f"{c['domain']}/{c['stratum']}"):
                groups[key].append((c,moved,values))
    return pin,finished,groups,ledger,delivery


def native_totals(rows, methods):
    scores = {method: Counter() for method in methods}
    for _, _, values in rows:
        for method in methods:
            scores[method].update(values[method])
    return dict(common=len(rows), metrics=scores)


def rpe_sensitivity(groups):
    """Reuse the recorded judge flags without changing the primary results."""
    results = {}
    for opponent in ('BASE', 'PLAN_SELECTED', 'DIRECT'):
        methods = ('SCOPE', opponent)
        for name, rows in groups.items():
            if not (name == 'RPEval' or name.startswith('RPEval/')):
                continue
            common = [row for row in rows if aligned(row[2], ('BASE', *methods))]
            unflagged = []
            for card, receipts, values in common:
                flags = [card['base_flags'] if method == 'BASE'
                         else receipts[method].get('score_flags') for method in methods]
                if all(flag == [] for flag in flags):
                    unflagged.append((card, receipts, values))
            results.setdefault(opponent, {})[name] = dict(
                primary=native_totals(common, methods),
                without_known_flags=native_totals(unflagged, methods),
                excluded_from_sensitivity=len(common)-len(unflagged))
    return results


def rpe_degree_bounds(rows):
    endpoint=HERE.parent/'ipe_c_two_endpoint_completion_v1'/'RESULTS.json'
    labels={r['uid']:r['labels'] for r in read(endpoint)['rows']}
    out={}
    for opponent in ('BASE','PLAN_SELECTED','DIRECT'):
        paired=[row for row in rows if aligned(row[2], ('BASE','SCOPE',opponent))]
        out[opponent]={label:paired_degree_bounds(paired,'SCOPE',opponent,label,labels)
                       for label in ('B','C')}
    return out


def rpe_group_support(entries):
    by_rpe=defaultdict(list)
    for c,_,values in entries:
        by_rpe[c['group']].append(values)
    group_support={}
    group_order=sorted(by_rpe,key=lambda g:sha(['public_source_group_order',g]))
    for opponent in ('BASE','PLAN_SELECTED','DIRECT'):
        rows=[]
        for i,group in enumerate(group_order,1):
            cells=[v for v in by_rpe[group] if aligned(v,('BASE',opponent,'SCOPE'))]
            pos=sum(v['BASE']['positions'] for v in cells)
            delta=sum(v['SCOPE']['primary']-v[opponent]['primary'] for v in cells)
            rows.append(dict(group=i,assigned=len(by_rpe[group]),common=len(cells),positions=pos,net_match=delta))
        scored=[r for r in rows if r['positions']]
        total_pos=sum(r['positions'] for r in scored)
        net_match=sum(r['net_match'] for r in scored)
        omitted=[(net_match-r['net_match'])/(total_pos-r['positions'])
                 for r in scored if total_pos>r['positions']]
        group_support[opponent]=dict(groups=rows,group_equal_delta=(
            sum(r['net_match']/r['positions'] for r in scored)/len(scored) if scored else None),
            omit_one_group_delta=[min(omitted),max(omitted)] if omitted else None,
            wins=sum(r['net_match']>0 for r in scored),losses=sum(r['net_match']<0 for r in scored),
            ties=sum(r['net_match']==0 for r in scored))
    return group_support


def summarize():
    pin,finished,groups,ledger,delivery=collect()
    if not finished:
        raise SystemExit('No batch result has settled')
    native={}
    scope_pairs={}
    for key,rows in groups.items():
        common=[row for row in rows if aligned(row[2],METHODS)]
        native[key]=dict(assigned=len(rows),**native_totals(common,METHODS))
        pairs={}
        for opponent in ('BASE','PLAN_SELECTED','DIRECT'):
            methods=('SCOPE',opponent)
            paired=[row for row in rows if aligned(row[2],('BASE',*methods))]
            pairs[opponent]=native_totals(paired,methods)
        scope_pairs[key]=pairs
    frozen_assignment=Counter(card['domain'] for batch in pin['batches'] for card in batch)
    return dict(finished_batches=finished,all_batches_assigned=sum(len(b) for b in pin['batches']),
                frozen_assignment=frozen_assignment,native=native,scope_native_pairs=scope_pairs,
                paired_comparisons=pairwise(groups,METHODS,aligned),rpe_groups=rpe_group_support(groups['RPEval']),
                rpe_judge_sensitivity=rpe_sensitivity(groups),
                rpe_use_degree_bounds=rpe_degree_bounds(groups['RPEval']),
                delivery=delivery,cost=dict(requests=len(ledger),stages=Counter(r['unit']['stage'] for r in ledger),
                    statuses=Counter(r['status'] for r in ledger),
                    tokens=sum((r.get('usage') or {}).get('total_tokens') or 0 for r in ledger),
                    unknown_usage=sum((r.get('usage') or {}).get('total_tokens') is None for r in ledger)))


if __name__=='__main__':
    print(json.dumps(summarize(),indent=2))
