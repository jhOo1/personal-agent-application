"""Zero-call snapshots of the frozen official multi coverage experiment.

This module never constructs a runtime or sampler. Intermediate scores do not
change the frozen policies, waves, or stopping rules.
"""
from collections import Counter
from itertools import combinations
import json
import os
from pathlib import Path
from statistics import mean, median
import time

import qamc_rpeval_formal_multi_run as experiment
from qamc_rpeval_fieldwise_audit import SEVERITIES, summarize
from qamc.contextual_match.rpeval_author_aggregation import replay
from qamc.contextual_match import selection_diagnostic as classification
from qamc.common import parse_object


def selection_measurements(rows, cases):
    """Measure explicit executable decisions, never infer them from prose."""
    cells = []
    for row in rows:
        case = cases[row['uid']]
        cell = {'phase': 'formal_multi', 'uid': row['uid'], 'method': row['method'],
                'group_id': case['analysis_group_id'], 'measurement': None}
        try:
            method = row['method']
            if method in experiment.legacy.OWN:
                codec, value = 'sparse_style', row.get('compiler_selection', row.get('selection'))
            elif method == 'RPR_PAPER_FULL':
                codec, value = 'ranked_policy', row.get('aggregation')
            elif method == 'DES2GEN_FULL':
                codec, value = 'des2gen', row.get('decisions')
            else:
                cell['unavailable_reason'] = 'NO_EXPLICIT_CATEGORICAL_DECISIONS'
                cells.append(cell)
                continue
            task = experiment.task_for(case)
            predictions = classification.decisions(task, codec, value)
            ref = experiment.read(experiment.ROOT/case['evaluation_path'])
            cell['measurement'] = classification.measure(task, predictions, ref)
        except (ValueError, TypeError, KeyError, AttributeError) as error:
            cell['unavailable_reason'] = str(error)
        cells.append(cell)
    return {'summaries': {m: classification.summarize([c for c in cells if c['method'] == m])
                           for m in experiment.METHODS},
            'pairs': [classification.paired(cells, ('formal_multi', left), ('formal_multi', right))
                      for left, right in combinations(experiment.METHODS, 2)], 'cells': cells,
            'not_generated_answer_usage_or_OPB_UPB': True}


def author_tables(rows, cases):
    """Keep unavailable Judge objects empty under the exact author aggregation.

    Missing physical responses remain missing. The original author's handling
    of empty fields is reported separately from valid-field diagnostics.
    """
    native = []
    for method in experiment.METHODS:
        entries = []
        for r in rows:
            if r['method'] != method:
                continue
            raw = r.get('raw_scores', {}).get('RPEvalJudge')
            try:
                obj = parse_object(raw) if isinstance(raw, str) else {}
                if not isinstance(obj, dict):
                    obj = {}
            except (ValueError, TypeError):
                obj = {}
            ref = experiment.read(experiment.ROOT/cases[r['uid']]['evaluation_path'])
            entries.append({'uid': r['uid'], 'ground_truth_type': ref['intent_type'],
                'generated_reply': r.get('answer'), 'judge_result': obj,
                'status': r.get('actor_status', 'UNKNOWN')})
        if entries:
            native.append({'method': method, **replay(experiment.ROOT/'literature/qamc_pa_v1/RPEval/generation_task/eval_multi.py', entries, True)})
    return native


