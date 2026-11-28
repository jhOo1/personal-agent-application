"""Summarize the frozen fit comparison from private receipts without making model calls."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
import json

from paired_macro import pairwise
from summarize_reassembly import aligned, bounds, measure
from trial import RUN, POLICIES

SEEDS = ('BASE', *POLICIES)


def metrics(card, score):
    domain = card['domain']
    if domain == 'RPEval' and not (score or {}).get('match'):
        return None
    values = measure(domain, card['stratum'], score)
    if domain == 'PersistBench' and values and card['stratum'] == 'beneficial_memory_usage':
        values['primary'] = values['strict_pass']
    return values


def macro(summary, methods):
    domain_scores = {arm: {} for arm in methods}
    persist_tracks = ('sycophancy', 'cross_domain', 'beneficial_memory_usage')
    for arm, parts in domain_scores.items():
        rpe = summary['RPEval']['paired_native'][arm]
        bench = summary['BenchPreS']['paired_native'][arm]
        if rpe['positions']:
            parts['RPEval'] = rpe['primary'] / rpe['positions']
        if bench['positions'] and bench['MR_denominator']:
            count = summary['BenchPreS']['common']
            aar = bench['primary'] / bench['positions']
            suppression = 1 - bench['MR'] / bench['MR_denominator']
            completeness = (bench['completeness'] / count - 1) / 4
            parts['BenchPreS'] = (aar + suppression + completeness) / 3
            parts['BenchPreS_without_completeness'] = (aar + suppression) / 2
        tracks = [summary['PersistBench/'+tag]['paired_native'][arm] for tag in persist_tracks]
        if all(track['positions'] for track in tracks):
            parts['PersistBench'] = sum(track['primary']/track['positions'] for track in tracks)/3
    domains = ('RPEval', 'BenchPreS', 'PersistBench')
    combined = {arm: sum(parts[d] for d in domains)/3 for arm, parts in domain_scores.items()
                if all(d in parts for d in domains)}
    ref = 'SELF_RECHECK' if 'SELF_RECHECK' in methods else 'GENERIC'
    gains = {}
    if ref in combined:
        for arm in methods[1:]:
            if arm != ref and arm in combined:
                changes = {d: domain_scores[arm][d]-domain_scores[ref][d] for d in domains}
                gains[arm] = dict(by_domain=changes, worst_allowed_weights=(sum(changes.values())+min(changes.values()))/4)
    return dict(parts=domain_scores, common_macro=combined, reference=ref, gains=gains)


def main():
    cli = ArgumentParser(description=__doc__)
    cli.add_argument('--external', action='store_true')
    cli.add_argument('--task-only', action='store_true')
    cli.add_argument('--crossover', action='store_true')
    options = cli.parse_args()
    plan = json.loads((RUN/'private/FROZEN.json').read_text())
    result = json.loads((RUN/'RESULTS.json').read_text())
    methods = SEEDS
    for enabled, suffix, method in (
        (options.external, '_self_recheck', 'SELF_RECHECK'),
        (options.task_only, '_task_only', 'TASK_ONLY'),
        (options.crossover, '_crossover', 'TASK_PLAN_SELECTED'),
    ):
        if enabled:
            extra = json.loads((RUN.with_name(RUN.name+suffix)/'RESULTS.json').read_text())
            result['rows'].extend(extra['rows'])
            result['ledger'].extend(extra['ledger'])
            methods += (method,)
    active = methods[1:]
    outcomes = {(row['uid'], row['method']): row for row in result['rows']}
    assert len(outcomes) == len(result['rows']) == len(plan['rows']) * len(active)
    groups = defaultdict(list)
    for card in plan['rows']:
        rows = {arm: outcomes[card['uid'], arm] for arm in active}
        scores = {'BASE': card['base_score'], **{arm: row['score'] for arm, row in rows.items()}}
        values = {arm: metrics(card, scores[arm]) for arm in methods}
        assert values['BASE'] is not None
        for key in (card['domain'], card['domain']+'/'+card['stratum']):
            groups[key].append((card, rows, values))
    # Validate every available grade against its own fixed boundaries, even if another arm is missing.
    for domain in ('RPEval', 'BenchPreS', 'PersistBench'):
        for _, _, values in groups[domain]:
            for method in active:
                if values[method] is not None:
                    assert aligned(values, ('BASE', method))
    summary = {}
    for name, entries in groups.items():
        common = [(c, r, v) for c, r, v in entries if aligned(v, methods)]
        sums = {arm: Counter() for arm in methods}
        for _, _, values in common:
            for arm, value in values.items():
                sums[arm].update(value)
        coverage = {arm: sum(v[arm] is not None for _, _, v in entries) for arm in methods}
        flags = [v for c, r, v in common if c['domain']=='RPEval' and
                 c['base_flags']==[] and all(r[arm].get('score_flags')==[] for arm in active)]
        directions = Counter()
        for _, _, values in common:
            diff = values['TASK_ACTIONS']['primary'] - values['GENERIC']['primary']
            directions['win' if diff>0 else 'loss' if diff<0 else 'tie'] += 1
        summary[name] = dict(assigned=len(entries), common=len(common), grades_available=coverage,
            paired_native=sums, directions=directions,
            assigned_delta_bounds=bounds(entries, 'TASK_ACTIONS', 'GENERIC'),
            unflagged_rpe=dict(tasks=len(flags), positions=sum(v['BASE']['positions'] for v in flags),
                               scores={arm:sum(v[arm]['primary'] for v in flags) for arm in methods}))
    ledger = result['ledger']
    cost = dict(requests=len(ledger), status=Counter(row['status'] for row in ledger),
                stages=Counter(row['unit']['stage'] for row in ledger),
                tokens=sum((row.get('usage') or {}).get('total_tokens') or 0 for row in ledger),
                unknown_usage=sum((row.get('usage') or {}).get('total_tokens') is None for row in ledger))
    print(json.dumps(dict(cost=cost, scores=summary, search_macro=macro(summary, methods),
                          pairwise_macro=pairwise(groups, methods, aligned)), indent=2))


if __name__ == '__main__':
    main()
