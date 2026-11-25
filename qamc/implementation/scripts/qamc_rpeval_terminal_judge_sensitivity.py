"""Reconcile degree-of-use rubric conflicts across the settled 300-root panel."""

from collections import Counter
from itertools import product
from pathlib import Path

from qamc.common import parse_object
from qamc.pa.core import digest
from qamc.transport_helpers import atomic_json
import qamc_rpeval_judge_reference_audit as reference_audit
import qamc_rpeval_rubric_consistency_audit as rubric_audit

run = rubric_audit.run
TRANSITION_BITS = rubric_audit.TRANSITION_BITS


def feasible_matches(labels, fields):
    """Missing severity allows both absent and present transitions."""
    missing = [name for name in TRANSITION_BITS if name not in fields]
    return sorted({k for completion in product((0, 1), repeat=len(missing))
                   for k in rubric_audit.possible_match_counts(
                       labels, {**fields, **dict(zip(missing, completion))})})


def inspect(row, labels):
    match = row['native_fields'].get('match')
    if match is None:
        return None
    n = len(labels)
    if match['positions'] != n or not 0 <= match['matched'] <= n:
        raise ValueError(f"Malformed saved match field for {row['uid']}")
    known = {key: row['native_fields'][key] for key in TRANSITION_BITS if key in row['native_fields']}
    raw = row['raw_scores']['RPEvalJudge']
    matched = match['matched']
    possible = feasible_matches(labels, known)
    flags = []
    if not possible:
        flags.append('BIAS_FIELDS_INCOMPATIBLE')
    elif matched not in possible:
        flags.append('MATCH_CONFLICTS_WITH_BIAS')
    positives = [i for i, label in enumerate(labels, 1) if label != 'A']
    reason = parse_object(raw).get('reason')
    ordinal = (reference_audit.explicit_ordinal(labels, reason)
               if len(positives) == 1 and isinstance(reason, str) else None)
    if ordinal and ordinal[0] != positives[0]:
        flags.append('WRONG_EXPLICIT_ORDINAL')
    return {
        'uid': row['uid'], 'method': row['method'], 'author_labels': labels,
        'matched': matched, 'positions': n, 'possible_from_bias_fields': possible, 'flags': flags,
        'legacy_default_zero_changes_flag': (
            matched in possible and matched not in rubric_audit.possible_match_counts(labels, known)),
        'observed_ordinal': ordinal[0] if ordinal else None, 'judge_sha256': run.sha(raw),
        'missing_bias_fields': [name for name in TRANSITION_BITS if name not in known],
        'answer_sha256': run.sha(row['answer']),
    }


def pair_bounds(left, right):
    n, a, b = left['positions'], left['matched'], right['matched']
    if n != right['positions'] or left['author_labels'] != right['author_labels']:
        raise ValueError('Cannot pair different author reference positions')
    if left['answer_sha256'] == right['answer_sha256'] and left['judge_sha256'] == right['judge_sha256']:
        if a != b or left['flags'] != right['flags']:
            raise ValueError('Same answer and judge result has inconsistent diagnostics')
        return 0, 0
    return ((0 if left['flags'] else a) - (n if right['flags'] else b),
            (n if left['flags'] else a) - (0 if right['flags'] else b))


def compare(uids, cells, cases, left, right):
    totals, groups = Counter(), set()
    for uid in uids:
        a, b = (cells.get((uid, method)) for method in (left, right))
        if a is None or b is None:
            continue
        groups.add(cases[uid]['analysis_group_id'])
        lower, upper = pair_bounds(a, b)
        totals.update(roots=1, positions=a['positions'], left_matched=a['matched'],
                      right_matched=b['matched'], flagged_roots=bool(a['flags'] or b['flags']),
                      minimum_delta=lower, maximum_delta=upper)
    return {**totals, 'source_groups': len(groups)}


