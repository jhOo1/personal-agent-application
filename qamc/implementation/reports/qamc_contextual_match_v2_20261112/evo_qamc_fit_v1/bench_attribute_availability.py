"""Replay BenchPreS attribute grades independently of completeness."""
from collections import Counter

from qamc.common import parse_object


def flags(decisions):
    return {f'BenchAttr{i}': ('aar' if d['appropriate'] else 'mr', d['label']=='follow')
            for i,d in enumerate(decisions)}


def raw_flags(receipt, reference):
    result={}
    for key,(metric,_) in reference.items():
        raw=receipt.get('raw_scores',{}).get(key)
        if raw is None:
            continue
        try:
            label=parse_object(raw).get('label')
        except (TypeError,ValueError):
            continue
        if label in ('follow','do_not_follow'):
            result[key]=(metric,label=='follow')
    return result


def summarize_attributes(rows, arms):
    counters={arm:Counter() for arm in arms}
    assigned=Counter()
    for card,receipts,_ in rows:
        baseline=flags(card['base_score']['decisions'])
        outcomes={'BASE':baseline}
        for arm in arms:
            if arm=='BASE':
                continue
            receipt=receipts[arm]
            outcomes[arm]=raw_flags(receipt,baseline)
            if receipt['score'] and outcomes[arm]!=flags(receipt['score']['decisions']):
                raise ValueError('Replayed BenchPreS attributes differ from the complete grade')
        for key,(metric,_) in baseline.items():
            assigned[metric]+=1
            if not all(key in outcomes[arm] for arm in arms):
                continue
            for arm in arms:
                counters[arm][metric+'_denominator']+=1
                counters[arm][metric+'_numerator']+=outcomes[arm][key][1]
    return dict(assigned_attributes=assigned,paired_attributes=counters)
