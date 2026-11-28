"""Compare archived strong outputs with the score-feasible JCC output inventory."""
from collections import Counter, defaultdict
import json

from joint_context import OUT, aligned, metrics, prepare, read

BRANCHES = ('SCOPE', 'OPT_GATE', 'JCC')


def summarize(cards, scope, records):
    indexed = {(row['uid'], row['method']): row for row in records}
    counters = defaultdict(lambda: defaultdict(Counter))
    groups = defaultdict(set)
    for card in cards:
        uid, domain, stratum = (card[field] for field in ('uid', 'domain', 'stratum'))
        row = {arm: indexed[uid, arm] for arm in BRANCHES if arm != 'SCOPE'}
        row['SCOPE'] = scope[uid]
        reference = metrics(card, card['base_score'])
        variants = {arm: metrics(card, item['score']) for arm, item in row.items()}
        observed = {arm: grade for arm, grade in variants.items() if grade is not None}
        count = counters[domain][stratum]
        count['assigned'] += 1
        if reference is None or len(observed) != len(BRANCHES):
            count['missing'] += 1
            continue
        if not aligned({'BASE': reference, **variants}, ('BASE', *BRANCHES)):
            raise ValueError('Complete inventory did not align')
        if domain == 'RPEval' and any(flags != [] for flags in (
                card['base_flags'], *(row[arm].get('score_flags') for arm in BRANCHES))):
            count['excluded_by_known_score_flags'] += 1
            continue
        count['compared'] += 1
        count['reference_score'] += reference['primary']
        count['available_positions'] += reference['positions']
        count['reference_missed'] += reference['positions'] - reference['primary']
        gains = []
        raw_gains = []
        for grade in observed.values():
            gain = grade['primary'] - reference['primary']
            raw_gains.append(gain)
            if domain == 'RPEval':
                preserving = all(grade[k] <= reference[k] for k in ('OPB', 'UPB', 'FM'))
            elif domain == 'BenchPreS':
                preserving = (grade['MR'] <= reference['MR']
                              and grade['completeness'] >= reference['completeness'])
            else:
                preserving = grade['strict_pass'] >= reference['strict_pass']
            if preserving:
                gains.append(gain)
        best = max([0, *gains])
        count['unconstrained_oracle_gain'] += max([0, *raw_gains])
        count['protected_oracle_gain'] += best
        count['improved_tasks'] += best > 0
        if best:
            groups[domain, stratum].add(card['group'])
    return {domain: {stratum: dict(count, improved_groups=len(groups[domain, stratum]))
                     for stratum, count in strata.items()} for domain, strata in counters.items()}


if __name__ == '__main__':
    _, cards, _, scope, _, _ = prepare()
    print(json.dumps(summarize(cards, scope, read(OUT/'RESULTS.json')['rows']), indent=2))
