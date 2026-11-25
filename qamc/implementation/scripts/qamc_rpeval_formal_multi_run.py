"""Frozen six-method end-to-end official multi coverage, resumable by wave.

Original policy/Compiler/Actor builders remain unchanged. The original24 full
trajectories, including failures, are inherited. Only276 new public tasks may
generate. Gold is accessed solely by the common native-model grading builder.
"""
from collections import Counter
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
import argparse
import os
import time

import qamc_rpeval_formal_multi_prepare as data
import qamc_rpeval_native_judge_probe as bridge_probe
from qamc_rpr_appendix_resume import ScopedDispatcher
from qamc.pa.core import PublicTask, Memory
from qamc.common import parse_object
from qamc_rpeval_fieldwise_audit import fields
from prepare_qamc_rpeval_actor_development import body

previous = data.previous
legacy = previous.parent
ROOT, read, frozen, pin = data.ROOT, data.read, data.frozen, data.pin
DATA_OUT = data.OUT
OUT = DATA_OUT
RUN = ROOT/'runs'/previous.spec.BASE.name/OUT.name
METHODS = legacy.METHODS
sha = previous.sha
sampling_key = previous.sampling_key
STAGES = {
    METHODS[0]: ('Selector', 'Actor'), METHODS[1]: ('Selector', 'Actor'),
    'GEPA_UNIFIED': ('Actor',),
    'MEMADAPTER_FULL': ('MemInduction', 'MemReflection', 'Actor'),
    'RPR_PAPER_FULL': ('RPR_MLE', 'RPR_IPE', 'Actor'),
    'DES2GEN_FULL': ('Selector', 'Actor')}


def block(stage):
    return 'grading' if stage == 'RPEvalJudge' else 'generation'


def unit(p, uid, method, stage):
    return {'protocol_sha256': sha(p['protocols'][block(stage)]),
        'root_id': uid, 'method': method, 'stage': stage, 'replicate': 0}


def job(p, uid, method, stage, request):
    if method not in METHODS or stage not in (*STAGES[method], 'RPEvalJudge'):
        raise ValueError('Unknown method/stage')
    proto = p['protocols'][block(stage)]
    if request['model'] != proto['model'] or any(
            request[k] != proto['stages'][stage][k] for k in ('max_tokens', 'temperature')):
        raise ValueError('Frozen model or cap changed')
    return {'unit': unit(p, uid, method, stage), 'request': request}


@lru_cache(None)
def public_tasks():
    return read(DATA_OUT/'PUBLIC_TASKS.json')


def task_for(case):
    v = public_tasks()[case['uid']]
    return PublicTask(v['uid'], v['query'], tuple(Memory(m['memory_id'], m['text'],
        tuple(tuple(x) for x in m['ranges'])) for m in v['memories']),
        v['current_context'], tuple(v['fixed_facts']))


@lru_cache(None)
def assets():
    prompts = read(legacy.OUT/'PROMPTS.json')['base']
    author = legacy.PersistAuthorBridge(legacy.previous.parent.AUTHOR)
    mem = legacy.MemAdapterBridge(ROOT/'literature/qamc_contextual_match_20261111/MemAdapter')
    paper = {name: (ROOT/'proposals/qamc_rpreasoner_paper'/(name+'.md')).read_text()
             for name in ('mle', 'ipe', 'generator')}
    return prompts, author, mem, paper


def initial_bodies(task, method):
    prompts, author, mem, paper = assets()
    if method in legacy.OWN:
        return [('Selector', legacy.selector(task, method, prompts))]
    if method == 'GEPA_UNIFIED':
        return [('Actor', legacy.gepa_unified.actor(task, author)['request'])]
    if method == 'MEMADAPTER_FULL':
        return [('MemInduction', mem.request(task, 'Stage1'))]
    if method == 'RPR_PAPER_FULL':
        return [('RPR_'+name.upper(), request) for name, request in legacy.rpr.estimator_requests(task, paper).items()]
    if method == 'DES2GEN_FULL':
        return [('Selector', legacy.d2g.decision_request(task, prompts['d2g']))]
    raise ValueError('No new method')


