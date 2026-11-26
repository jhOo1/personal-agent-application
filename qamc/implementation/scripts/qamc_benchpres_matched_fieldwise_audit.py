"""Use independent saved fields and bound missing-slot effects on 48 frozen roots."""

from collections import Counter, defaultdict
import json
from pathlib import Path
import re

import qamc_benchpres_matched_paper_run as run
from qamc.common import parse_object

C5, GATE = run.base.OWN
PAPER = run.METHOD
METHODS = (C5, GATE, PAPER)
METRICS = ('AAR', 'bold_AAR', 'nonbold_AAR', 'MR', 'completeness')
BOLD = re.compile(r'\bbold\s+text\b', re.I)
RATING = re.compile(r'Rating:\s*\[\[([1-5])\]\]\s*$')


def archived_fields(row, reference):
    """The same value rules as the frozen scorer, applied field by field."""
    raw = row.get('raw_scores', {})
    if raw and row['actor_status'] != 'OK':
        raise ValueError('Archived grade cannot be attributed to a failed Actor')
    attrs = reference['preference_attribute']
    labels = reference['preference_label']
    if len(attrs) != 5 or len(labels) != len(attrs) or any(type(x) is not bool for x in labels):
        raise ValueError('Unexpected frozen benchmark attribute allocation')
    values = []
    for pos in range(len(attrs)):
        key = f'BenchAttr{pos}'
        try:
            value = parse_object(raw[key]).get('label')
        except (ValueError, KeyError, TypeError, AttributeError):
            value = None
        values.append({'follow': int(value == 'follow') if value in ('follow', 'do_not_follow') else None,
                       'appropriate': labels[pos], 'attribute': attrs[pos]})
    complete_reply = raw.get('BenchComplete')
    rating = RATING.search(complete_reply) if isinstance(complete_reply, str) else None
    completeness = int(rating[1]) if rating else None
    strict = row.get('score')
    if strict is not None:
        measured = [(s['attribute'], s['appropriate'], s['follow']) for s in values]
        expected = [(d['preference'], d['appropriate'], int(d['label'] == 'follow'))
                    for d in strict['decisions']]
        if measured != expected or completeness != strict['task_completeness']:
            raise ValueError('Field-wise read did not reproduce archived strict values')
    return values, completeness


def elements(metric, slots, completeness):
    if metric == 'completeness':
        return [(uid, root['values']) for uid, root in completeness.items()]
    expected_appropriate = metric != 'MR'
    selected = []
    for s in slots:
        if s['appropriate'] != expected_appropriate:
            continue
        is_bold = BOLD.search(s['attribute']) is not None
        if (metric == 'bold_AAR' and not is_bold) or (metric == 'nonbold_AAR' and is_bold):
            continue
        selected.append((s['uid'], s['values']))
    return selected


def delta_bounds(items, left, right, value_low, value_high):
    """Bound total L-R while preserving every observed component."""
    available = [x for _, x in items if x[left] is not None and x[right] is not None]
    lo, hi = 0, 0
    for _, values in items:
        a, b = values[left], values[right]
        lo += (value_low if a is None else a) - (value_high if b is None else b)
        hi += (value_high if a is None else a) - (value_low if b is None else b)
    n = len(items)
    return {'allocation': n, 'common_observed': len(available),
            'common_observed_sum': {m: sum(v[m] for v in available) for m in (left, right)},
            'missing_positions': {m: sum(x[m] is None for _, x in items) for m in (left, right)},
            'full_allocation_delta_numerator_bounds': [lo, hi],
            'full_allocation_delta_ratio_bounds': [lo / n, hi / n] if n else None}


def missed_c5_preference(case, claim, c5):
    task = run.base.task_for(case)
    def normalized(s):
        return s.strip().casefold().rstrip('.')
    literal = [m.memory_id for m in task.memories if normalized(m.text) == normalized(claim)]
    visible = (c5.get('view') or {}).get('source_evidence', [])
    wire = c5['actor_request']
    if run.sha(wire) != c5['actor_request_sha256']:
        raise ValueError('Saved C5 Actor wire fingerprint changed')
    sources = [r for r in visible if normalized(r['text']) == normalized(claim)]
    if any(r['text'] not in wire['messages'][0]['content'] for r in sources):
        raise ValueError('The saved view mentioned a literal source absent from the Actor wire')
    matching = [r['memory_id'] for r in sources]
    if not literal:
        stage = 'NO_EXACT_ATTRIBUTE_MATCH'
    elif matching:
        stage = 'EXACT_ORIGINAL_DELIVERED_TO_ACTOR'
    elif set(literal) & {r['memory_id'] for r in visible}:
        stage = 'SOURCE_DELIVERED_WITHOUT_EXACT_ATTRIBUTE'
    else:
        stage = 'EXACT_ORIGINAL_NOT_DELIVERED'
    return {'literal_source_ids': literal, 'delivered_literal_ids': matching,
            'stage': stage, 'c5_actor_request_sha256': c5.get('actor_request_sha256')}


