"""Frozen paper-mechanism comparator on the original48 exposed RPEval roots."""
import copy
import json
import sqlite3
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts'), str(ROOT)]
from qamc.common import parse_object, sha
from qamc.pa.experiment import Experiment, load_task
from qamc.pa.prepare import write_once
from qamc.pa.report import metrics
from qamc.bace.runtime import runner_lock
from qamc.transport_helpers import atomic_json
from audit_qamc_pa_score_sensitivity import atomic_match
from qamc_stream_cooldown import CooldownGateway
from run_qamc_purpose_compatibility import fh, read, STOP
from proposals.qamc_rpreasoner_paper.engine import ARM, RPReasonerPaperEngine

OUT = ROOT / 'reports/qamc_rpreasoner_paper'
RUN = ROOT / 'runs/qamc_rpreasoner_paper/execution'
CF = ROOT / 'reports/qamc_counterfactual_admission'
P0 = ROOT / 'reports/qamc_purpose_compatibility'
PARENT = ROOT / 'reports/qamc_phase2_sparse_contract'


def freeze():
    source = read(CF / 'PLAN.json')
    terminal = read(CF / 'TERMINAL_CHECKPOINT.json')
    assert terminal['process_exit_code_observed'] == 0 and terminal['saved_cells'] == 96
    for path, expected in terminal['outcome_sha256'].items():
        assert fh(ROOT / path) == expected
    cases = [copy.deepcopy(c) for c in source['cases'] if c['benchmark'] == 'rpeval']
    assert len(cases) == 48
    tracks = sorted({c['track'] for c in cases})
    # Smoke allocation uses public track/UID only, never an answer or label.
    smoke = [min(c['uid'] for c in cases if c['track'] == t) for t in tracks]
    plan = {k: source[k] for k in ('concurrency', 'spacing_seconds', 'model',
                                  'temperature', 'input_estimate_token_cap')}
    plan.update(cases=cases, smoke_uids=smoke, arm=ARM, baseline_arms=['CF0', 'P0', 'G0'],
                request_cap=512, finite_attempt_guard=512, request_guard_is_quota=False,
                estimator_output_cap=8192, actor_output_cap=4096, judge_output_cap=2048,
                nominal_deployment_stages=3, nominal_requests_before_cache=192,
                smoke_requests_before_cache=16, smoke_is_subset_not_replication=True,
                fallback=False, failed_attempt_retry=False, no_new_samples=True,
                no_store_changes=True, exposed_development=True, independent_confirmation=False,
                paper_based_adaptation=True, literal_author_prompt_replication=False,
                generator_differs_from_common_actor=True,
                judge_protocol='rpeval_archived_rubric_adapted_v1_qwen', human_reviews=0)
    files = [Path(__file__), OUT / 'DECISION_RULES.md', OUT / 'PROTOCOL.md',
             ROOT / 'tests/test_qamc_rpreasoner_runner.py',
             ROOT / 'tests/test_qamc_rpreasoner_paper.py',
             ROOT / 'scripts/qamc_stream_cooldown.py',
             ROOT / 'scripts/run_qamc_purpose_compatibility.py',
             ROOT / 'scripts/audit_qamc_pa_score_sensitivity.py',
             CF / 'PLAN.json', CF / 'TERMINAL_CHECKPOINT.json', CF / 'RESULTS.json',
             P0 / 'PLAN.json', P0 / 'PAIRED_DIAGNOSTIC.json',
             PARENT / 'CASE_DETAILS.json', PARENT / 'RPEVAL_AVAILABILITY.json',
             ROOT / 'literature/qamc_pa_v1/RPEval/prompts/prompts_715.py']
    files += [p for p in (ROOT / 'proposals/qamc_rpreasoner_paper').glob('*.*') if p.suffix in {'.py', '.md'}]
    files += list((ROOT / 'src/qamc').rglob('*.py'))
    for c in cases:
        files += [ROOT / c[k] for k in ('public_path', 'evaluation_path', 'source_file')]
        files += [ROOT / 'runs/qamc_purpose_compatibility/execution/outcomes' / sha(c['uid'])[:24] / 'P0.json',
                  ROOT / 'runs/qamc_counterfactual_admission/execution/outcomes' / sha(c['uid'])[:24] / 'CF0.json']
    plan['hashes'] = {str(p.relative_to(ROOT)): fh(p) for p in files}
    policy = read(CF / 'DISPATCH_POLICY.json')
    policy['epoch_id'] = 'qamc_rpreasoner_paper_20261107_01'
    write_once(OUT / 'DISPATCH_POLICY.json', policy)
    write_once(OUT / 'PLAN.json', plan)
    check(plan)
    return plan


