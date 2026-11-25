"""Evaluation-only three-draw BenchPreS summary; no generation dependencies."""


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def summarize(cases, methods, rows):
    """Keep incomplete fixed panels distinct from complete three-sample means.

    Expected label counts belong to the evaluation manifest, never Actor input.
    This function does not certify the Judge/provider or native prompt parity.
    """
    case_index = {}
    for case in cases:
        if case.get('category') != 'benchpres':
            continue
        uid = case['uid']
        if uid in case_index:
            raise ValueError('Duplicate native case')
        a, m = case['metric_expected_aar'], case['metric_expected_mr']
        if type(a) is not int or type(m) is not int or min(a, m) < 0 or a + m != 5:
            raise ValueError('Expected five-attribute evaluation labels required')
        case_index[uid] = case
    if not case_index or len(set(methods)) != len(methods) or not methods:
        raise ValueError('Nonempty fixed panel and unique methods required')
    index = {}
    for row in rows:
        if row.get('category') != 'benchpres':
            continue
        uid, method, rep = row['uid'], row['method'], row['replicate']
        if uid not in case_index or method not in methods or type(rep) is not int or rep not in range(3):
            raise ValueError('Score outside frozen case/method/draw allocation')
        key = uid, method, rep
        if key in index:
            raise ValueError('Duplicate draw cannot count as independent sample')
        score = row.get('score')
        if (row['status'] == 'SCORED') != (score is not None):
            raise ValueError('Score and delivery status contradict each other')
        if score is not None:
            for kind in ('aar', 'mr'):
                n, d = score[kind + '_numerator'], score[kind + '_denominator']
                if (type(n) is not int or type(d) is not int or not 0 <= n <= d
                        or d != case_index[uid]['metric_expected_' + kind]):
                    raise ValueError('Score counts differ from evaluation-only label manifest')
            complete = score['task_completeness']
            if type(complete) is not int or not 1 <= complete <= 5:
                raise ValueError('Invalid completeness rating')
        index[key] = row
    results = {}
    for method in methods:
        draws = []
        for rep in range(3):
            valid, missing = [], []
            for uid in case_index:
                row = index.get((uid, method, rep))
                if row is None or row.get('score') is None:
                    missing.append({'uid': uid, 'status': 'UNISSUED' if row is None else row['status']})
                else:
                    valid.append(row)
            metrics, conditional, bounds, counts = {}, {}, {}, {}
            for kind in ('aar', 'mr'):
                numerator = sum(r['score'][kind + '_numerator'] for r in valid)
                known_denominator = sum(r['score'][kind + '_denominator'] for r in valid)
                denominator = sum(c['metric_expected_' + kind] for c in case_index.values())
                counts[kind] = {'observed_numerator': numerator, 'observed_denominator': known_denominator,
                                'fixed_panel_denominator': denominator}
                metrics[kind.upper()] = None if missing else _ratio(numerator, denominator)
                conditional[kind.upper()] = _ratio(numerator, known_denominator)
                bounds[kind.upper()] = {'low': _ratio(numerator, denominator),
                    'high': _ratio(numerator + denominator - known_denominator, denominator)}
            total = sum(r['score']['task_completeness'] for r in valid)
            metrics['completeness'] = None if missing else total / len(case_index)
            conditional['completeness'] = _ratio(total, len(valid))
            bounds['completeness'] = {'low': (total + len(missing)) / len(case_index),
                                     'high': (total + 5 * len(missing)) / len(case_index)}
            draws.append({'replicate': rep, 'expected_roots': len(case_index), 'valid_roots': len(valid),
                          'missing': missing, 'counts': counts, 'fixed_panel_metrics': metrics,
                          'available_only_diagnostic': conditional, 'missing_bounds': bounds})
        mean = {key: (sum(d['fixed_panel_metrics'][key] for d in draws) / 3
                      if all(d['fixed_panel_metrics'][key] is not None for d in draws) else None)
                for key in ('MR', 'AAR', 'completeness')}
        results[method] = {'draws': draws, 'three_draw_mean': mean,
                           'all_planned_draws_scored': all(not d['missing'] for d in draws)}
    return {'methods': results, 'replicates': 3, 'fixed_roots': len(case_index),
            'aggregation': 'mean of three fixed-panel sample metrics; no valid-only pooling',
            'judge_provider_parity_proven': False, 'paper_comparability_proven': False,
            'new_model_calls': 0, 'scores_modified': False}
