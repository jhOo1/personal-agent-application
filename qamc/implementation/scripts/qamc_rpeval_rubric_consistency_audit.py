"""Check whether saved Judge fields admit a common A/B/C interpretation."""
from collections import Counter
from pathlib import Path

import qamc_rpeval_formal_multi_run as run
from qamc.pa.core import digest
from qamc.transport_helpers import atomic_json


# The archived multi-preference rubric partitions all six directed changes.
TRANSITION_BITS = {'OPB': 1, 'UPB': 2, 'RII': 4}
DESTINATIONS_BY_GOLD = {'A': (1, 4), 'B': (1, 2), 'C': (2, 4)}


def possible_match_counts(labels, fields):
    required = sum(bit for name, bit in TRANSITION_BITS.items() if fields.get(name, 0) > 0)
    forbidden = sum(bit for name, bit in TRANSITION_BITS.items() if fields.get(name) == 0)
    reached = {(0, 0)}
    for label in labels:
        # Staying at the current label is always possible. Update only after
        # considering both alternative destinations of this one position.
        reached |= {(errors + 1, seen | bit) for errors, seen in reached
                    for bit in DESTINATIONS_BY_GOLD[label] if not bit & forbidden}
    return sorted({len(labels) - errors for errors, seen in reached if seen & required == required})


def compare(left, right, cases, values):
    metrics = Counter()
    groups = set()
    for uid, case in cases.items():
        a, b = [values.get((uid, m)) for m in (left, right)]
        if a is None or b is None:
            continue
        total = a['match']['positions']
        if total != b['match']['positions']:
            raise ValueError('Unequal matching denominators')
        groups.add(case['analysis_group_id'])
        a_value, b_value = a['match']['matched'], b['match']['matched']
        a_flag, b_flag = (r['inconsistency'] is not None for r in (a, b))
        metrics.update(roots=1, positions=total, left_matches=a_value, right_matches=b_value,
                       affected_roots=a_flag or b_flag,
                       minimum_difference=(0 if a_flag else a_value) - (total if b_flag else b_value),
                       maximum_difference=(total if a_flag else a_value) - (0 if b_flag else b_value))
    return {'left': left, 'right': right, **metrics, 'groups': len(groups)}


def main():
    plan = run.read(run.OUT / 'PLAN.json')
    wave_paths = sorted((run.OUT / 'waves').glob('*.json'))
    rows = [r for path in wave_paths for r in run.read(path)['rows']]
    completed = {r['uid'] for r in rows}
    if len(rows) != len(completed) * len(run.METHODS) or len(rows) != len({
            (r['uid'], r['method']) for r in rows}):
        raise ValueError('Completed waves have incomplete method rows')
    cases = {c['uid']: c for c in plan['cases'] if c['uid'] in completed}
    labels = {}
    refs = []
    for uid, case in cases.items():
        path = run.ROOT / case['evaluation_path']
        ref = run.read(path)
        actual = ref['intent_type']
        if digest(ref) != case['evaluation_hash'] or not isinstance(actual, str) or not actual or (
                set(actual) - DESTINATIONS_BY_GOLD.keys()):
            raise ValueError('Author intent labels changed')
        labels[uid] = actual
        refs.append(path)
    by_method = {method: Counter() for method in run.METHODS}
    values = {}
    for row in rows:
        uid, method = row['uid'], row['method']
        original = row.get('native_fields', {})
        match = original.get('match')
        if match is None:
            continue
        if match['positions'] != len(labels[uid]):
            raise ValueError('Judge denominator does not match author labels')
        possible = possible_match_counts(labels[uid], original)
        inconsistency = None
        if not possible:
            inconsistency = 'TRANSITION_FIELDS_UNSATISFIABLE'
        elif match['matched'] not in possible:
            inconsistency = 'MATCH_COUNT_CONFLICTS_WITH_TRANSITION_FIELDS'
        by_method[method].update(match_available=1, flagged=inconsistency is not None)
        if inconsistency:
            by_method[method][inconsistency] += 1
        values[uid, method] = {
            'uid': uid, 'method': method, 'match': match,
            'transition_fields': {key: original.get(key) for key in TRANSITION_BITS},
            'author_intent': labels[uid], 'possible_match_counts': possible,
            'inconsistency': inconsistency, 'actor_request_sha256': row.get('actor_request_sha256'),
            'judge_answer_sha256': run.sha(row['raw_scores']['RPEvalJudge']),
        }
    pairs = [compare(run.METHODS[0], method, cases, values) for method in run.METHODS[1:]]
    rubric = run.ROOT / 'literature/qamc_pa_v1/RPEval/prompts/prompts_715.py'
    path = run.OUT / f'RUBRIC_CONSISTENCY_THROUGH_W{len(wave_paths)-1:02d}.json'
    atomic_json(path, {
        'completed_roots': len(completed), 'naming_uses_zero_based_wave': True,
        'conditional_on_both_match_fields_available': True,
        'original_scores_unchanged': True, 'new_model_calls': 0, 'human_reviews': 0,
        'assumption': 'Each positive OPB/UPB/RII applies to at least one transition in its rubric family. '
                      'Zero means absent. Missing severity is unconstrained.',
        'summaries': by_method, 'pairs': pairs,
        'flagged_cells': [v for v in values.values() if v['inconsistency']],
        'source_pins': {str(p.relative_to(run.ROOT)): run.pin(p) for p in (
            Path(__file__).resolve(), rubric, run.OUT / 'PLAN.json', *wave_paths, *refs)},
    })
    print(path.name, len(completed), by_method)
    for pair in pairs:
        print(pair)


if __name__ == '__main__':
    main()