def replay_inherited(rows, cases):
    prompts, author, mem, paper = assets()
    lookup = {c['uid']: c for c in cases}
    for row in rows:
        task = task_for(lookup[row['uid']])
        request = row.get('actor_request')
        if not request:
            continue
        method = row['method']
        if method in legacy.OWN or method == 'GEPA_UNIFIED':
            expected = legacy.actor(task, row.get('selector_answer'), method, prompts, author)['request']
        elif method == 'MEMADAPTER_FULL':
            expected = mem.request(task, 'Stage3', row['memory_use_instructions'])
        elif method == 'RPR_PAPER_FULL':
            view = row['view']
            assert view['query'] == task.query and view['current_context'] == task.current_context
            assert view['facts'] == list(task.fixed_facts)
            assert view['source_evidence'] == [{'memory_id': m.memory_id, 'text': m.text} for m in task.memories]
            expected = body(paper['generator'], view, 4096)
        else:
            expected = legacy.d2g.generator_request(task, prompts['d2g'], row['decisions'])['request']
        if expected != request or sha(expected) != row['actor_request_sha256']:
            raise ValueError('Legacy full-system input changed')


def grading_jobs(p, cases, rows):
    grading = previous.spec.prior.parent.legacy.grading
    rubrics = grading.ext.load_rubrics(ROOT/'literature/qamc_pa_v1/RPEval/prompts/prompts_715.py')
    lookup = {c['uid']: c for c in cases}
    jobs = []
    for row in rows:
        if row.get('actor_status') != 'OK' or not row.get('answer'):
            continue
        case = lookup[row['uid']]
        ref = read(ROOT/case['evaluation_path'])
        if grading.ext.digest(ref) != case['evaluation_hash']:
            raise ValueError('Evaluation reference changed')
        prompt = grading.ext.aligned_prompt(rubrics, ref, row['answer'])
        request = grading.text_request(grading.ext.JUDGE_SYSTEM, prompt, 'gpt-4.1', 8192)
        jobs.append(job(p, row['uid'], row['method'], 'RPEvalJudge', request))
    return jobs