def check(plan):
    assert len(plan['cases']) == 48 and len(plan['smoke_uids']) == 4
    for path, expected in plan['hashes'].items():
        if fh(ROOT / path) != expected:
            raise ValueError('Frozen drift: ' + path)
    for c in plan['cases']:
        load_task(ROOT, c)


class PaperExperiment(Experiment):
    def __init__(self, gateway, root, run):
        super().__init__(gateway, root, run)
        self.engine = RPReasonerPaperEngine(gateway, run)

    def case(self, item):
        task = load_task(self.root, item)
        folder = self.run / 'outcomes' / sha(task.uid)[:24]
        folder.mkdir(parents=True, exist_ok=True)
        dest, saved = folder / (ARM + '.json'), folder / (ARM + '.generation.json')
        if dest.exists():
            row = read(dest)
        elif saved.exists():
            row = read(saved)
        else:
            if self.stopped():
                return
            row = {'uid': task.uid, 'benchmark': 'rpeval', 'arm': ARM,
                   'public_hash': item['public_hash'], 'pipeline_status': 'OK', 'fallback': False,
                   'answer_status': 'NOT_RUN', 'score_status': 'NOT_RUN'}
            try:
                row.update(self.engine.run(task, ARM), answer_status='OK')
            except Exception as exc:
                row.update(pipeline_status='FAILED', answer_status='FAILED',
                           error_type=type(exc).__name__, error=str(exc))
            atomic_json(saved, row)
        # A failed/unknown generation and a failed Judge are terminal identities.
        row = self.score_saved(item, task, row)
        atomic_json(dest, row)
        print(json.dumps({'uid': row['uid'], 'generation': row['pipeline_status'],
                          'score': row['score_status']}), flush=True)


def outcomes():
    return [read(p) for p in sorted((RUN / 'outcomes').glob('*/' + ARM + '.json'))]


def ledger():
    path = RUN / 'api/ledger.sqlite'
    if not path.exists():
        return [], []
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as db:
        return ([json.loads(v[0]) for v in db.execute('SELECT data FROM requests')],
                [json.loads(v[0]) for v in db.execute('SELECT data FROM cache_imports')])


def available_atomic(row, item, calls, imports):
    if row.get('answer_status') != 'OK' or row.get('pipeline_status') != 'OK':
        return None
    reference = read(ROOT / item['evaluation_path'])
    obj, origin = (row.get('score') or {}).get('raw_judge'), 'strict_saved'
    if obj is None:
        task = load_task(ROOT, item)
        prefix = 'pa/eval/' + sha(['rpeval', task.uid, task.query, reference, row['answer']]) + '/'
        paths = [RUN / 'api' / v['response_path'] for v in calls
                 if v['key'].startswith(prefix) and v['status'] == 'ok' and v.get('response_path')]
        paths += [Path(v['source_response_path']) for v in imports if v['key'].startswith(prefix)]
        objects = {}
        for path in paths:
            try:
                value = parse_object(read(path)['answer'])
                objects[sha(value)] = (value, str(path))
            except (ValueError, TypeError):
                continue
        if len(objects) != 1:
            return None
        obj, origin = next(iter(objects.values()))
    try:
        multiple = isinstance(reference['persona'], list)
        matched, total = atomic_match(obj, len(reference['persona']) if multiple else 1, multiple)
        return {'uid': row['uid'], 'matched': matched, 'total': total,
                'origin': origin, 'strict_status': row['score_status']}
    except (ValueError, KeyError, TypeError):
        return None


