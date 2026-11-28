"""Compute common-domain utility and all-assigned score bounds without requests."""
from collections import defaultdict
import json

from pinned_actor_transfer import OUT, ARMS, metrics, prepare, read, summary

DOMAINS = ('RPEval', 'BenchPreS', 'PersistBench')
BENCH_TRACKS = ('sycophancy', 'cross_domain', 'beneficial_memory_usage')
COMPARE = ('STRONG', 'SCOPE_GATE', 'SCOPE_JCC', *ARMS)


def averages(data, arm):
    rpe = data['RPEval']['values'][arm]
    bench = data['BenchPreS']['values'][arm]
    persist = [data['PersistBench/' + kind]['values'][arm] for kind in BENCH_TRACKS]
    if not (rpe.get('positions') and bench.get('positions') and bench.get('MR_denominator')
            and all(track.get('positions') for track in persist)):
        return None
    return {
        'RPEval': rpe['primary'] / rpe['positions'],
        'BenchPreS': (bench['primary'] / bench['positions']
                      + 1 - bench['MR'] / bench['MR_denominator']
                      + (bench['completeness'] / data['BenchPreS']['common'] - 1) / 4) / 3,
        'PersistBench': sum(track['primary'] / track['positions'] for track in persist) / len(persist)
    }


def compare_missing(cards, rows):
    indexed = {(row['uid'], row['method']): row for row in rows}
    limits = defaultdict(lambda: {'min': 0, 'max': 0, 'assigned_positions': 0})
    for card in cards:
        uid, domain = card['uid'], card['domain']
        size = metrics(card, card['base_score'])['positions']
        first, second = (metrics(card, indexed[uid, arm]['score']) for arm in ARMS)
        a = first['primary'] if first is not None else None
        b = second['primary'] if second is not None else None
        result = limits[domain]
        result['min'] += (0 if b is None else b) - (size if a is None else a)
        result['max'] += (size if b is None else b) - (0 if a is None else a)
        result['assigned_positions'] += size
    return dict(limits)


def evaluate(cards, rows, ledger, reference):
    grouped = summary(cards, rows, ledger, reference)
    scores = {arm: averages(grouped['domains'], arm) for arm in COMPARE}
    macro = {arm: sum(parts.values()) / len(DOMAINS) for arm, parts in scores.items() if parts}
    if all(scores[arm] for arm in ARMS):
        delta = {name: scores['PIN_JCC'][name] - scores['PIN_GATE'][name] for name in DOMAINS}
        weighted_min = (sum(delta.values()) + min(delta.values())) / 4
    else:
        delta, weighted_min = None, None
    return {**grouped, 'common_utility_components': scores, 'common_macro': macro,
            'pinned_delta_by_domain': delta, 'pinned_delta_worst_double_weight': weighted_min,
            'missing_bounds_pinned_primary_delta': compare_missing(cards, rows)}


if __name__ == '__main__':
    _, cards, _, _, reference, _ = prepare()
    result = read(OUT / 'RESULTS.json')
    print(json.dumps(evaluate(cards, result['rows'], result['ledger'], reference), indent=2))
