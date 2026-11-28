"""Bound achieved B/C degrees from aggregate grades without inventing slot labels."""
from qamc_rpeval_rubric_consistency_audit import DESTINATIONS_BY_GOLD, TRANSITION_BITS


def correct_degree_bounds(labels, score, target):
    """Return the feasible min/max number of correct target labels for one answer."""
    match = score['match']
    if match['positions'] != len(labels):
        raise ValueError('Author labels and graded positions diverged')
    required = sum(bit for field, bit in TRANSITION_BITS.items()
                   if score.get(field) is not None and score[field] > 0)
    forbidden = sum(bit for field, bit in TRANSITION_BITS.items() if score.get(field) == 0)
    errors = len(labels) - match['matched']
    states = {(0, 0, 0)}
    for label in labels:
        states = {
            (n_errors + bool(bit), seen | bit, n_correct + (bit == 0 and label == target))
            for n_errors, seen, n_correct in states
            for bit in (0, *DESTINATIONS_BY_GOLD[label])
            if not (bit & forbidden) and n_errors + bool(bit) <= errors
        }
    feasible = [n for count, seen, n in states if count == errors and seen & required == required]
    return (min(feasible), max(feasible)) if feasible else None


def paired_degree_bounds(rows, left, right, label, author_labels):
    low = high = common = positions = unbounded = incompatible = 0
    for card, receipts, _ in rows:
        labels = author_labels[card['uid']]
        count = labels.count(label)
        if not count:
            continue
        bounds = []
        for method in (left, right):
            score = card['base_score'] if method == 'BASE' else receipts[method]['score']
            flags = card['base_flags'] if method == 'BASE' else receipts[method].get('score_flags')
            result = correct_degree_bounds(labels, score, label)
            incompatible += result is None
            if result is None or flags != []:
                unbounded += 1
                result = (0, count)
            bounds.append(result)
        a, b = bounds
        low += a[0] - b[1]
        high += a[1] - b[0]
        common += 1
        positions += count
    return dict(common_tasks=common, author_positions=positions,
                delta_bounds=[low, high] if common else None,
                unbounded_cells=unbounded, incompatible_cells=incompatible)