def audit(plan, rows):
    cases = {case['uid']: case for case in plan['cases']}
    index = {(r['uid'], r['method']): r for r in rows}
    if index.keys() != {(u, m) for u in cases for m in METHODS} or len(index) != len(rows):
        raise ValueError('Expected exactly three frozen methods at each root')
    slots, complete, recovered, misses = [], {}, [], []
    for uid, case in cases.items():
        ref = run.read(run.ROOT / case['evaluation_path'])
        parsed, ratings = {}, {}
        for method in METHODS:
            row = index[uid, method]
            parsed[method], ratings[method] = archived_fields(row, ref)
            if row.get('score') is None:
                known = sum(v['follow'] is not None for v in parsed[method])
                recovered.append({'uid': uid, 'method': method, 'actor_status': row['actor_status'],
                                  'available_attr_fields': known, 'completeness': ratings[method],
                                  'strict_score_error': row.get('score_error')})
        complete[uid] = {'values': ratings, 'profile': case['analysis_group_id']}
        for pos, (text, authorized) in enumerate(zip(ref['preference_attribute'], ref['preference_label'], strict=True)):
            values = {method: parsed[method][pos]['follow'] for method in METHODS}
            slot = {'uid': uid, 'profile': case['analysis_group_id'], 'attribute': text,
                    'appropriate': authorized, 'position': pos, 'values': values}
            slots.append(slot)
            if authorized and not BOLD.search(text) and values[C5] == 0 and values[PAPER] == 1:
                misses.append({**slot, **missed_c5_preference(case, text, index[uid, C5])})
    pairs = []
    for left, right in ((C5, PAPER), (GATE, PAPER), (C5, GATE)):
        metrics = {}
        for name in METRICS:
            items = elements(name, slots, complete)
            low, high = (1, 5) if name == 'completeness' else (0, 1)
            metrics[name] = delta_bounds(items, left, right, low, high)
        by_profile = defaultdict(lambda: [0, 0, 0])
        for slot in slots:
            values = slot['values']
            if not slot['appropriate'] or BOLD.search(slot['attribute']) or any(values[m] is None for m in (left, right)):
                continue
            counts = by_profile[slot['profile']]
            counts[0] += 1
            counts[1] += values[left]
            counts[2] += values[right]
        pairs.append({'left': left, 'right': right, 'metrics': metrics,
                      'nonbold_observed_by_profile': dict(by_profile)})
    return {'roots': len(cases), 'profiles': len({c['analysis_group_id'] for c in cases.values()}),
            'archived_method_cells': len(rows), 'method_cells_missing_strict': recovered,
            'pairs': pairs, 'c5_nonbold_misses_when_paper_follows': misses,
            'c5_nonbold_miss_source_state': dict(Counter(item['stage'] for item in misses)),
            'scores_unchanged': True, 'new_model_calls': 0, 'not_native_paper_protocol': True}


def main():
    state = run.read(run.OUT / 'RUN_STATE.json')
    if state['phase'] != 'DEV_TERMINAL':
        raise ValueError('Only the terminal frozen scope is eligible')
    plan_path = run.OUT / 'PLAN.json'
    matched_path = run.OUT / 'RESULT_ROWS.json'
    old_path = run.base.OUT / 'RESULT_ROWS.json'
    plan = run.read(plan_path)
    run.check(plan, False)
    cases = {c['uid'] for c in plan['cases']}
    old = [x for x in run.read(old_path) if x['uid'] in cases and x['method'] in (C5, GATE)]
    rows = old + run.read(matched_path)
    result = audit(plan, rows)
    result['source_pins'] = {str(p.relative_to(run.ROOT)): run.pin(p)
                             for p in (plan_path, matched_path, old_path, Path(__file__).resolve())}
    run.formal.frozen(run.OUT / 'FIELDWISE_MISSINGNESS_AUDIT.json', result)
    for pair in result['pairs']:
        print(pair['left'], pair['right'])
        print(json.dumps(pair['metrics']))
    print(result['c5_nonbold_miss_source_state'])


if __name__ == '__main__':
    main()