def build_plan():
    old = legacy.prepare(); legacy.check(old, False)
    native = bridge_probe.prepare(); bridge_probe.check(native, False)
    if read(bridge_probe.OUT/'RUN_STATE.json')['successful_responses'] != 2:
        raise ValueError('Native judge service bridge not established')
    frozen_data = read(DATA_OUT/'FROZEN_DATA.json')
    for name, digest in frozen_data['files'].items():
        if pin(ROOT/name) != digest:
            raise ValueError('Frozen official data changed: '+name)
    cases = read(DATA_OUT/'MANIFEST_300.json')
    inherited_ids = {c['uid'] for c in cases if c['legacy_same_configuration_uid']}
    inherited = [deepcopy(r) for r in read(legacy.OUT/'RESULT_ROWS.json') if r['uid'] in inherited_ids]
    if len(inherited) != 144:
        raise ValueError('Original24 six-method trajectories missing')
    replay_inherited(inherited, cases)
    protocols = deepcopy(old['protocols'])
    for key in protocols:
        protocols[key]['namespace'] = previous.spec.BASE.name+'/'+OUT.name+'/'+key
        protocols[key]['stream_cooldown_seconds'] = 60
    protocols['generation']['stages'] = {s: {'temperature': 0, 'max_tokens': 4096 if s == 'Actor' else 8192}
        for s in ('Selector', 'MemInduction', 'MemReflection', 'RPR_MLE', 'RPR_IPE', 'Actor')}
    protocols['grading'].update(model='gpt-4.1', stages={'RPEvalJudge': {'temperature': 0, 'max_tokens': 8192}})
    p = {'cases': cases, 'methods': list(METHODS), 'protocols': protocols,
        'service_reference_sha256': old['service_reference_sha256'],
        'maximum_new_physical_requests': 5382, 'new_algorithm_candidates': 0,
        'legacy_generation_uids': sorted(inherited_ids), 'new_generation_roots': 276,
        'not_confirmation': True, 'formal_official_multi_coverage': True,
        'no_parent_budget_reset': True, 'no_automatic_retries': True, 'no_online_repairs': True,
        'new_Writer_Store_or_retrieval_calls': 0}
    initial, allowed = [], []
    for case in cases:
        task = task_for(case)
        for method in METHODS:
            if task.uid not in inherited_ids:
                initial += [job(p, task.uid, method, stage, request) for stage, request in initial_bodies(task, method)]
                allowed += [sampling_key(unit(p, task.uid, method, s)) for s in STAGES[method]]
                allowed.append(sampling_key(unit(p, task.uid, method, 'RPEvalJudge')))
            else:
                row = next(r for r in inherited if (r['uid'], r['method']) == (task.uid, method))
                if row.get('actor_status') == 'OK' and row.get('answer'):
                    allowed.append(sampling_key(unit(p, task.uid, method, 'RPEvalJudge')))
    p.update(initial_requests=initial, allowed_unit_keys=sorted(allowed))
    old_smoke = list(previous.prepare()['smoke_ids'])
    fresh_smoke = [next(c['uid'] for c in cases if c['track'] == track and c['uid'] not in inherited_ids)
                   for track in ('explicit/multi', 'implicit/multi')]
    smoke = old_smoke+fresh_smoke
    remaining = {track: sorted([c['uid'] for c in cases if c['track'] == track and c['uid'] not in smoke],
        key=lambda uid: sha(['formal_multi_wave_v1', uid])) for track in ('explicit/multi', 'implicit/multi')}
    p['fresh_smoke_ids'] = fresh_smoke
    p['smoke_ids'] = smoke
    p['waves'] = [smoke]+[remaining['explicit/multi'][i:i+5]+remaining['implicit/multi'][i:i+5]
                         for i in range(0, len(remaining['explicit/multi']), 5)]
    frozen(OUT/'INHERITED_GENERATION_ROWS.json', inherited)
    prompts, author, mem, paper = assets()
    frozen(OUT/'FROZEN_METHODS.json', {'base': prompts, 'effect_selector': legacy.goal_effect.SYSTEM,
        'rpr': paper, 'complete_GEPA_policy': author.blobs['GEPA'].decode(),
        'memadapter': mem.manifest(), 'memadapter_complete_prompts': mem.prompts,
        'rpr_is_mechanism_reconstruction': True, 'd2g_is_not_full_ABIDE_calibration': True})
    files = {Path(__file__), ROOT/'tests/test_qamc_formal_multi_run.py', OUT/'RUN_RULES.md',
        DATA_OUT/'FROZEN_DATA.json', OUT/'INHERITED_GENERATION_ROWS.json', OUT/'FROZEN_METHODS.json',
        legacy.OUT/'PLAN.json', legacy.OUT/'RESULT_ROWS.json', bridge_probe.OUT/'PLAN.json',
        bridge_probe.OUT/'TERMINAL_ACCEPTANCE.json', bridge_probe.OUT/'CUMULATIVE_AT_REPORT.json'}
    files.update(ROOT/name for name in frozen_data['files'])
    files.update(ROOT/name for name in old['files'])
    p['files'] = {str(f.relative_to(ROOT)) if f.is_relative_to(ROOT) else str(f): pin(f) for f in sorted(files)}
    check(p, False)
    return p


def check(p, service=True):
    if (len(p['cases']), len(p['initial_requests']), len(p['allowed_unit_keys']),
            len(set(p['allowed_unit_keys'])), p['maximum_new_physical_requests']) != (300, 1932, 5382, 5382, 5382):
        raise ValueError('Frozen population or finite allocation changed')
    if len(p['legacy_generation_uids']) != 24 or p['new_algorithm_candidates'] != 0:
        raise ValueError('Legacy trajectory protection changed')
    if tuple(p['methods']) != METHODS or p['cases'] != read(DATA_OUT/'MANIFEST_300.json'):
        raise ValueError('Method or dataset changed')
    if p['protocols']['generation']['model'] != 'qwen3.8-flash' or p['protocols']['grading']['model'] != 'gpt-4.1':
        raise ValueError('No model substitution')
    if any(proto['concurrency'] != 8 or proto['spacing_seconds'] != 3.2 or proto['stream_cooldown_seconds'] != 60
           for proto in p['protocols'].values()):
        raise ValueError('Frozen pacing changed')
    if len({u for wave in p['waves'] for u in wave}) != 300 or sum(map(len, p['waves'])) != 300:
        raise ValueError('Wave population changed')
    for name, digest in p['files'].items():
        if pin(ROOT/name) != digest:
            raise ValueError('Frozen source changed: '+name)
    if service and previous.previous.prior.read_reference()[1] != p['service_reference_sha256']:
        raise ValueError('Service reference changed')