def report(plan):
    rows, (calls, imports) = outcomes(), ledger()
    cases = {c['uid']: c for c in plan['cases']}
    controls = {c['case']['uid']: {v['arm']: v for v in c['outcomes']}
                for c in read(PARENT / 'CASE_DETAILS.json') if c['case']['uid'] in cases}
    for uid in cases:
        for arm, directory in [('P0', 'qamc_purpose_compatibility'), ('CF0', 'qamc_counterfactual_admission')]:
            controls[uid][arm] = read(ROOT / 'runs' / directory / 'execution/outcomes' / sha(uid)[:24] / (arm + '.json'))
    old_atomic = {(v['uid'], v['arm']): v for v in read(PARENT / 'RPEVAL_AVAILABILITY.json')['rows']}
    for arm, path in [('P0', P0 / 'PAIRED_DIAGNOSTIC.json'), ('CF0', CF / 'RESULTS.json')]:
        for v in read(path)['atomic_rows']:
            old_atomic[v['uid'], arm] = v
    atoms = {v['uid']: v for row in rows
             for v in [available_atomic(row, cases[row['uid']], calls, imports)] if v is not None}
    valid = lambda x: x.get('pipeline_status') == 'OK' and x.get('score_status') == 'OK' and not x.get('fallback')
    strata = {'mixed_single_multi_diagnostic': set(cases)}
    for track in sorted({c['track'] for c in cases.values()}):
        strata[track] = {uid for uid, c in cases.items() if c['track'] == track}
    strata['multi_all'] = {uid for uid, c in cases.items() if c['track'].endswith('/multi')}
    strata['single_all'] = set(cases) - strata['multi_all']
    pairs = []
    for name, uids in strata.items():
        for arm in plan['baseline_arms']:
            strict = [v for v in rows if v['uid'] in uids and valid(v) and valid(controls[v['uid']][arm])]
            available = sorted(uid for uid in atoms if uid in uids and old_atomic.get((uid, arm), {}).get('matched') is not None)
            assert all(atoms[uid]['total'] == old_atomic[uid, arm]['total'] for uid in available)
            count = lambda which: [sum(which[uid]['matched'] for uid in available), sum(atoms[uid]['total'] for uid in available)]
            a = count(atoms)
            b = [sum(old_atomic[uid, arm]['matched'] for uid in available), a[1]]
            deltas = [atoms[uid]['matched'] - old_atomic[uid, arm]['matched'] for uid in available]
            pairs.append({'stratum': name, 'baseline': arm, 'allocated_roots': len(uids),
                          'strict_common': len(strict), 'strict_uids': [v['uid'] for v in strict],
                          'candidate_strict': metrics('rpeval', strict),
                          'control_strict': metrics('rpeval', [controls[v['uid']][arm] for v in strict]),
                          'available_common': len(available), 'available_uids': available,
                          'candidate_atomic': a, 'control_atomic': b,
                          'atomic_paired_roots': {'win': sum(d > 0 for d in deltas), 'tie': sum(d == 0 for d in deltas),
                                                 'loss': sum(d < 0 for d in deltas)}})
    cost = {'physical_requests': len(calls), 'statuses': dict(Counter(v['status'] for v in calls)),
            'usage': {k: sum((v.get('usage') or {}).get(k, 0) or 0 for v in calls)
                      for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')},
            'unknown_usage': sum(v.get('usage') is None for v in calls), 'cache_imports': len(imports),
            'nominal_deployment_stages': 3, 'cache_is_replication': False}
    result = {'expected_cells': 48, 'saved_cells': len(rows), 'generation_ok': sum(v['pipeline_status'] == 'OK' for v in rows),
              'strict_valid': sum(valid(v) for v in rows), 'atomic_rows': list(atoms.values()), 'pairs': pairs,
              'ledger': cost, 'new_calls_by_report': 0, 'human_reviews': 0, 'exposed_development': True}
    atomic_json(OUT / 'RESULTS.json', result)
    atomic_json(OUT / 'CALL_LEDGER_SUMMARY.json', cost)
    atomic_json(OUT / 'CASE_DETAILS.json', [{'case': cases[v['uid']], 'candidate': v,
                'controls': {a: controls[v['uid']][a] for a in plan['baseline_arms']}} for v in rows])
    lines = ['# Paper-based RP-Reasoner: adapted development results\n',
             f'Saved{len(rows)}/48; generation{result["generation_ok"]}; strict scoring{result["strict_valid"]}. Human0.\n',
             'Own zero-shot estimator/generator instructions; paper-mechanism adaptation, not literal author prompt or published score reproduction. Same Qwen alias, private labels only in evaluation. No SOTA claim.\n',
             '| Stratum | Control | Strict common | Candidate strict item accuracy | Control strict item accuracy | Available common | Candidate atoms | Control atoms |',
             '|---|---|---:|---|---|---:|---|---|']
    for p in pairs:
        lines.append(f'| {p["stratum"]} | {p["baseline"]} | {p["strict_common"]} | {p["candidate_strict"].get("atomic_match", "NA")} | {p["control_strict"].get("atomic_match", "NA")} | {p["available_common"]} | {p["candidate_atomic"]} | {p["control_atomic"]} |')
    lines += ['\nMacro/whole-root and severity use strict contracts in RESULTS.json; available atoms do not invent missing severity. Single and multi are separately stratified. Mixed totals are diagnostic only.\n',
              'Three deployment calls: MLE, IPE, policy-conditioned generator. Generator differs from the common Actor; this is an end-to-end comparison. Old methods are exact saved controls, not new replications.\n',
              '## Ledger\n\n```json\n' + json.dumps(cost, indent=2) + '\n```\n']
    (OUT / 'RESULTS.md').write_text('\n'.join(lines) + '\n')
    return result


def smoke_passed(plan):
    rows = {v['uid']: v for v in outcomes()}
    atoms = {v['uid'] for v in report(plan)['atomic_rows']}
    for uid in plan['smoke_uids']:
        row = rows.get(uid, {})
        if row.get('pipeline_status') != 'OK' or row.get('fallback') or uid not in atoms:
            return False
        task = load_task(ROOT, next(c for c in plan['cases'] if c['uid'] == uid))
        if len(row.get('aggregation', [])) != len(task.memories) or set(row.get('estimators', {})) != {'mle', 'ipe'}:
            return False
        if [v['text'] for v in row['view']['source_evidence']] != [m.text for m in task.memories]:
            return False
    return True


def main():
    action = sys.argv[1]
    if action == 'freeze':
        plan = freeze()
        print(json.dumps({'cases': 48, 'smoke': plan['smoke_uids'], 'new_calls': 0})); return
    plan = read(OUT / 'PLAN.json'); check(plan)
    if action == 'test':
        print(json.dumps({'verified_cases': 48, 'new_calls': 0})); return
    if action == 'report':
        result = report(plan)
        print(json.dumps({k: result[k] for k in ('saved_cells', 'strict_valid', 'generation_ok', 'ledger')})); return
    if action not in {'smoke', 'pilot'}:
        raise ValueError(action)
    if action == 'pilot' and not smoke_passed(plan):
        raise ValueError('Smoke contract failed; preserve failure without retry')
    cases = [c for c in plan['cases'] if action == 'pilot' or c['uid'] in plan['smoke_uids']]
    with runner_lock(ROOT / 'runs/qamc_pa_v1/runner.lock'):
        gateway = CooldownGateway(RUN / 'api', plan, read(OUT / 'DISPATCH_POLICY.json'), STOP)
        try:
            experiment = PaperExperiment(gateway, ROOT, RUN)
            with ThreadPoolExecutor(max_workers=plan['concurrency']) as pool:
                list(pool.map(experiment.case, cases))
        finally:
            gateway.export(); report(plan)


if __name__ == '__main__':
    main()
