"""Evaluation-only author-label agreement, separate from generated-answer use.

APPLY/PARTIAL cannot reveal Support versus Dominate. Free-form use instructions
cannot be converted into categorical decisions without another adjudication.
"""
from collections import Counter
from .core import normalize_selection

SINGLE = {'ignore': 'A', 'support': 'B', 'supportive': 'B', 'dominate': 'C', 'dominant': 'C',
          '忽略偏好': 'A', '调和偏好': 'B', '支持性偏好': 'B', '以偏好为主线': 'C'}


def decisions(task, codec, value):
    ids = [m.memory_id for m in task.memories]
    if codec == 'sparse_style':
        selection = normalize_selection(task, value)
        mapped = {r['memory_id']: {'admitted': r['decision'] != 'DROP', 'strength': None,
                                   'decision': r['decision']} for r in selection['preference_actions']}
    elif codec == 'abc':
        if not isinstance(value, str) or len(value) != len(ids) or not set(value) <= set('ABC'):
            raise ValueError('Policy does not align with all original memories')
        mapped = {mid: {'admitted': label != 'A', 'strength': label, 'decision': label}
                  for mid, label in zip(ids, value)}
    elif codec in {'des2gen', 'ranked_policy'}:
        if not isinstance(value, list) or len(value) != len(ids):
            raise ValueError('Categorical decision coverage differs')
        mapped = {}
        for row in value:
            mid = row['memory_id']
            if mid not in ids or mid in mapped:
                raise ValueError('Duplicate or unknown categorical memory')
            if codec == 'des2gen':
                label = row['decision']
                if label not in {'Apply', 'Suppress'}:raise ValueError('Unknown Apply/Suppress decision')
                mapped[mid] = {'admitted': label == 'Apply', 'strength': None, 'decision': label}
            else:
                label = row['policy']
                if label not in {'A', 'B', 'C'}:raise ValueError('Unknown ranked policy')
                mapped[mid] = {'admitted': label != 'A', 'strength': label, 'decision': label}
    else:
        raise ValueError('No categorical codec; do not infer decisions from prose or source visibility')
    if set(mapped) != set(ids):raise ValueError('Missing categorical memory')
    return [{'memory_id': mid, **mapped[mid]} for mid in ids]


def measure(task, predicted, reference):
    """Gold enters only this measurement, never a policy decoder or inference."""
    if isinstance(reference['persona'], list):
        policy = reference['intent_type']
        if len(reference['persona']) != len(task.memories):raise ValueError('Author preference count differs')
    else:
        if len(task.memories) != 1:raise ValueError('Single preference has multiple candidates')
        policy = SINGLE.get(reference['intent_type'])
    if not isinstance(policy, str) or len(policy) != len(task.memories) or not set(policy) <= set('ABC'):
        raise ValueError('Unknown or misaligned author policy')
    if ([r['memory_id'] for r in predicted] != [m.memory_id for m in task.memories]
            or any(type(r['admitted']) is not bool for r in predicted)):
        raise ValueError('Prediction identity or decision changed')
    rows = [{'memory_id': row['memory_id'], 'author_label': gold, **row,
             'admission_agrees': row['admitted'] == (gold != 'A'),
             'exact_abc_agrees': row['strength'] == gold if row['strength'] is not None else None}
            for row, gold in zip(predicted, policy)]
    return {'positions': rows, 'binary_all_correct': all(r['admission_agrees'] for r in rows),
            'exact_abc_all_correct': all(r['exact_abc_agrees'] for r in rows)
                if all(r['exact_abc_agrees'] is not None for r in rows) else None}


def summarize(cells):
    valid = [c for c in cells if c.get('measurement') is not None]
    positions = [r for c in valid for r in c['measurement']['positions']]
    counts = Counter(r['author_label'] for r in positions)
    exact = [r for r in positions if r['exact_abc_agrees'] is not None]
    return {'recorded_cells': len(cells), 'valid_categorical_cells': len(valid),
            'unavailable_or_non_categorical_cells': len(cells) - len(valid),
            'positions': len(positions), 'author_label_counts': dict(counts),
            'A_labelled_admitted': sum(r['author_label'] == 'A' and r['admitted'] for r in positions),
            'B_labelled_excluded': sum(r['author_label'] == 'B' and not r['admitted'] for r in positions),
            'C_labelled_excluded': sum(r['author_label'] == 'C' and not r['admitted'] for r in positions),
            'binary_correct': sum(r['admission_agrees'] for r in positions),
            'binary_all_correct_roots': sum(c['measurement']['binary_all_correct'] for c in valid),
            'exact_ABC_positions_available': len(exact),
            'exact_ABC_correct': sum(r['exact_abc_agrees'] for r in exact),
            'not_generated_answer_OPB_or_UPB': True,
            'author_agreement_is_not_independent_semantic_truth': True}


def paired(cells, left, right):
    """Pair categorical availability, not successful Actors or Judge scores."""
    index = {}
    for cell in cells:
        key = cell['phase'], cell['method'], cell['uid']
        if key in index:raise ValueError('Duplicate diagnostic cell')
        index[key] = cell
    common = sorted({uid for phase, method, uid in index if (phase, method) == left
                     and index[phase, method, uid].get('measurement') is not None
                     and (*right, uid) in index and index[*right, uid].get('measurement') is not None})
    rows = []; groups = {}
    for uid in common:
        a, b = index[*left, uid], index[*right, uid]
        ap, bp = a['measurement']['positions'], b['measurement']['positions']
        if (a['group_id'] != b['group_id']
                or [(r['memory_id'], r['author_label']) for r in ap] != [(r['memory_id'], r['author_label']) for r in bp]):
            raise ValueError('Paired identities, author labels or source grouping differ')
        ac, bc = sum(r['admission_agrees'] for r in ap), sum(r['admission_agrees'] for r in bp)
        row = {'uid': uid, 'group_id': a['group_id'], 'left_binary_correct': ac, 'right_binary_correct': bc,
               'different_admissions': [r['memory_id'] for r, s in zip(ap, bp) if r['admitted'] != s['admitted']]}
        rows.append(row); groups.setdefault(a['group_id'], []).append(row)
    a, b = ([index[*side, uid] for uid in common] for side in (left, right))
    return {'left': list(left), 'right': list(right), 'common_valid_roots': len(common),
            'source_groups': len(groups), 'left_summary': summarize(a), 'right_summary': summarize(b),
            'root_wins': sum(r['left_binary_correct'] > r['right_binary_correct'] for r in rows),
            'root_losses': sum(r['left_binary_correct'] < r['right_binary_correct'] for r in rows),
            'root_ties': sum(r['left_binary_correct'] == r['right_binary_correct'] for r in rows),
            'equal_count_ties_with_different_admissions': sum(r['left_binary_correct'] == r['right_binary_correct']
                                                            and bool(r['different_admissions']) for r in rows),
            'by_source_group': [{'group_id': group, 'uids': [r['uid'] for r in members],
                                 'binary_correct_delta': sum(r['left_binary_correct'] - r['right_binary_correct'] for r in members)}
                                for group, members in sorted(groups.items())],
            'rows': rows, 'not_a_significance_or_generated_answer_claim': True}
