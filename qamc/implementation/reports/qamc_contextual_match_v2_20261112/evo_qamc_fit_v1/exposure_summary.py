"""Summarize fixed-Actor exposure outcomes without calling any model."""
from collections import Counter,defaultdict
import json

from expansion_summary import metrics,native_totals
from bench_attribute_availability import summarize_attributes
from expansion_run import OUT as EXPANSION
from exposure_controls import ARMS,OUT,read
from paired_macro import pairwise
from summarize_reassembly import aligned
from trial import HERE,sha


METHODS=('BASE',*ARMS,'GATE')
RPE_PAIRS=(('OFF','SELECTED'),('FULL','SELECTED'),('GATE','SELECTED'),('GATE','BASE'))


def route_result(decision,endpoints):
    if not decision or decision['decision'] is None:
        return dict(score=None,actor_status='GATE_UNAVAILABLE')
    return endpoints[decision['decision']]


def collect():
    pin=read(OUT/'private/FROZEN.json')
    gate_path=OUT/'GATE_CHOICES.json'
    if not gate_path.exists():
        raise SystemExit('Ordinary gate decisions have not settled')
    gate=read(gate_path)
    if gate['frozen']!=sha(pin):
        raise ValueError('Gate choices came from another exposure experiment')
    archive=read(EXPANSION/'private/FROZEN.json')
    ends=read(HERE.parent/'ipe_c_two_endpoint_completion_v1'/'RESULTS.json')['rows']
    ipe_routes={row['uid']:row['old_route'] for row in ends}
    groups=defaultdict(list)
    settled=[]
    ledger=list(gate['ledger'])
    delivery=defaultdict(Counter)
    for index,cards in enumerate(archive['batches'],1):
        path=OUT/f'batch_{index}'/'RESULTS.json'
        if not path.exists():
            continue
        settled.append(index)
        result=read(path)
        ledger.extend(result['ledger'])
        results={(row['uid'],row['method']):row for row in result['rows']}
        selected={r['uid']:r for r in read(EXPANSION/f'batch_{index}'/'RESULTS.json')['rows']
                  if r['method']=='SCOPE'}
        assert len(results)==len(result['rows'])==len(cards)*2
        for card in cards:
            uid=card['uid']
            cells={a:results[uid,a] for a in ('OFF','FULL')}
            cells['SELECTED']=selected[uid]
            for arm in ('OFF','FULL'):
                row=cells[arm]
                if row.get('exact_selected_response'):
                    assert row['answer']==selected[uid]['answer'] and row['score']==selected[uid]['score']
                    cells[arm]={**row,'raw_scores':selected[uid].get('raw_scores',{})}
            cells['GATE']=route_result(gate['choices'].get(uid),cells)
            grades={arm:metrics(card,row['score']) for arm,row in cells.items()}
            grades['BASE']=metrics(card,card['base_score'])
            for arm,row in cells.items():
                delivery[arm].update({row['actor_status']:1,'grade_available':grades[arm] is not None})
                if grades[arm] is not None:
                    assert aligned(grades,('BASE',arm))
            domain=card['domain']
            keys=(domain,f"{domain}/{card['stratum']}")
            if domain=='RPEval':
                route='IPE_RETAIN' if ipe_routes[uid]=='REUSE_RP' else 'IPE_CLEAR'
                keys+=('RPEval/'+route,)
            for key in keys:
                groups[key].append((card,cells,grades))
    route_counts=defaultdict(Counter)
    for batch in pin['batches']:
        for card in batch:
            outcome=gate['choices'].get(card['uid'],{})
            route_counts[card['domain']][outcome.get('decision') or outcome.get('status','NO_SCOPE_ACTOR')]+=1
    return pin,settled,groups,ledger,delivery,route_counts


def rpe_pairs(groups):
    out={}
    for left,right in RPE_PAIRS:
        breakdown={}
        for name,rows in groups.items():
            if not (name=='RPEval' or name.startswith('RPEval/')):
                continue
            common=[]
            unflagged=[]
            source_deltas=Counter()
            for card,cells,grades in rows:
                triple=card,cells,grades
                if not aligned(grades,('BASE',left,right)):
                    continue
                common.append(triple)
                source_deltas[card['group']]+=grades[left]['primary']-grades[right]['primary']
                flags=[card['base_flags'] if arm=='BASE' else cells[arm].get('score_flags')
                       for arm in (left,right)]
                if all(f==[] for f in flags):
                    unflagged.append(triple)
            breakdown[name]=dict(primary=native_totals(common,(left,right)),
                without_known_flags=native_totals(unflagged,(left,right)),
                source_wins=sum(delta>0 for delta in source_deltas.values()),
                source_losses=sum(delta<0 for delta in source_deltas.values()),
                source_ties=sum(delta==0 for delta in source_deltas.values()))
        out[f'{left}_minus_{right}']=breakdown
    return out


def summarize():
    pin,batches,groups,ledger,delivery,gate=collect()
    if not batches:
        raise SystemExit('No exposure comparison batch has settled')
    native={name:{'assigned':len(rows),**native_totals(
            [row for row in rows if aligned(row[2],METHODS)],METHODS)} for name,rows in groups.items()}
    bench=summarize_attributes(groups['BenchPreS'],METHODS)
    return dict(finished_batches=batches,all_batches_assigned=sum(len(b) for b in pin['batches']),
                native=native,paired_comparisons=pairwise(groups,METHODS,aligned),
                rpe_pairs=rpe_pairs(groups),bench_attribute_only=bench,delivery=delivery,gate=gate,
                cost=dict(requests=len(ledger),stages=Counter(r['unit']['stage'] for r in ledger),
                          statuses=Counter(r['status'] for r in ledger),
                          tokens=sum((r.get('usage') or {}).get('total_tokens') or 0 for r in ledger),
                          unknown_usage=sum((r.get('usage') or {}).get('total_tokens') is None for r in ledger)))


if __name__=='__main__':
    print(json.dumps(summarize(),indent=2))