def main():
    rp = run.OUT / 'PLAN.json'
    results_path = run.OUT / 'RESULT_ROWS.json'
    gap_path = run.OUT / 'SELECTION_GENERATION_GAP_300.json'
    state_path = run.OUT / 'RUN_STATE.json'
    plan = run.read(rp)
    run.check(plan, False)
    if run.read(state_path)['phase'] != 'FORMAL_TERMINAL':
        raise ValueError('Formal panel must be settled')
    cases = {item['uid']: item for item in plan['cases']}
    rows = run.read(results_path)
    index = {(r['uid'], r['method']): r for r in rows}
    if len(index) != len(rows) or index.keys() != {(u, m) for u in cases for m in run.METHODS}:
        raise ValueError('Terminal results do not cover the frozen root/method matrix')
    refs, labels = [], {}
    for uid, case in cases.items():
        path = run.ROOT / case['evaluation_path']
        ref = run.read(path)
        intent = ref['intent_type']
        if (digest(ref) != case['evaluation_hash'] or not isinstance(intent, str)
                or not intent or set(intent) - set('ABC')):
            raise ValueError(f"Author label mismatch for {uid}")
        labels[uid] = intent
        refs.append(path)
    flags = {m: Counter(assigned_roots=len(cases)) for m in run.METHODS}
    cells = {}
    for row in rows:
        uid, arm = row['uid'], row['method']
        evidence = inspect(row, labels[uid])
        if evidence is None:
            flags[arm]['missing_match'] += 1
        else:
            cells[uid, arm] = evidence
            flags[arm].update(match_available=1, any_flag=bool(evidence['flags']),
                              missing_bias_field=bool(evidence['missing_bias_fields']),
                              false_flag_from_default_zero=evidence['legacy_default_zero_changes_flag'])
            flags[arm].update(evidence['flags'])
    rg = run.read(gap_path)['rows']
    rpr = 'RPR_PAPER_FULL'
    c5 = run.METHODS[0]
    for row in rg:
        uid = row['uid']
        if any(row['answer_matched'][m] != cells[uid, m]['matched'] for m in (c5, rpr)):
            raise ValueError(f"Admission join does not match the saved final score for {uid}")
    scopes = {'same_ids': [row['uid'] for row in rg if row['same_admitted_ids']],
              'different_ids': [row['uid'] for row in rg if not row['same_admitted_ids']]}
    cohorts = {label: [u for u, s in labels.items() if (set(s) == {'A'}) == (label == 'all_A')]
               for label in ('all_A', 'contains_B_or_C')}
    same_all_a = sorted(set(scopes['same_ids']) & set(cohorts['all_A']))
    same_nonempty = [u for u in same_all_a if index[u, c5]['view']['source_evidence']]
    report = {
        'roots': len(cases), 'method_counts': flags, 'new_model_calls': 0,
        'scores_updated': 0,
        'all_paired': {m: compare(cases, cells, cases, c5, m) for m in run.METHODS[1:]},
        'rpr_matched_selection_strata': {
            name: compare(uids, cells, cases, c5, rpr)
            for name, uids in {**scopes, **cohorts,
                               'same_ids_all_A': same_all_a,
                               'same_nonempty_ids_all_A': same_nonempty,
                               'same_empty_ids_all_A': sorted(set(same_all_a) - set(same_nonempty)),
                               'same_ids_with_BC': sorted(set(scopes['same_ids']) & set(cohorts['contains_B_or_C']))}.items()},
        'flagged_cells': [r for r in cells.values() if r['flags'] or r['legacy_default_zero_changes_flag']],
        'source_pins': {str(p.relative_to(run.ROOT)): run.pin(p) for p in (
            Path(__file__).resolve(), Path(rubric_audit.__file__).resolve(),
            Path(reference_audit.__file__).resolve(), rp, state_path, results_path, gap_path, *refs)},
    }
    atomic_json(run.OUT / 'TERMINAL_JUDGE_SENSITIVITY.json', report)
    print({k: v for k, v in report.items() if k not in {'flagged_cells', 'source_pins'}})


if __name__ == '__main__':
    main()
