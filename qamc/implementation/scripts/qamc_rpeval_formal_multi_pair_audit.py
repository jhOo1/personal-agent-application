"""Evaluate same-root differences and group concentration from saved waves."""
from collections import defaultdict
from itertools import combinations
import random

import qamc_rpeval_formal_multi_report as report
from qamc.contextual_match.evaluation import percentile

run = report.experiment
METRICS = ('match', 'full_match', *report.SEVERITIES)
STRATA = ('all', 'explicit/multi', 'implicit/multi', 'inherited', 'new_generation',
          'all_ignore', 'requires_preference')


def score_parts(metric, row):
    value = row.get('native_fields', {}).get(metric)
    if value is None:
        return None
    if metric == 'match':
        return value['matched'], value['positions']
    return value, 1


def paired_endpoint(rows, cases, left, right, metric, draws=2000, seed=20261115):
    maximum = 1 if metric in ('match', 'full_match') else 5
    availability = dict.fromkeys(('both', 'left_only', 'right_only', 'neither'), 0)
    groups = defaultdict(lambda: {'roots': 0, 'left_sum': 0, 'right_sum': 0, 'denominator': 0})
    entire_denominator = 0
    observed_left = observed_right = missing_left = missing_right = 0
    wins = losses = ties = 0
    root_deltas = []
    for case in cases:
        uid = case['uid']
        expected = case['preference_count'] if metric == 'match' else 1
        a = score_parts(metric, rows[uid, left])
        b = score_parts(metric, rows[uid, right])
        entire_denominator += expected
        for value in (a, b):
            if value is not None and (value[1] != expected or not 0 <= value[0] <= expected * maximum):
                raise ValueError(f'Saved score incompatible with frozen denominator: {uid} {metric}')
        if a is None:
            missing_left += expected
        else:
            observed_left += a[0]
        if b is None:
            missing_right += expected
        else:
            observed_right += b[0]
        if a is None or b is None:
            bucket = 'right_only' if a is None and b is not None else 'left_only' if a is not None else 'neither'
            availability[bucket] += 1
            continue
        availability['both'] += 1
        group_id = case['analysis_group_id']
        group = groups[group_id]
        group['roots'] += 1
        group['left_sum'] += a[0]
        group['right_sum'] += b[0]
        group['denominator'] += expected
        wins += a[0] > b[0]
        losses += a[0] < b[0]
        ties += a[0] == b[0]
        root_deltas.append({'uid': uid, 'group_id': group_id, 'left_sum': a[0],
                            'right_sum': b[0], 'denominator': expected})
    left_sum = sum(g['left_sum'] for g in groups.values())
    right_sum = sum(g['right_sum'] for g in groups.values())
    diff = left_sum - right_sum
    denominator = sum(g['denominator'] for g in groups.values())
    contributions = []
    for group_id, group in groups.items():
        local = group['left_sum'] - group['right_sum']
        remaining = denominator - group['denominator']
        contributions.append({'group_id': group_id, **group, 'numerator_difference': local,
                              'excluding_group_delta': (diff - local) / remaining if remaining else None})
    contributions.sort(key=lambda g: (-abs(g['numerator_difference']), g['group_id']))
    rng = random.Random(seed)
    group_weights = [(g['numerator_difference'], g['denominator'])
                     for g in sorted(contributions, key=lambda g: g['group_id'])]
    resampled = []
    if len(group_weights) >= 2:
        for _ in range(draws):
            chosen = rng.choices(group_weights, k=len(group_weights))
            resampled.append(sum(n for n, d in chosen) / sum(d for n, d in chosen))
    return {
        'left': left, 'right': right, 'metric': metric, 'completed_roots': len(cases),
        'availability': availability, 'common_root_higher_lower_tied': [wins, losses, ties],
        'common_left_sum': left_sum, 'common_right_sum': right_sum, 'common_denominator': denominator,
        'delta_left_minus_right': diff / denominator if denominator else None,
        'common_source_groups': len(groups), 'source_group_contributions': contributions,
        'common_root_scores': root_deltas,
        'source_group_resampling_95_percentile': [percentile(resampled, q) for q in (.025, .975)],
        'group_resampling_draws': len(resampled),
        'completed_roots_missing_score_delta_bounds': [
            (observed_left - observed_right - maximum * missing_right) / entire_denominator,
            (observed_left + maximum * missing_left - observed_right) / entire_denominator,
        ] if entire_denominator else [None, None],
    }