def snapshot():
    """Read only completed waves and existing physical-call receipts."""
    p = experiment.read(experiment.OUT/'PLAN.json')
    experiment.check(p, False)
    rows = [row for path in sorted((experiment.OUT/'waves').glob('*.json'))
            for row in experiment.read(path)['rows']]
    if len({(r['uid'], r['method']) for r in rows}) != len(rows):
        raise ValueError('Duplicate completed wave row')
    records = [experiment.read(path) for path in
               experiment.RUN.glob('*/execution/visible/*/record.json')]
    state_path = experiment.OUT/'RUN_STATE.json'
    state = experiment.read(state_path) if state_path.exists() else {}
    pid = state.get('pid')
    live = False
    if pid:
        try:
            os.kill(pid, 0)
            live = True
        except ProcessLookupError:
            pass
    pending = [r for r in records if r['status'] == 'PENDING_DELIVERY_UNKNOWN']
    settled = [r for r in records if r['status'] != 'PENDING_DELIVERY_UNKNOWN']
    current_stage = None
    if state.get('stage') and state.get('model_block'):
        manifest = experiment.OUT/state['model_block']/'stage_manifests'/('component_'+state['stage']+'.json')
        if manifest.exists():
            jobs = experiment.read(manifest)['units']
            keys = {experiment.sampling_key(j['unit']) for j in jobs}
            outputs = []
            for key in keys:
                path = experiment.RUN/state['model_block']/'outputs'/(key+'.json')
                if path.exists():
                    outputs.append(experiment.read(path))
            stage_records = [r for r in records if experiment.sampling_key(r['unit']) in keys]
            current_stage = {'name': state['stage'], 'planned_logical_positions': len(keys),
                'completed_logical_outputs': len(outputs),
                'logical_output_statuses': dict(Counter(r['status'] for r in outputs)),
                'physical_registered': len(stage_records),
                'pending_registered': sum(r['status'] == 'PENDING_DELIVERY_UNKNOWN' for r in stage_records),
                'cross_file_snapshot_is_not_transactional': True}
    durations = [r['elapsed_seconds'] for r in settled if type(r.get('elapsed_seconds')) in (int, float)]
    logical = [experiment.read(path) for path in experiment.RUN.glob('*/outputs/*.json')]
    cost = {'physical_requests': len(records), 'maximum': p['maximum_new_physical_requests'],
        'statuses': dict(Counter(r['status'] for r in records)),
        'reported_tokens': sum((r.get('usage') or {}).get('total_tokens', 0) for r in settled),
        'settled_unknown_usage': sum('total_tokens' not in (r.get('usage') or {}) for r in settled),
        'pending_receipts': len(pending), 'automatic_retries': sum(r.get('automatic_retries', 0) for r in records),
        'physical_by_stage': dict(Counter(r['unit']['stage'] for r in records)),
        'logical_outputs': len(logical), 'logical_output_origins': dict(Counter(r.get('origin', 'UNKNOWN') for r in logical)),
        'settled_latency_seconds': {'count': len(durations), 'mean': mean(durations) if durations else None,
            'median': median(durations) if durations else None, 'max': max(durations) if durations else None},
        'USD': 'UNKNOWN', 'new_calls_by_this_report': 0}
    before = experiment.read(experiment.bridge_probe.OUT/'CUMULATIVE_AT_REPORT.json')
    cumulative = {'total_physical_requests': before['cumulative_v2_requests']+len(records),
        'known_total_tokens': before['cumulative_v2_reported_tokens']+cost['reported_tokens'],
        'settled_unknown_total_usage': before['cumulative_v2_unknown_usage']+cost['settled_unknown_usage'],
        'pending_receipts': len(pending), 'USD': 'UNKNOWN', 'not_final_billing': True,
        'excludes_pre_v2_historical_import_cost': True}
    cases = {c['uid']: c for c in p['cases']}
    field_rows = [{**r, 'fields': r.get('native_fields', {})} for r in rows]
    tables = []
    for track in ('explicit/multi', 'implicit/multi', 'multi'):
        for method in p['methods']:
            chosen = [r for r in field_rows if r['method'] == method and
                      (track == 'multi' or cases[r['uid']]['track'] == track)]
            tables.append({'track': track, 'method': method, 'completed_rows': len(chosen),
                'expected_rows': 300 if track == 'multi' else 150,
                'answers': sum(r.get('actor_status') == 'OK' and bool(r.get('answer')) for r in chosen),
                'legacy_complete_contract_scores': sum(r.get('score') is not None for r in chosen),
                'fieldwise_diagnostic': {m: summarize(chosen, m) for m in ('match', 'full_match', *SEVERITIES)}})
    index = {(r['uid'], r['method']): r for r in field_rows}
    pairs = []
    for left, right in combinations(p['methods'], 2):
        for metric in ('match', 'full_match', *SEVERITIES):
            ids = [uid for uid in cases if (uid, left) in index and (uid, right) in index
                   and metric in index[uid, left]['fields'] and metric in index[uid, right]['fields']]
            pairs.append({'left': left, 'right': right, 'metric': metric, 'uids': ids,
                'common_roots': len(ids), 'census_source_groups': len({cases[u]['analysis_group_id'] for u in ids}),
                'left_counts': summarize([index[u, left] for u in ids], metric),
                'right_counts': summarize([index[u, right] for u in ids], metric),
                'conditional_on_availability': True, 'certified_independent_groups': False})
    return {'observed_unix': time.time(), 'state': state, 'pid_exists_now': live,
        'completed_waves': len(list((experiment.OUT/'waves').glob('*.json'))),
        'planned_waves': len(p['waves']), 'current_stage_progress': current_stage,
        'completed_rows': len(rows), 'expected_rows': 1800,
        'complete': state.get('phase') == 'FORMAL_TERMINAL' and len(rows) == 1800,
        'cost': cost, 'cumulative': cumulative, 'tables': tables, 'pairs': pairs,
        'settled_failure_index': [{'unit': r['unit'], 'request_sha256': r['request_sha256'],
            'status': r['status'], 'elapsed_seconds': r.get('elapsed_seconds'),
            'finish_reason': r.get('finish_reason'), 'received_done': r.get('received_done')}
            for r in settled if r['status'] != 'OK'],
        'selection_author_agreement': selection_measurements(rows, cases),
        'goal_complete': False}, rows