def prepare():
    if (OUT/'PLAN.json').exists():
        p = read(OUT/'PLAN.json'); check(p, False); return p
    p = build_plan(); frozen(OUT/'PLAN.json', p); return p


def engine(p, path=None, offline=False):
    dispatcher = previous.previous.prior.parent.previous.parent.latest.previous.previous.Dispatcher
    ex = dispatcher(ROOT, OUT, path or RUN, p,
        (lambda value: check(value, False)) if offline else check, job, block)
    records = previous.spec.prior.receipts(ex.run)
    if any(r['status'] == 'PENDING_DELIVERY_UNKNOWN' for r in records):
        raise ValueError('Inspect live handle; unknown delivery is not a retry opportunity')
    previous.previous.prior.activate(ex.gate, max((r['started_unix']+r.get('elapsed_seconds', 0)
        for r in records if r['status'] != 'OK'), default=0))

    def sampler(*args, **kwargs):
        value = previous.previous.prior.UsageObservableSampler(*args, **kwargs)
        value.control = previous.previous.prior.MinuteControl(value.control, ex.gate)
        return value

    for rt in ex.rt.values():
        rt.sampler_class = sampler
    return ex


def answer_from(ex, request):
    value = ex.observed(request)
    return value['response']['answer'] if value and value['status'] == 'OK' else None