def build(snapshot, rows, cases, methods):
    index = {(row['uid'], row['method']): row for row in rows}
    if len(index) != len(rows):
        raise ValueError('Duplicate completed method trajectory')
    completed = {row['uid'] for row in rows}
    if set(index) != {(uid, method) for uid in completed for method in methods}:
        raise ValueError('Report requires a completed wave for each included root')
    audited_cases = []
    for case in cases:
        if case['uid'] not in completed:
            continue
        count = len(run.task_for(case).memories)
        labels = run.read(run.ROOT / case['evaluation_path'])['intent_type']
        if not isinstance(labels, str) or len(labels) != count or not set(labels) <= {'A', 'B', 'C'}:
            raise ValueError('Saved author preference labels do not align with the public input')
        audited_cases.append({**case, 'preference_count': count, 'all_ignore': set(labels) == {'A'}})
    cases = audited_cases
    subgroups = {
        'all': cases,
        'explicit/multi': [c for c in cases if c['track'] == 'explicit/multi'],
        'implicit/multi': [c for c in cases if c['track'] == 'implicit/multi'],
        'inherited': [c for c in cases if c['legacy_same_configuration_uid']],
        'new_generation': [c for c in cases if not c['legacy_same_configuration_uid']],
        'all_ignore': [c for c in cases if c['all_ignore']],
        'requires_preference': [c for c in cases if not c['all_ignore']],
    }
    results = []
    for left, right in combinations(methods, 2):
        for stratum in STRATA:
            for metric in (METRICS if stratum == 'all' else ('match', 'full_match', 'OPB', 'UPB')):
                if subgroups[stratum]:
                    results.append({'stratum': stratum, **paired_endpoint(
                        index, subgroups[stratum], left, right, metric,
                        draws=2000 if stratum == 'all' else 0)})
    return {
        'observed_unix': snapshot['observed_unix'], 'complete': snapshot['complete'],
        'completed_waves': snapshot['completed_waves'], 'completed_roots': len(cases),
        'completed_source_groups': len({c['analysis_group_id'] for c in cases}),
        'stratum_counts': {key: len(value) for key, value in subgroups.items()},
        'pairs': results, 'new_model_calls': 0,
        'group_resampling_is_descriptive': True, 'missing_bounds_are_not_imputed_scores': True,
    }


def main():
    snapshot, rows = report.snapshot()
    plan = run.read(run.OUT/'PLAN.json')
    value = build(snapshot, rows, plan['cases'], plan['methods'])
    # Cross-check same-root numerators and denominators against the existing
    # progress report before publishing the additional diagnostics.
    expected = {(p['left'], p['right'], p['metric']): p for p in snapshot['pairs']}
    for pair in value['pairs']:
        if pair['stratum'] != 'all':
            continue
        original = expected[pair['left'], pair['right'], pair['metric']]
        metric = pair['metric']
        total_key = 'positions' if metric == 'match' else 'valid_roots'
        sum_key = 'matched' if metric == 'match' else 'sum'
        if (pair['availability']['both'] != original['common_roots']
                or pair['common_denominator'] != original['left_counts'][total_key]
                or pair['common_left_sum'] != original['left_counts'][sum_key]
                or pair['common_right_sum'] != original['right_counts'][sum_key]):
            raise ValueError('Same-root diagnostic disagrees with the frozen report')
    run.previous.previous.prior.atomic_json(run.OUT/'PAIRED_SCORE_AUDIT.json', value)

    def pct(number):
        return 'NA' if number is None else f'{100 * number:+.2f} pp'

    lines = ['# RPEval 同题分差及来源组检查', '',
             f"已完成 {value['completed_waves']} 波，覆盖 {value['completed_roots']}/300 题和 "
             f"{value['completed_source_groups']} 个普查来源组。"
             '各行只比较双方该指标都有分的题。区间采用整组重采样，属于描述性敏感性检查。', '',
             '|对手|指标|共同题 / 组|QAMC|对手|同题差|组重采样区间|计入缺失的不确定范围|',
             '|---|---|---:|---:|---:|---:|---:|---:|']
    for pair in value['pairs']:
        if pair['stratum'] != 'all' or pair['left'] != plan['methods'][0] or pair['metric'] not in ('match', 'full_match'):
            continue
        ci = ' 至 '.join(map(pct, pair['source_group_resampling_95_percentile']))
        bounds = ' 至 '.join(map(pct, pair['completed_roots_missing_score_delta_bounds']))
        denominator = pair['common_denominator']
        lines.append(f"|{pair['right']}|{pair['metric']}|{pair['availability']['both']} / "
                     f"{pair['common_source_groups']}|{pair['common_left_sum']}/{denominator}|"
                     f"{pair['common_right_sum']}/{denominator}|{pct(pair['delta_left_minus_right'])}|{ci}|{bounds}|")
    lines += ['', '完整 JSON 包含每组贡献、逐题分差、去掉任一来源组后的分差，以及按公开输入轨道、生成来源和作者偏好标签划分的结果。'
              '缺失范围用已完成波次中两边尚无有效评分的端点取可能上下界，未对原分补值。'
              '较高的 match 和 full_match 表示较多匹配。OPB、UPB 等严重度报告原始分差。']
    (run.OUT/'PAIRED_SCORE_AUDIT.md').write_text('\n'.join(lines)+'\n')
    print({'completed_roots': value['completed_roots'], 'pairs': len(value['pairs']), 'new_model_calls': 0})


if __name__ == '__main__':
    main()