def main():
    value, rows = snapshot()
    atom = experiment.previous.previous.prior.atomic_json
    atom(experiment.OUT/'LIVE_PROGRESS.json', value)
    lines = ['# RPEval 官方300条多偏好覆盖：执行快照',
        '此报告零模型调用，不补评分、不重试、不修改方法。未完成的波次不进入成绩表。',
        f"状态：{value['state'].get('phase', 'NOT_STARTED')}；进程存在：{value['pid_exists_now']}；"
        f"已完成{value['completed_waves']}/{value['planned_waves']}波、{value['completed_rows']}/1800条方法轨迹。",
        '300根、explicit/implicit各150；不是完整600题或三基准全量，不是独立确认。'
        '45个普查组未认证为语义独立。六种策略冻结，原24题144条生成轨迹整体继承。',
        '生成Qwen3.8-Flash、评分GPT-4.1，模型别名不认证底层权重。'
        '保留作者rubric；评分争议、字段缺失和运行失败分别保存。以下逐字段可用诊断不是作者失败分母聚合。',
        '|方法|完成/预定|答案|有效逐位分母|逐位正确|整题可用正确/可用根|',
        '|---|---:|---:|---:|---:|---:|']
    for table in value['tables']:
        if table['track'] != 'multi':
            continue
        f = table['fieldwise_diagnostic']; match, whole = f['match'], f['full_match']
        lines.append(f"|{table['method']}|{table['completed_rows']}/300|{table['answers']}|"
                     f"{match['positions']}|{match['matched']}|{whole['sum']}/{whole['valid_roots']}|")
    lines += ['\n## 可执行选择与作者标签的一致性',
        '只评估方法实际给出的分类。A=忽略，B/C=应使用；普通APPLY/PARTIAL不能区分Support与Dominate。'
        '完整原文可见不等于实际放行；不从GEPA/MemAdapter的自由说明或Judge理由反推分类。'
        '标签一致性不是独立语义真值，也不是答案实际误用/漏用。',
        '|方法|分类可用根|位置|A误放|B漏留|C漏留|', '|---|---:|---:|---:|---:|---:|']
    for method, c in value['selection_author_agreement']['summaries'].items():
        errors = [str(c[k]) if c['valid_categorical_cells'] else 'NA'
                  for k in ('A_labelled_admitted', 'B_labelled_excluded', 'C_labelled_excluded')]
        lines.append(f"|{method}|{c['valid_categorical_cells']}|{c['positions']}|"
                     + '|'.join(errors)+'|')
    if value['current_stage_progress']:
        lines += ['\n## 当前组件进度（不提前算作整条轨迹完成）', '```json',
                  json.dumps(value['current_stage_progress'], indent=2), '```']
    lines += ['\n## 调用与错误', '```json', json.dumps(value['cost'], indent=2), '```',
        '在途PENDING标记是派发前登记状态；只有进程及请求终态证据才能判定交付未知。'
        '失败不能算语义答错，缓存不能算新的重复生成。',
        '\n## 累计账本', '```json', json.dumps(value['cumulative'], indent=2), '```',
        '所有中间成绩只用于观察，不能按中途胜负改Prompt、调规则、筛样本或选最好版本。']
    (experiment.OUT/'LIVE_RESULTS.md').write_text('\n\n'.join(lines).replace('|\n\n|', '|\n|')+'\n')
    if value['complete']:
        cases = {c['uid']: c for c in experiment.read(experiment.OUT/'PLAN.json')['cases']}
        experiment.frozen(experiment.OUT/'AUTHOR_NATIVE_AGGREGATION.json', author_tables(rows, cases))
        experiment.frozen(experiment.OUT/'CALL_LEDGER_SUMMARY.json', value['cost'])
    print(json.dumps({k: value[k] for k in ('completed_waves', 'completed_rows', 'complete', 'pid_exists_now', 'cost')}))


if __name__ == '__main__':
    main()