def execute_wave(p, number, ex):
    cases = [c for c in p['cases'] if c['uid'] in p['waves'][number]]
    ids = {c['uid'] for c in cases}
    new_ids = ids-set(p['legacy_generation_uids'])
    prompts, author, mem, paper = assets()
    initial = [j for j in p['initial_requests'] if j['unit']['root_id'] in ids]
    ex.dispatch(f'w{number:02d}_fronts', initial)
    rows = []
    for old in read(OUT/'INHERITED_GENERATION_ROWS.json'):
        if old['uid'] not in ids:
            continue
        row = deepcopy(old)
        row['inherited_generation_row'] = deepcopy(old)
        row['legacy_qwen_score_reference'] = row.pop('score', None)
        row['legacy_qwen_raw_scores_reference'] = row.pop('raw_scores', {})
        row.pop('score_error', None)
        row.update(score=None, raw_scores={}, native_fields={}, judge_statuses={},
                   generation_origin='EXACT_FIXED_LEGACY_TRAJECTORY')
        rows.append(row)
    observations = {(j['unit']['root_id'], j['unit']['method'], j['unit']['stage']): ex.observed(j)
                    for j in initial}
    reflections = []
    for case in cases:
        if case['uid'] not in new_ids:
            continue
        task = task_for(case)
        for method in METHODS:
            row = {'uid': task.uid, 'benchmark': 'rpeval', 'method': method, 'read_status': 'UNAVAILABLE',
                'actor_status': 'NOT_ISSUED', 'score': None, 'raw_scores': {}, 'native_fields': {},
                'generation_origin': 'FROZEN_FORMAL_PIPELINE', 'reader_responses': {}, 'reader_statuses': {},
                'reader_requests': {}, 'reader_origins': {}}
            for stage, request in initial_bodies(task, method):
                value = observations.get((task.uid, method, stage))
                row['reader_requests'][stage] = request
                row['reader_statuses'][stage] = value['status'] if value else 'UNISSUED'
                row['reader_origins'][stage] = value.get('origin') if value else None
                if value and value['status'] == 'OK':
                    row['reader_responses'][stage] = value['response']['answer']
            rows.append(row)
            if method == 'MEMADAPTER_FULL' and 'MemInduction' in row['reader_responses']:
                try:
                    row['memory_boundary_cards'] = mem.parse(task, 'Stage1', row['reader_responses']['MemInduction'])
                    reflections.append(job(p, task.uid, method, 'MemReflection', mem.request(task, 'Stage2', row['memory_boundary_cards'])))
                except (ValueError, TypeError, KeyError) as error:
                    row.update(read_status='INVALID_STAGE1_CONTRACT', read_error=str(error))
    ex.dispatch(f'w{number:02d}_reflections', reflections)
    actors = []
    for row in rows:
        if row['uid'] not in new_ids:
            continue
        task = task_for(next(c for c in cases if c['uid'] == row['uid']))
        method = row['method']
        raw = row['reader_responses']
        try:
            if method == 'GEPA_UNIFIED':
                built = legacy.gepa_unified.actor(task, author)
            elif method == 'MEMADAPTER_FULL':
                j = next((j for j in reflections if j['unit']['root_id'] == row['uid']), None)
                value = ex.observed(j) if j else None
                if j:
                    row['reader_requests']['MemReflection'] = j['request']
                row['reader_statuses']['MemReflection'] = value['status'] if value else 'UNISSUED'
                if not value or value['status'] != 'OK':
                    continue
                raw['MemReflection'] = value['response']['answer']
                instructions = mem.parse(task, 'Stage2', raw['MemReflection'])
                row['memory_use_instructions'] = instructions
                built = {'view': {'query': task.query, 'current_context': task.current_context,
                    'facts': list(task.fixed_facts), 'source_evidence': [
                        {'memory_id': m.memory_id, 'text': m.text} for m in task.memories],
                    'memory_use_instructions': instructions['memory_use_instructions']},
                    'request': mem.request(task, 'Stage3', instructions)}
            elif method in legacy.OWN:
                if 'Selector' not in raw:
                    continue
                row['selector_answer'] = raw['Selector']
                built = legacy.actor(task, raw['Selector'], method, prompts, author)
            elif method == 'RPR_PAPER_FULL':
                if not {'RPR_MLE', 'RPR_IPE'} <= raw.keys():
                    continue
                built = legacy.rpr.generator_request(task, paper, parse_object(raw['RPR_MLE']), parse_object(raw['RPR_IPE']))
                row['aggregation'] = built['aggregation']
            else:
                if 'Selector' not in raw:
                    continue
                row['decisions'] = legacy.d2g.parse_decisions(task, raw['Selector'])
                built = legacy.d2g.generator_request(task, prompts['d2g'], row['decisions'])
            row.update(read_status='VALID', view=built['view'], actor_request=built['request'],
                       actor_request_sha256=sha(built['request']))
            for name in ('selection', 'effect_audit', 'audit'):
                if name in built:
                    row['compiler_'+name] = deepcopy(built[name])
            if method != 'GEPA_UNIFIED':
                actors.append(job(p, row['uid'], method, 'Actor', built['request']))
        except (ValueError, TypeError, KeyError) as error:
            row.update(read_status='INVALID_CONTRACT', read_error=str(error))
    frozen(OUT/'checkpoints'/f'w{number:02d}_reads.json', rows)
    ex.dispatch(f'w{number:02d}_actors', actors)
    for row in rows:
        if row['uid'] not in new_ids or 'actor_request' not in row:
            continue
        j = job(p, row['uid'], row['method'], 'Actor', row['actor_request'])
        value = ex.observed(j)
        row['actor_status'] = value['status'] if value else 'UNISSUED'
        row['actor_origin'] = value.get('origin') if value else None
        if value and value['status'] == 'OK':
            row['answer'] = value['response']['answer']
    frozen(OUT/'checkpoints'/f'w{number:02d}_answers.json', rows)
    grades = grading_jobs(p, cases, rows)
    ex.dispatch(f'w{number:02d}_native_grades', grades)
    for row in rows:
        j = next((j for j in grades if (j['unit']['root_id'], j['unit']['method']) == (row['uid'], row['method'])), None)
        value = ex.observed(j) if j else None
        row['judge_statuses'] = {'RPEvalJudge': value['status'] if value else 'UNISSUED'}
        if value and value['status'] == 'OK':
            raw = value['response']['answer']; row['raw_scores']['RPEvalJudge'] = raw
            try:
                n = len(task_for(next(c for c in cases if c['uid'] == row['uid'])).memories)
                obj = parse_object(raw)
                row['native_fields'], row['invalid_native_fields'] = fields(obj, n, True)
                row['score'] = {**previous.spec.prior.parent.legacy.grading.ext.parse_score(obj, n, True),
                    'judge_variant': 'author_rubric_GPT41_8192', 'fully_official': False}
            except (ValueError, TypeError, KeyError) as error:
                row['score_error'] = str(error)
    frozen(OUT/'waves'/f'{number:02d}.json', {'wave': number, 'rows': rows})
    return rows


def main(action):
    p = prepare()
    if action == 'prepare':
        print({'new_calls': 0, 'maximum': 5382, 'initial': 1932, 'legacy_trajectories': 144}); return
    state = read(OUT/'RUN_STATE.json') if (OUT/'RUN_STATE.json').exists() else {}
    if state.get('phase') == 'FORMAL_TERMINAL' or (action == 'smoke' and state.get('phase') == 'SMOKE_TERMINAL'):
        raise ValueError('Completed phase is not restarted')
    if action == 'pilot' and not read(OUT/'SMOKE_ACCEPTANCE.json')['pass']:
        raise ValueError('Smoke did not establish all six full pipelines')
    check(p, True)
    with previous.previous.prior.runner_lock(RUN/'runner.lock'):
        previous.previous.prior.atomic_json(OUT/'RUN_STATE.json', {'phase': 'RUNNING', 'pid': os.getpid(),
            'panel': action, 'updated_unix': time.time(), 'goal_complete': False})
        ex = ScopedDispatcher(engine(p))
        for number in ([0] if action == 'smoke' else range(len(p['waves']))):
            path = OUT/'waves'/f'{number:02d}.json'
            rows = read(path)['rows'] if path.exists() else execute_wave(p, number, ex)
            previous.previous.prior.atomic_json(OUT/'WAVE_CHECKPOINT.json', {'last_completed_wave': number,
                'completed_waves': len(list((OUT/'waves').glob('*.json'))), 'pid': os.getpid(),
                'goal_complete': False, 'updated_unix': time.time()})
            if action == 'smoke':
                fresh = [r for r in rows if r['uid'] in p['fresh_smoke_ids']]
                accepted = all(any(r['method'] == m and r['actor_status'] == 'OK' and 'match' in r['native_fields']
                                   for r in fresh) for m in METHODS)
                frozen(OUT/'SMOKE_ACCEPTANCE.json', {'pass': accepted, 'all_six_fresh_pipeline_paths_observed': accepted,
                    'semantic_scores_used_to_select_prompt': False, 'new_model_calls': len(previous.spec.prior.receipts(RUN)),
                    'rows': len(rows), 'fresh_answers': sum(r['actor_status'] == 'OK' for r in fresh)})
        if action == 'pilot':
            all_rows = [r for i in range(len(p['waves'])) for r in read(OUT/'waves'/f'{i:02d}.json')['rows']]
            frozen(OUT/'RESULT_ROWS.json', all_rows)
            for key in p['protocols']:
                (RUN/key/'STOP').write_text('Frozen formal multi coverage terminal. No expansion.\n')
        previous.previous.prior.atomic_json(OUT/'RUN_STATE.json', {'phase': 'SMOKE_TERMINAL' if action == 'smoke' else 'FORMAL_TERMINAL',
            'pid': None, 'registered_requests': len(previous.spec.prior.receipts(RUN)),
            'maximum': 5382, 'goal_complete': False, 'updated_unix': time.time()})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'smoke', 'pilot'])
    main(parser.parse_args().action)
